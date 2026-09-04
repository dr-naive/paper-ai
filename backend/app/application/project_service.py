"""Application use cases for Project metadata, ownership, and paper membership."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.project import ProjectPaper, ResearchProject, WritingArtifact

logger = logging.getLogger(__name__)

PROJECT_SCOPE_KEY = "research_scope"
PROJECT_SCOPE_DEFAULTS: dict[str, Any] = {
    "field": "",
    "research_subject": "",
    "research_question": "",
    "research_goal": "",
    "keywords": [],
    "method_direction": "",
    "notes": "",
}
PROJECT_SCOPE_TEXT_LIMITS = {
    "field": 200,
    "research_subject": 500,
    "research_question": 2000,
    "research_goal": 2000,
    "method_direction": 1000,
    "notes": 4000,
}


class ProjectNotFoundError(LookupError):
    """The project is absent or not owned by the requesting user."""


class PaperNotFoundError(LookupError):
    """The paper is absent or not owned by the requesting user."""


def normalize_research_scope(value: Any) -> dict[str, Any]:
    """Return the stable public research-scope shape from flexible JSON storage."""
    source = value if isinstance(value, dict) else {}
    normalized = dict(PROJECT_SCOPE_DEFAULTS)
    for key, default in PROJECT_SCOPE_DEFAULTS.items():
        candidate = source.get(key, default)
        if isinstance(default, list):
            keywords: list[str] = []
            if isinstance(candidate, list):
                for value in candidate[:30]:
                    if not isinstance(value, str):
                        continue
                    keyword = value.strip()[:100]
                    if keyword and keyword not in keywords:
                        keywords.append(keyword)
            normalized[key] = keywords
        else:
            normalized[key] = (
                candidate.strip()[:PROJECT_SCOPE_TEXT_LIMITS[key]]
                if isinstance(candidate, str)
                else ""
            )
    return normalized


def project_profile_dict(project: ResearchProject) -> dict[str, Any]:
    """Build the typed Project Profile shape from existing project storage.

    V1 keeps the profile in ``ResearchProject`` and its structured
    ``preferences.research_scope`` JSON rather than introducing a 1:1 table.
    """
    scope = normalize_research_scope((project.preferences or {}).get(PROJECT_SCOPE_KEY))
    return {
        "project_id": str(project.id),
        "title": str(project.title or "").strip(),
        "research_topic": str(project.research_topic or "").strip(),
        "field": scope["field"],
        "research_subject": scope["research_subject"],
        "research_question": scope["research_question"],
        "research_goal": scope["research_goal"],
        "keywords": list(scope["keywords"]),
        "method_direction": scope["method_direction"],
        "user_notes": scope["notes"] or str(project.abstract or "").strip()[:PROJECT_SCOPE_TEXT_LIMITS["notes"]],
        "updated_at": project.updated_at,
    }


def project_dict(project: ResearchProject, **counts: int) -> dict[str, Any]:
    payload = project.to_dict()
    payload[PROJECT_SCOPE_KEY] = normalize_research_scope(
        (project.preferences or {}).get(PROJECT_SCOPE_KEY)
    )
    payload.update(counts)
    return payload


@dataclass(slots=True)
class ProjectService:
    db: AsyncSession

    async def get_owned_project(self, project_id: str, user_id: str) -> ResearchProject:
        project = await self.db.get(ResearchProject, project_id)
        if project is None or project.user_id != user_id:
            raise ProjectNotFoundError(project_id)
        return project

    async def list_projects(
        self,
        *,
        user_id: str,
        page: int,
        page_size: int,
        status: str | None,
        query: str | None,
    ) -> dict[str, Any]:
        stmt = select(ResearchProject).where(ResearchProject.user_id == user_id)
        if status:
            stmt = stmt.where(ResearchProject.status == status)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                ResearchProject.title.ilike(like)
                | ResearchProject.research_topic.ilike(like)
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        projects = (
            await self.db.execute(
                stmt.order_by(ResearchProject.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        paper_counts: dict[str, int] = {}
        artifact_counts: dict[str, int] = {}
        if projects:
            project_ids = [project.id for project in projects]
            paper_rows = (
                await self.db.execute(
                    select(ProjectPaper.project_id, func.count(ProjectPaper.id))
                    .where(ProjectPaper.project_id.in_(project_ids))
                    .group_by(ProjectPaper.project_id)
                )
            ).all()
            paper_counts = {row[0]: row[1] for row in paper_rows}
            artifact_rows = (
                await self.db.execute(
                    select(WritingArtifact.project_id, func.count(WritingArtifact.id))
                    .where(WritingArtifact.project_id.in_(project_ids))
                    .group_by(WritingArtifact.project_id)
                )
            ).all()
            artifact_counts = {row[0]: row[1] for row in artifact_rows}

        return {
            "items": [
                project_dict(
                    project,
                    paper_count=paper_counts.get(project.id, 0),
                    artifact_count=artifact_counts.get(project.id, 0),
                )
                for project in projects
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def create_project(
        self,
        *,
        user_id: str,
        title: str,
        research_topic: str,
        abstract: str,
        phase: str,
        preferences: dict[str, Any],
        research_scope: dict[str, Any] | None,
        status: str,
    ) -> dict[str, Any]:
        stored_preferences = dict(preferences)
        stored_preferences[PROJECT_SCOPE_KEY] = normalize_research_scope(
            research_scope if research_scope is not None else stored_preferences.get(PROJECT_SCOPE_KEY)
        )
        project = ResearchProject(
            user_id=user_id,
            title=title,
            research_topic=research_topic,
            abstract=abstract,
            phase=phase,
            status=status,
            memory={"summary": "", "notes": []},
            preferences=stored_preferences,
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project_dict(project)

    async def get_project_detail(self, *, project_id: str, user_id: str) -> dict[str, Any]:
        project = await self.get_owned_project(project_id, user_id)
        paper_count = (
            await self.db.execute(
                select(func.count()).select_from(ProjectPaper).where(
                    ProjectPaper.project_id == project_id
                )
            )
        ).scalar() or 0
        artifact_count = (
            await self.db.execute(
                select(func.count()).select_from(WritingArtifact).where(
                    WritingArtifact.project_id == project_id
                )
            )
        ).scalar() or 0
        return project_dict(
            project,
            paper_count=paper_count,
            artifact_count=artifact_count,
        )

    async def update_project(
        self,
        *,
        project_id: str,
        user_id: str,
        changes: dict[str, Any],
        research_scope: dict[str, Any] | None,
    ) -> dict[str, Any]:
        project = await self.get_owned_project(project_id, user_id)
        updates = dict(changes)
        if "preferences" in updates:
            preferences = dict(updates["preferences"] or {})
            preferences[PROJECT_SCOPE_KEY] = normalize_research_scope(
                preferences.get(PROJECT_SCOPE_KEY)
            )
            updates["preferences"] = preferences
        if research_scope is not None:
            preferences = dict(updates.pop("preferences", project.preferences or {}) or {})
            current_scope = normalize_research_scope(preferences.get(PROJECT_SCOPE_KEY))
            for key, value in research_scope.items():
                current_scope[key] = PROJECT_SCOPE_DEFAULTS[key] if value is None else value
            preferences[PROJECT_SCOPE_KEY] = current_scope
            updates["preferences"] = preferences
        for key, value in updates.items():
            setattr(project, key, value)
        await self.db.commit()
        await self.db.refresh(project)
        return project_dict(project)

    async def delete_project(self, *, project_id: str, user_id: str) -> None:
        project = await self.get_owned_project(project_id, user_id)
        await self.db.delete(project)
        await self.db.commit()

    async def list_project_papers(
        self,
        *,
        project_id: str,
        user_id: str,
        role: str | None,
    ) -> dict[str, Any]:
        await self.get_owned_project(project_id, user_id)
        stmt = (
            select(ProjectPaper, Paper)
            .join(Paper, Paper.id == ProjectPaper.paper_id)
            .where(ProjectPaper.project_id == project_id)
            .order_by(ProjectPaper.reading_priority.desc(), ProjectPaper.added_at.desc())
        )
        if role:
            stmt = stmt.where(ProjectPaper.role == role)
        rows = (await self.db.execute(stmt)).all()
        items = []
        for project_paper, paper in rows:
            item = project_paper.to_dict()
            item["paper"] = {
                "id": paper.id,
                "title": paper.title,
                "authors": paper.authors,
                "abstract": (paper.abstract or "")[:300],
                "keywords": paper.keywords or [],
                "publication_year": paper.publication_year,
                "venue": paper.venue,
                "doi": paper.doi,
                "reading_progress": paper.reading_progress,
            }
            items.append(item)
        return {"items": items, "total": len(items)}

    async def add_project_paper(
        self,
        *,
        project_id: str,
        user_id: str,
        paper_id: str,
        role: str,
        tags: list[str],
        notes: str,
        reading_priority: int,
    ) -> dict[str, Any]:
        await self.get_owned_project(project_id, user_id)
        paper = await self.db.get(Paper, paper_id)
        if paper is None or paper.user_id != user_id:
            raise PaperNotFoundError(paper_id)
        existing = (
            await self.db.execute(
                select(ProjectPaper).where(
                    ProjectPaper.project_id == project_id,
                    ProjectPaper.paper_id == paper_id,
                )
            )
        ).scalars().first()
        if existing:
            existing.role = role
            existing.tags = tags
            existing.notes = notes
            existing.reading_priority = reading_priority
            action = "updated"
            project_paper = existing
        else:
            project_paper = ProjectPaper(
                project_id=project_id,
                paper_id=paper_id,
                role=role,
                tags=tags,
                notes=notes,
                reading_priority=reading_priority,
            )
            self.db.add(project_paper)
            action = "created"
        await self.db.commit()
        await self.db.refresh(project_paper)
        if action == "created" or not (project_paper.analysis_card or {}).get("paper_profile"):
            from app.research.context.paper_profile import (
                PaperProfileNotReadyError,
                PaperProfileService,
            )

            try:
                await PaperProfileService(self.db).request_generation(
                    project_id=project_id,
                    paper_id=paper_id,
                    user_id=user_id,
                )
                await self.db.refresh(project_paper)
            except PaperProfileNotReadyError:
                logger.info("Project Paper 尚未完成解析，暂不生成 Profile paper_id=%s", paper_id)
            except Exception:
                # Profile is an enhancement; membership and Reader availability
                # must survive queue/configuration failures.
                logger.exception("Project Paper Profile 调度失败 paper_id=%s", paper_id)
        return {**project_paper.to_dict(), "_action": action}
