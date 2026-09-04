"""Stable, bounded DTOs for project-level context.

These DTOs deliberately contain structured values rather than a prompt string.
Prompt formatting remains a concern of the caller that owns the use case.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# These are the only MemoryItem types that the V1 discovery context treats as
# durable Literature Memory. Existing research-note types remain available to
# the compatibility API, but are not silently promoted into agent context.
DISCOVERY_MEMORY_TYPES = frozenset(
    {
        "project_decision",
        "literature_intent",
        "literature_preference",
        "literature_exclusion",
    }
)


def _unique_terms(values: list[Any], *, limit: int, max_length: int = 200) -> list[str]:
    result: list[str] = []
    for value in values[:limit]:
        if not isinstance(value, str):
            continue
        term = value.strip()[:max_length]
        if term and term not in result:
            result.append(term)
    return result


class ProjectProfileContext(BaseModel):
    """The stable answer to “what is this project researching?”"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=300)
    research_topic: str = Field(min_length=1, max_length=300)
    field: str = Field(default="", max_length=200)
    research_subject: str = Field(default="", max_length=500)
    research_question: str = Field(default="", max_length=2_000)
    research_goal: str = Field(default="", max_length=2_000)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    method_direction: str = Field(default="", max_length=1_000)
    user_notes: str = Field(default="", max_length=4_000)
    updated_at: datetime | None = None

    _list_limit: ClassVar[int] = 30

    @field_validator("title", "research_topic", "field", "research_subject", "research_question", "research_goal", "method_direction", "user_notes", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, value: Any) -> list[str]:
        return _unique_terms(value if isinstance(value, list) else [], limit=cls._list_limit, max_length=100)


class LiteratureMemoryContext(BaseModel):
    """Bounded, durable discovery memory; never raw search history or reasoning."""

    model_config = ConfigDict(extra="forbid")

    search_intent_summary: str = Field(default="", max_length=2_000)
    important_keywords: list[str] = Field(default_factory=list, max_length=30)
    preferred_directions: list[str] = Field(default_factory=list, max_length=12)
    excluded_directions: list[str] = Field(default_factory=list, max_length=12)
    important_search_notes: list[str] = Field(default_factory=list, max_length=12)
    favorite_paper_ids: list[str] = Field(default_factory=list, max_length=200)
    imported_paper_ids: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("search_intent_summary", mode="before")
    @classmethod
    def normalize_summary(cls, value: Any) -> str:
        return str(value or "").strip()[:2_000]

    @field_validator(
        "important_keywords",
        "preferred_directions",
        "excluded_directions",
        "important_search_notes",
        "favorite_paper_ids",
        "imported_paper_ids",
        mode="before",
    )
    @classmethod
    def normalize_lists(cls, value: Any, info: Any) -> list[str]:
        values = value if isinstance(value, list) else []
        limit = 200 if info.field_name in {"favorite_paper_ids", "imported_paper_ids"} else 30
        max_length = 2000 if info.field_name == "important_search_notes" else 512
        return _unique_terms(values, limit=limit, max_length=max_length)


class DiscoveryContext(BaseModel):
    """The context contract consumed by the Literature Discovery workflow."""

    model_config = ConfigDict(extra="forbid")

    project_profile: ProjectProfileContext
    literature_memory: LiteratureMemoryContext


class CandidatePaperContext(BaseModel):
    """One project-owned paper selected from its ready Paper Profile."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    paper_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=500)
    authors: str = Field(default="", max_length=2_000)
    publication_year: int | None = None
    doi: str = Field(default="", max_length=200)
    role: str = Field(default="related", max_length=30)
    profile_status: Literal["ready", "stale"]
    profile_version: int = Field(ge=1)
    topic: str = Field(default="", max_length=2_000)
    methods: list[str] = Field(default_factory=list, max_length=12)
    main_results: list[str] = Field(default_factory=list, max_length=12)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    project_relevance: str = Field(default="", max_length=2_000)
    selection_score: float = Field(ge=0)


class CandidateSelectionResult(BaseModel):
    """Bounded shortlist plus enough state to report empty-project conditions."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[CandidatePaperContext] = Field(default_factory=list, max_length=5)
    imported_paper_count: int = Field(default=0, ge=0)
    ready_profile_count: int = Field(default=0, ge=0)


class EvidenceCandidateContext(BaseModel):
    """Transient, source-traceable evidence returned by restricted retrieval."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    paper_id: str = Field(min_length=1, max_length=36)
    chunk_id: str = Field(min_length=1, max_length=200)
    snippet: str = Field(min_length=1, max_length=2_000)
    section_id: str | None = Field(default=None, max_length=36)
    section_title: str = Field(default="", max_length=500)
    page_number: int | None = Field(default=None, ge=1)
    element_id: str | None = Field(default=None, max_length=100)
    bbox: list[Any] | dict[str, Any] | None = None
    paper_title: str = Field(min_length=1, max_length=500)
    paper_authors: str = Field(default="", max_length=2_000)
    publication_year: int | None = None
    doi: str = Field(default="", max_length=200)
    retrieval_score: float = Field(default=0, ge=0)
    retrieval_method: str = Field(default="hybrid", max_length=80)
    source_type: Literal["retrieval_generated"] = "retrieval_generated"
    verification_status: Literal["unverified"] = "unverified"


class WritingRetrievalContext(BaseModel):
    """Temporary context for one writing retrieval request, never long-term memory."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "no_imported_papers", "no_ready_profiles", "no_supporting_evidence"]
    project_profile: ProjectProfileContext
    document_id: str | None = Field(default=None, max_length=36)
    instruction: str = Field(min_length=1, max_length=20_000)
    current_section_title: str = Field(default="", max_length=500)
    current_section_path: list[str] = Field(default_factory=list, max_length=20)
    selection: str = Field(default="", max_length=12_000)
    nearby_text: str = Field(default="", max_length=12_000)
    candidate_papers: list[CandidatePaperContext] = Field(default_factory=list, max_length=5)
    evidence: list[EvidenceCandidateContext] = Field(default_factory=list, max_length=20)
