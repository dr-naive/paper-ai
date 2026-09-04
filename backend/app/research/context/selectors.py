"""Deterministic, project-owned Paper Profile candidate selection."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.project import ProjectPaper, ResearchProject
from app.rag.hybrid_retrieval import tokenize

from .paper_profile import PaperProfile, read_paper_profile
from .schemas import CandidatePaperContext, CandidateSelectionResult, ProjectProfileContext


class CandidateSelectionProjectNotFoundError(LookupError):
    """The project is absent or not owned by the caller."""


def _profile_text(profile: PaperProfile, paper: Paper, project_paper: ProjectPaper) -> str:
    values = [
        paper.title,
        profile.topic,
        *profile.research_questions,
        *profile.research_subjects,
        *profile.methods,
        *profile.datasets_or_samples,
        *profile.main_results,
        *profile.conclusions,
        *profile.contributions,
        *profile.limitations,
        *profile.keywords,
        profile.project_relevance,
        *(project_paper.tags or []),
        project_paper.notes,
    ]
    return " ".join(str(value or "") for value in values)


def _selection_score(
    query: str,
    profile: PaperProfile,
    paper: Paper,
    project_paper: ProjectPaper,
) -> float:
    query_tokens = set(tokenize(query))
    profile_tokens = set(tokenize(_profile_text(profile, paper, project_paper)))
    overlap = len(query_tokens & profile_tokens) / max(len(query_tokens), 1)
    role_bonus = {"core": 0.08, "related": 0.04, "background": 0.0}.get(
        str(project_paper.role or ""), 0.0
    )
    priority = max(1, min(int(project_paper.reading_priority or 3), 5))
    stale_penalty = 0.05 if profile.status == "stale" else 0.0
    return round(max(0.0, overlap + role_bonus + priority * 0.005 - stale_penalty), 6)


class CandidatePaperSelector:
    """Select 3–5 papers without exposing every full text or raw project record."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def select(
        self,
        *,
        project_id: str,
        user_id: str,
        project_profile: ProjectProfileContext,
        instruction: str,
        current_section_title: str = "",
        limit: int = 5,
    ) -> CandidateSelectionResult:
        project = await self.db.get(ResearchProject, project_id)
        if project is None or project.user_id != user_id:
            raise CandidateSelectionProjectNotFoundError(project_id)

        rows = (
            await self.db.execute(
                select(ProjectPaper, Paper)
                .join(Paper, Paper.id == ProjectPaper.paper_id)
                .where(
                    ProjectPaper.project_id == project_id,
                    Paper.user_id == user_id,
                )
            )
        ).all()
        query = " ".join(
            value
            for value in (
                instruction.strip(),
                current_section_title.strip(),
                project_profile.research_topic,
                project_profile.research_question,
                " ".join(project_profile.keywords),
            )
            if value
        )
        ranked: list[tuple[float, ProjectPaper, Paper, PaperProfile]] = []
        for project_paper, paper in rows:
            profile = read_paper_profile(project_paper.analysis_card)
            if profile is None or profile.status not in {"ready", "stale"}:
                continue
            score = _selection_score(query, profile, paper, project_paper)
            ranked.append((score, project_paper, paper, profile))
        ranked.sort(key=lambda item: (-item[0], str(item[2].id)))

        bounded_limit = max(1, min(int(limit), 5))
        candidates = [
            CandidatePaperContext(
                project_id=project_id,
                paper_id=str(paper.id),
                title=str(paper.title or "")[:500],
                authors=str(paper.authors or "")[:2_000],
                publication_year=paper.publication_year,
                doi=str(paper.doi or "")[:200],
                role=str(project_paper.role or "related"),
                profile_status=profile.status,
                profile_version=profile.profile_version,
                topic=profile.topic,
                methods=profile.methods[:12],
                main_results=profile.main_results[:12],
                keywords=profile.keywords[:20],
                project_relevance=profile.project_relevance,
                selection_score=score,
            )
            for score, project_paper, paper, profile in ranked[:bounded_limit]
        ]
        return CandidateSelectionResult(
            candidates=candidates,
            imported_paper_count=len(rows),
            ready_profile_count=len(ranked),
        )


__all__ = [
    "CandidatePaperSelector",
    "CandidateSelectionProjectNotFoundError",
]
