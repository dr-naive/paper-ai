"""Ownership-aware, bounded project context assembly."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.project_service import project_profile_dict
from app.models.document import WritingDocument
from app.models.project import ProjectPaper, ResearchProject
from app.models.research import MemoryItem

from .schemas import (
    DISCOVERY_MEMORY_TYPES,
    DiscoveryContext,
    LiteratureMemoryContext,
    ProjectProfileContext,
    WritingRetrievalContext,
)


class ProjectContextNotFoundError(LookupError):
    """The project is absent or is not owned by the requesting user."""


def _tag_values(tags: Any, prefix: str) -> list[str]:
    if not isinstance(tags, list):
        return []
    return [str(item)[len(prefix):].strip() for item in tags if isinstance(item, str) and item.startswith(prefix) and str(item)[len(prefix):].strip()]


def _append_unique(values: list[str], candidates: Iterable[Any], *, limit: int, max_length: int = 2000) -> None:
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        value = candidate.strip()[:max_length]
        if value and value not in values:
            values.append(value)
        if len(values) >= limit:
            return


def _preference_ids(project: ResearchProject, key: str, *, statuses: set[str] | None = None) -> list[str]:
    preferences = project.preferences if isinstance(project.preferences, dict) else {}
    values: list[str] = []
    for raw in preferences.get(key) or []:
        if not isinstance(raw, dict):
            continue
        if statuses is not None and str(raw.get("status") or "").casefold() not in statuses:
            continue
        identifier = raw.get("source_paper_id") if key == "discovery_favorites" else raw.get("paper_id")
        if identifier:
            _append_unique(values, [str(identifier)], limit=200, max_length=512)
    return values


class ProjectContextManager:
    """Build typed context for a use case without constructing final prose."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _owned_project(self, project_id: str, user_id: str | None) -> ResearchProject:
        project = await self.db.get(ResearchProject, project_id)
        if project is None or (user_id and project.user_id != user_id):
            raise ProjectContextNotFoundError(project_id)
        return project

    async def build_discovery_context(
        self,
        project_id: str,
        user_id: str | None = None,
    ) -> DiscoveryContext:
        """Return only the profile and durable discovery memory for a project.

        The query intentionally filters MemoryItem by stable Literature Memory
        types. Legacy ``ResearchProject.memory`` is not treated as context.
        """
        project = await self._owned_project(project_id, user_id)
        rows = (
            await self.db.execute(
                select(MemoryItem)
                .where(
                    MemoryItem.project_id == project_id,
                    MemoryItem.user_id == project.user_id,
                    MemoryItem.superseded_by.is_(None),
                    MemoryItem.type.in_(DISCOVERY_MEMORY_TYPES),
                )
                .order_by(MemoryItem.updated_at.desc())
                .limit(100)
            )
        ).scalars().all()

        summary = ""
        important_keywords: list[str] = []
        preferred: list[str] = []
        excluded: list[str] = []
        notes: list[str] = []
        for item in rows:
            content = str(item.content or "").strip()
            if item.type == "literature_intent" and not summary:
                summary = content[:2_000]
            if item.type == "literature_preference":
                _append_unique(preferred, [*_tag_values(item.tags, "direction:"), content], limit=12)
            elif item.type == "literature_exclusion":
                _append_unique(excluded, [*_tag_values(item.tags, "direction:"), content], limit=12)
            elif item.type == "project_decision":
                _append_unique(notes, [content], limit=12)
            _append_unique(important_keywords, _tag_values(item.tags, "keyword:"), limit=30, max_length=100)

        # The existing discovery persistence stores metadata snapshots in
        # preferences. Read only stable identifiers, never the raw payloads.
        favorite_ids = _preference_ids(project, "discovery_favorites")
        imported_ids = _preference_ids(
            project,
            "paper_imports",
            statuses={"ready", "imported", "completed"},
        )
        project_paper_ids = (
            await self.db.execute(
                select(ProjectPaper.paper_id)
                .where(ProjectPaper.project_id == project_id)
                .limit(200)
            )
        ).scalars().all()
        _append_unique(imported_ids, [str(value) for value in project_paper_ids], limit=200, max_length=512)

        profile = ProjectProfileContext.model_validate(project_profile_dict(project))
        memory = LiteratureMemoryContext(
            search_intent_summary=summary,
            important_keywords=important_keywords,
            preferred_directions=preferred,
            excluded_directions=excluded,
            important_search_notes=notes,
            favorite_paper_ids=favorite_ids,
            imported_paper_ids=imported_ids,
        )
        return DiscoveryContext(project_profile=profile, literature_memory=memory)

    async def build_writing_context(
        self,
        *,
        project_id: str,
        user_id: str,
        instruction: str,
        document_id: str | None = None,
        current_section_title: str = "",
        current_section_path: list[str] | None = None,
        selection: str = "",
        nearby_text: str = "",
        intent: str = "general",
        max_candidates: int = 5,
        top_k: int = 10,
        allowed_paper_ids: list[str] | None = None,
    ) -> WritingRetrievalContext:
        """Build one bounded writing context through candidate-restricted retrieval."""
        project = await self._owned_project(project_id, user_id)
        if document_id:
            document = await self.db.get(WritingDocument, document_id)
            if document is None or str(document.project_id) != project_id:
                raise ProjectContextNotFoundError(document_id)

        profile = ProjectProfileContext.model_validate(project_profile_dict(project))
        retrieval_need = "\n".join(
            value
            for value in (
                instruction.strip(),
                current_section_title.strip(),
                selection.strip()[:4_000],
                nearby_text.strip()[:2_000],
            )
            if value
        )
        if not retrieval_need:
            raise ValueError("instruction is required")

        # Delayed import keeps discovery-only context use independent of RAG setup.
        from app.research.evidence.retrieval import ProjectEvidenceRetrievalService

        status, candidates, evidence = await ProjectEvidenceRetrievalService(self.db).retrieve(
            project_id=project_id,
            user_id=user_id,
            project_profile=profile,
            instruction=retrieval_need,
            current_section_title=current_section_title,
            intent=intent,
            max_candidates=max_candidates,
            top_k=top_k,
            **({"allowed_paper_ids": allowed_paper_ids} if allowed_paper_ids is not None else {}),
        )
        return WritingRetrievalContext(
            status=status,
            project_profile=profile,
            document_id=document_id,
            instruction=instruction.strip(),
            current_section_title=current_section_title.strip()[:500],
            current_section_path=[str(value).strip()[:500] for value in (current_section_path or [])[:20] if str(value).strip()],
            selection=selection.strip()[:12_000],
            nearby_text=nearby_text.strip()[:12_000],
            candidate_papers=candidates,
            evidence=evidence,
        )
