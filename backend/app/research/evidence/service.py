"""EvidenceItem persistence with project, paper and source-location integrity."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import DocumentElement, Paper, Section
from app.models.project import ProjectPaper, ResearchProject
from app.models.research import EvidenceItem
from app.research.context.paper_profile import paper_source_fingerprint
from app.research.context.schemas import EvidenceCandidateContext


class EvidenceProvenanceError(ValueError):
    """Evidence does not resolve to a real source inside the owned project."""


def _authors_json(authors: Any) -> list[str]:
    if isinstance(authors, list):
        return [str(value).strip() for value in authors if str(value).strip()]
    return [value.strip() for value in str(authors or "").split(",") if value.strip()]


class EvidenceService:
    """Persist only evidence actually selected by a caller for later generation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def source_fingerprint(self, paper: Paper) -> str:
        sections = list(
            (
                await self.db.execute(
                    select(Section)
                    .where(Section.paper_id == str(paper.id))
                    .order_by(Section.order_index)
                )
            ).scalars().all()
        )
        return paper_source_fingerprint(paper, sections)

    async def _owned_source(
        self,
        *,
        project_id: str,
        paper_id: str,
        user_id: str,
    ) -> Paper:
        project = await self.db.get(ResearchProject, project_id)
        if project is None or project.user_id != user_id:
            raise EvidenceProvenanceError("project_not_found")
        membership = (
            await self.db.execute(
                select(ProjectPaper).where(
                    ProjectPaper.project_id == project_id,
                    ProjectPaper.paper_id == paper_id,
                )
            )
        ).scalars().first()
        paper = await self.db.get(Paper, paper_id)
        if membership is None or paper is None or paper.user_id != user_id:
            raise EvidenceProvenanceError("paper_not_in_project")
        return paper

    async def validate_locator(
        self,
        *,
        paper_id: str,
        section_id: str | None,
        element_id: str | None,
        chunk_id: str | None,
    ) -> tuple[Section | None, DocumentElement | None]:
        if not (section_id or element_id or chunk_id):
            raise EvidenceProvenanceError("missing_locator")
        section = await self.db.get(Section, section_id) if section_id else None
        if section_id and (section is None or str(section.paper_id) != paper_id):
            raise EvidenceProvenanceError("invalid_section")
        element = await self.db.get(DocumentElement, element_id) if element_id else None
        if element_id and (element is None or str(element.paper_id) != paper_id):
            raise EvidenceProvenanceError("invalid_element")
        if element and section_id and str(element.section_id or "") != section_id:
            raise EvidenceProvenanceError("section_element_mismatch")
        if chunk_id and not (section or element):
            raise EvidenceProvenanceError("unverifiable_chunk")
        return section, element

    async def persist_used(
        self,
        *,
        candidate: EvidenceCandidateContext,
        user_id: str,
        normalized_claim: str,
        evidence_type: str = "quote",
    ) -> EvidenceItem:
        paper = await self._owned_source(
            project_id=candidate.project_id,
            paper_id=candidate.paper_id,
            user_id=user_id,
        )
        section, element = await self.validate_locator(
            paper_id=candidate.paper_id,
            section_id=candidate.section_id,
            element_id=candidate.element_id,
            chunk_id=candidate.chunk_id,
        )
        page_number = candidate.page_number or (element.page_number if element else None)
        bbox = candidate.bbox or (element.bbox if element else None)
        source_fingerprint = await self.source_fingerprint(paper)
        item = EvidenceItem(
            project_id=candidate.project_id,
            paper_id=candidate.paper_id,
            section_id=str(section.id) if section else None,
            element_id=str(element.id) if element else None,
            chunk_id=candidate.chunk_id,
            page_number=page_number,
            bbox=bbox,
            evidence_type=evidence_type,
            snippet=candidate.snippet,
            normalized_claim=str(normalized_claim or "")[:10_000],
            source_title=str(paper.title or "")[:500],
            source_authors=_authors_json(paper.authors),
            source_year=paper.publication_year,
            doi=str(paper.doi or "")[:200] or None,
            source_type="retrieval_generated",
            status="active",
            source_fingerprint=source_fingerprint,
            verification_status="unverified",
            created_by="retrieval",
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item


__all__ = ["EvidenceProvenanceError", "EvidenceService"]
