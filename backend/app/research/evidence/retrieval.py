"""Candidate-restricted Hybrid Retrieval with stable Evidence provenance."""
from __future__ import annotations

import math
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.project import ProjectPaper
from app.rag.hybrid_retrieval import HybridPaperRetriever, tokenize
from app.research.context.schemas import (
    CandidatePaperContext,
    EvidenceCandidateContext,
    ProjectProfileContext,
)
from app.research.context.selectors import CandidatePaperSelector


def rank_project_chunks(
    query: str,
    groups: list[tuple[CandidatePaperContext | ProjectPaper, Paper, list[dict[str, Any]]]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Rank across candidate papers while retaining source identity and diversity."""
    query_tokens = set(tokenize(query))
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for candidate, paper, chunks in groups:
        role = str(getattr(candidate, "role", "related") or "related")
        project_id = str(getattr(candidate, "project_id", ""))
        for rank, chunk in enumerate(chunks, start=1):
            item = dict(chunk)
            text_tokens = set(tokenize(f"{item.get('section', '')} {item.get('content', '')}"))
            overlap = len(query_tokens & text_tokens) / max(len(query_tokens), 1)
            local_score = float(item.get("rerank_score") or 0.0)
            role_bonus = {"core": 0.04, "related": 0.02, "background": 0.0}.get(role, 0.0)
            score = overlap * 0.75 + min(local_score, 1.0) * 0.15 + 1 / (60 + rank) + role_bonus
            item.update(
                {
                    "paper_id": str(paper.id),
                    "paper_title": str(paper.title or ""),
                    "paper_authors": str(paper.authors or ""),
                    "paper_year": getattr(paper, "publication_year", None),
                    "paper_doi": str(getattr(paper, "doi", "") or ""),
                    "paper_role": role,
                    "project_id": project_id,
                    "project_rerank_score": round(score, 6),
                }
            )
            scored.append((score, str(paper.id), item))
    scored.sort(key=lambda value: value[0], reverse=True)

    paper_count = max(len(groups), 1)
    per_paper_cap = max(2, math.ceil(top_k / paper_count) + 1)
    counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for _score, paper_id, item in scored:
        signature = (
            paper_id,
            str(item.get("page") or ""),
            re.sub(r"\s+", "", str(item.get("content") or ""))[:180],
        )
        if signature in seen or counts.get(paper_id, 0) >= per_paper_cap:
            continue
        seen.add(signature)
        counts[paper_id] = counts.get(paper_id, 0) + 1
        selected.append(item)
        if len(selected) >= top_k:
            break
    for index, item in enumerate(selected, start=1):
        item["source_id"] = f"S{index}"
        item["content"] = str(item.get("content") or "")[:2_000]
    return selected


def _chunk_identifier(item: dict[str, Any]) -> str:
    if item.get("element_id"):
        return f"element:{item['element_id']}"
    if item.get("table_id") and item.get("row_index") is not None:
        return f"table:{item['table_id']}:row:{item['row_index']}"
    chunk_index = str(item.get("chunk_index") or item.get("source_id") or "0")
    section_id = str(item.get("section_id") or "unmapped")
    return f"chunk:{section_id}:{chunk_index}"[:200]


def _positive_page(value: Any) -> int | None:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page >= 1 else None


class ProjectEvidenceRetrievalService:
    """Own the full project → candidate papers → evidence-chunks boundary."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.selector = CandidatePaperSelector(db)

    async def retrieve(
        self,
        *,
        project_id: str,
        user_id: str,
        project_profile: ProjectProfileContext,
        instruction: str,
        current_section_title: str = "",
        intent: str = "general",
        max_candidates: int = 5,
        top_k: int = 10,
    ) -> tuple[str, list[CandidatePaperContext], list[EvidenceCandidateContext]]:
        selection = await self.selector.select(
            project_id=project_id,
            user_id=user_id,
            project_profile=project_profile,
            instruction=instruction,
            current_section_title=current_section_title,
            limit=max_candidates,
        )
        if selection.imported_paper_count == 0:
            return "no_imported_papers", [], []
        if not selection.candidates:
            return "no_ready_profiles", [], []

        retriever = HybridPaperRetriever(self.db)
        candidate_by_id = {candidate.paper_id: candidate for candidate in selection.candidates}
        groups: list[tuple[CandidatePaperContext, Paper, list[dict[str, Any]]]] = []
        per_paper_k = max(2, min(6, math.ceil(top_k / len(selection.candidates)) + 1))
        for candidate in selection.candidates:
            paper = await self.db.get(Paper, candidate.paper_id)
            if paper is None or paper.user_id != user_id:
                continue
            result = await retriever.retrieve(
                paper_id=candidate.paper_id,
                question=instruction,
                history_context="",
                intent=intent,
            )
            if result.chunks:
                groups.append((candidate, paper, result.chunks[:per_paper_k]))

        ranked = rank_project_chunks(instruction, groups, max(1, min(int(top_k), 20)))
        evidence: list[EvidenceCandidateContext] = []
        for item in ranked:
            candidate = candidate_by_id.get(str(item.get("paper_id") or ""))
            if candidate is None:
                continue
            evidence.append(
                EvidenceCandidateContext(
                    project_id=project_id,
                    paper_id=candidate.paper_id,
                    chunk_id=_chunk_identifier(item),
                    snippet=str(item.get("content") or "")[:2_000],
                    section_id=str(item["section_id"]) if item.get("section_id") else None,
                    section_title=str(item.get("section") or "")[:500],
                    page_number=_positive_page(item.get("page")),
                    element_id=str(item["element_id"]) if item.get("element_id") else None,
                    bbox=item.get("bbox"),
                    paper_title=candidate.title,
                    paper_authors=candidate.authors,
                    publication_year=candidate.publication_year,
                    doi=candidate.doi,
                    retrieval_score=max(0.0, float(item.get("project_rerank_score") or 0.0)),
                    retrieval_method=str(item.get("retrieval_method") or "hybrid")[:80],
                )
            )
        status = "ready" if evidence else "no_supporting_evidence"
        return status, selection.candidates, evidence


__all__ = ["ProjectEvidenceRetrievalService", "rank_project_chunks"]
