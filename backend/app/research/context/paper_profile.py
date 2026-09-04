"""Stable Paper Profile persistence and lifecycle on ProjectPaper.analysis_card."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.job_queue import enqueue_job
from app.models.paper import Paper, Section
from app.models.project import ProjectPaper, ResearchProject

logger = logging.getLogger(__name__)

PAPER_PROFILE_CARD_KEY = "paper_profile"
PAPER_PROFILE_SCHEMA_NAME = "paper_profile"
PAPER_PROFILE_VERSION = 1
PAPER_PROFILE_GENERATOR_VERSION = "1.0"
PAPER_PROFILE_STATUSES = {"pending", "generating", "ready", "failed", "stale"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _unique_text(values: Any, *, limit: int = 30, max_length: int = 1_000) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for raw in values[:limit]:
        if not isinstance(raw, str):
            continue
        value = raw.strip()[:max_length]
        if value and value not in result:
            result.append(value)
    return result


class PaperProfileContent(BaseModel):
    """Model-produced academic content; missing information stays empty."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(default="", max_length=2_000)
    research_questions: list[str] = Field(default_factory=list, max_length=20)
    research_subjects: list[str] = Field(default_factory=list, max_length=20)
    methods: list[str] = Field(default_factory=list, max_length=30)
    datasets_or_samples: list[str] = Field(default_factory=list, max_length=30)
    main_results: list[str] = Field(default_factory=list, max_length=30)
    conclusions: list[str] = Field(default_factory=list, max_length=20)
    contributions: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    project_relevance: str = Field(default="", max_length=2_000)

    @field_validator("topic", "project_relevance", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator(
        "research_questions",
        "research_subjects",
        "methods",
        "datasets_or_samples",
        "main_results",
        "conclusions",
        "contributions",
        "limitations",
        "keywords",
        mode="before",
    )
    @classmethod
    def normalize_lists(cls, value: Any) -> list[str]:
        return _unique_text(value)


class PaperProfile(PaperProfileContent):
    """Persisted, versioned profile state stored inside analysis_card."""

    schema_name: Literal["paper_profile"] = PAPER_PROFILE_SCHEMA_NAME
    profile_version: int = PAPER_PROFILE_VERSION
    generator_version: str = PAPER_PROFILE_GENERATOR_VERSION
    status: Literal["pending", "generating", "ready", "failed", "stale"]
    project_id: str = Field(min_length=1, max_length=36)
    paper_id: str = Field(min_length=1, max_length=36)
    source_model: str = Field(default="", max_length=200)
    source_fingerprint: str = Field(min_length=64, max_length=64)
    generated_at: str | None = Field(default=None, max_length=64)
    updated_at: str = Field(default_factory=_now_iso, max_length=64)
    retry_count: int = Field(default=0, ge=0, le=100)
    error_code: str | None = Field(default=None, max_length=100)
    error_message: str | None = Field(default=None, max_length=500)


class PaperProfileNotFoundError(LookupError):
    """The project, paper, or membership is absent or not owned."""


class PaperProfileNotReadyError(RuntimeError):
    """The paper has not completed enough parsing to build a profile."""


@dataclass(slots=True)
class PaperProfileBundle:
    project: ResearchProject
    project_paper: ProjectPaper
    paper: Paper
    sections: list[Section]


def read_paper_profile(analysis_card: Any) -> PaperProfile | None:
    if not isinstance(analysis_card, dict):
        return None
    raw = analysis_card.get(PAPER_PROFILE_CARD_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        return PaperProfile.model_validate(raw)
    except Exception:
        return None


def write_paper_profile(project_paper: ProjectPaper, profile: PaperProfile) -> None:
    card = dict(project_paper.analysis_card or {})
    card[PAPER_PROFILE_CARD_KEY] = profile.model_dump(mode="json")
    project_paper.analysis_card = card


def paper_source_fingerprint(paper: Paper, sections: list[Section]) -> str:
    """Hash parse identity without persisting or prompting with the full paper."""
    section_signatures = []
    for section in sections:
        content = str(section.content or "")
        section_signatures.append(
            {
                "id": str(section.id or ""),
                "title": str(section.section_title or ""),
                "order": int(section.order_index or 0),
                "length": len(content),
                "head": content[:256],
                "tail": content[-256:] if content else "",
                "created_at": section.created_at.isoformat() if section.created_at else "",
            }
        )
    payload = {
        "paper_id": str(paper.id),
        "title": str(paper.title or ""),
        "abstract": str(paper.abstract or ""),
        "updated_at": paper.updated_at.isoformat() if paper.updated_at else "",
        "full_text_length": len(str(paper.full_text or "")),
        "sections": section_signatures,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def paper_profile_is_stale(profile: PaperProfile, source_fingerprint: str) -> bool:
    generator_major = str(profile.generator_version or "").split(".", 1)[0]
    current_major = PAPER_PROFILE_GENERATOR_VERSION.split(".", 1)[0]
    return (
        profile.profile_version != PAPER_PROFILE_VERSION
        or generator_major != current_major
        or profile.source_fingerprint != source_fingerprint
    )


def _blank_profile(
    *,
    project_id: str,
    paper_id: str,
    source_fingerprint: str,
    status: Literal["pending", "generating", "ready", "failed", "stale"],
    retry_count: int = 0,
) -> PaperProfile:
    return PaperProfile(
        project_id=project_id,
        paper_id=paper_id,
        source_fingerprint=source_fingerprint,
        status=status,
        retry_count=retry_count,
    )


class PaperProfileService:
    """Own profile authorization, state transitions, queueing, and generation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_bundle(
        self,
        project_id: str,
        paper_id: str,
        user_id: str | None = None,
    ) -> PaperProfileBundle:
        project = await self.db.get(ResearchProject, project_id)
        if project is None or (user_id and project.user_id != user_id):
            raise PaperProfileNotFoundError(project_id)
        project_paper = (
            await self.db.execute(
                select(ProjectPaper).where(
                    ProjectPaper.project_id == project_id,
                    ProjectPaper.paper_id == paper_id,
                )
            )
        ).scalars().first()
        paper = await self.db.get(Paper, paper_id)
        if project_paper is None or paper is None or paper.user_id != project.user_id:
            raise PaperProfileNotFoundError(paper_id)
        sections = list(
            (
                await self.db.execute(
                    select(Section)
                    .where(Section.paper_id == paper_id)
                    .order_by(Section.order_index)
                )
            ).scalars().all()
        )
        return PaperProfileBundle(project, project_paper, paper, sections)

    @staticmethod
    def _parsed(bundle: PaperProfileBundle) -> bool:
        return bool(bundle.sections or str(bundle.paper.full_text or "").strip())

    async def get_profile(
        self,
        *,
        project_id: str,
        paper_id: str,
        user_id: str,
    ) -> PaperProfile | None:
        bundle = await self._load_bundle(project_id, paper_id, user_id)
        profile = read_paper_profile(bundle.project_paper.analysis_card)
        if profile is None:
            return None
        fingerprint = paper_source_fingerprint(bundle.paper, bundle.sections)
        if profile.status == "ready" and paper_profile_is_stale(profile, fingerprint):
            profile = profile.model_copy(
                update={
                    "status": "stale",
                    "updated_at": _now_iso(),
                    "error_code": "PROFILE_SOURCE_CHANGED",
                    "error_message": "论文解析内容或 Profile 版本已变化，需要重新生成",
                }
            )
            write_paper_profile(bundle.project_paper, profile)
            await self.db.commit()
        return profile

    async def request_generation(
        self,
        *,
        project_id: str,
        paper_id: str,
        user_id: str | None = None,
        force: bool = False,
    ) -> PaperProfile:
        bundle = await self._load_bundle(project_id, paper_id, user_id)
        if not self._parsed(bundle):
            raise PaperProfileNotReadyError(paper_id)
        fingerprint = paper_source_fingerprint(bundle.paper, bundle.sections)
        current = read_paper_profile(bundle.project_paper.analysis_card)
        if current and current.status in {"pending", "generating"} and current.source_fingerprint == fingerprint:
            return current
        if current and current.status == "ready" and not paper_profile_is_stale(current, fingerprint) and not force:
            return current

        retry_count = current.retry_count if current else 0
        if current and (force or current.status in {"failed", "stale"}):
            retry_count += 1
        pending = _blank_profile(
            project_id=project_id,
            paper_id=paper_id,
            source_fingerprint=fingerprint,
            status="pending",
            retry_count=retry_count,
        )
        write_paper_profile(bundle.project_paper, pending)
        await self.db.commit()
        try:
            await enqueue_job(
                "paper_profile",
                {
                    "project_id": project_id,
                    "paper_id": paper_id,
                    "source_fingerprint": fingerprint,
                },
                job_id=f"paper-profile-{project_id}-{paper_id}-{fingerprint[:12]}",
            )
        except Exception as exc:
            logger.exception("Paper Profile 入队失败 project_id=%s paper_id=%s", project_id, paper_id)
            failed = pending.model_copy(
                update={
                    "status": "failed",
                    "updated_at": _now_iso(),
                    "error_code": "PROFILE_QUEUE_UNAVAILABLE",
                    "error_message": type(exc).__name__,
                }
            )
            write_paper_profile(bundle.project_paper, failed)
            await self.db.commit()
            return failed
        return pending

    async def run_generation(
        self,
        *,
        project_id: str,
        paper_id: str,
        expected_fingerprint: str,
    ) -> PaperProfile:
        bundle = await self._load_bundle(project_id, paper_id)
        current = read_paper_profile(bundle.project_paper.analysis_card)
        fingerprint = paper_source_fingerprint(bundle.paper, bundle.sections)
        if current is None:
            current = _blank_profile(
                project_id=project_id,
                paper_id=paper_id,
                source_fingerprint=fingerprint,
                status="pending",
            )
        if expected_fingerprint != fingerprint:
            stale = current.model_copy(
                update={
                    "status": "stale",
                    "source_fingerprint": fingerprint,
                    "updated_at": _now_iso(),
                    "error_code": "PROFILE_SOURCE_CHANGED",
                    "error_message": "生成前检测到论文解析内容变化",
                }
            )
            write_paper_profile(bundle.project_paper, stale)
            await self.db.commit()
            return await self.request_generation(
                project_id=project_id,
                paper_id=paper_id,
                user_id=bundle.project.user_id,
                force=True,
            )

        generating = current.model_copy(
            update={
                "status": "generating",
                "updated_at": _now_iso(),
                "error_code": None,
                "error_message": None,
            }
        )
        write_paper_profile(bundle.project_paper, generating)
        await self.db.commit()

        try:
            from .paper_profile_generator import PaperProfileGenerator

            generator = PaperProfileGenerator()
            content = await generator.generate(bundle.project, bundle.paper, bundle.sections)
            ready = PaperProfile(
                **content.model_dump(),
                project_id=project_id,
                paper_id=paper_id,
                status="ready",
                source_model=generator.source_model,
                source_fingerprint=fingerprint,
                generated_at=_now_iso(),
                updated_at=_now_iso(),
                retry_count=generating.retry_count,
            )
            write_paper_profile(bundle.project_paper, ready)
            await self.db.commit()
            return ready
        except Exception as exc:
            logger.exception("Paper Profile 生成失败 project_id=%s paper_id=%s", project_id, paper_id)
            failed = generating.model_copy(
                update={
                    "status": "failed",
                    "updated_at": _now_iso(),
                    "error_code": "PROFILE_GENERATION_FAILED",
                    "error_message": type(exc).__name__,
                }
            )
            write_paper_profile(bundle.project_paper, failed)
            await self.db.commit()
            return failed


async def schedule_profiles_for_parsed_paper(
    db: AsyncSession,
    paper_id: str,
    *,
    force: bool = False,
) -> list[PaperProfile]:
    """Schedule every current project membership after parse/index completion."""
    paper = await db.get(Paper, paper_id)
    if paper is None:
        return []
    memberships = list(
        (
            await db.execute(select(ProjectPaper).where(ProjectPaper.paper_id == paper_id))
        ).scalars().all()
    )
    results: list[PaperProfile] = []
    service = PaperProfileService(db)
    for membership in memberships:
        try:
            results.append(
                await service.request_generation(
                    project_id=str(membership.project_id),
                    paper_id=paper_id,
                    user_id=str(paper.user_id),
                    force=force,
                )
            )
        except PaperProfileNotReadyError:
            logger.info("跳过未完成解析的 Paper Profile paper_id=%s", paper_id)
    return results
