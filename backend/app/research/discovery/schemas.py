"""Stable DTOs shared by academic-search providers and discovery workflows."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SearchText = Annotated[str, Field(min_length=1, max_length=2_000)]


class SearchIntentDTO(BaseModel):
    """Structured intent. Block 2A defines the contract; planning arrives in Block 2B."""

    topic: SearchText
    research_question: str | None = Field(default=None, max_length=2_000)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    preferred_methods: list[str] = Field(default_factory=list, max_length=20)
    target_contexts: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("keywords", "preferred_methods", "target_contexts")
    @classmethod
    def normalize_terms(cls, values: list[str]) -> list[str]:
        return _unique_terms(values)


class SearchFiltersDTO(BaseModel):
    """Deterministic filters, mapped only when the selected provider supports them."""

    year_from: int | None = Field(default=None, ge=1800, le=2200)
    year_to: int | None = Field(default=None, ge=1800, le=2200)
    language: str | None = Field(default=None, min_length=2, max_length=32)
    fields: list[str] = Field(default_factory=list, max_length=10)
    publication_types: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        normalized = str(value or "").strip().lower()
        return normalized or None

    @field_validator("fields", "publication_types")
    @classmethod
    def normalize_filter_terms(cls, values: list[str]) -> list[str]:
        return _unique_terms(values)

    @model_validator(mode="after")
    def validate_year_range(self) -> "SearchFiltersDTO":
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("year_from 不能晚于 year_to")
        return self


class LiteratureSearchRequest(BaseModel):
    project_id: str = Field(min_length=1)
    intent: SearchIntentDTO
    filters: SearchFiltersDTO = Field(default_factory=SearchFiltersDTO)
    max_results: int = Field(default=10, ge=1, le=10)


class DiscoverySearchRequest(BaseModel):
    """Path-scoped request for the Block 2B discovery endpoint."""

    intent: SearchIntentDTO
    filters: SearchFiltersDTO = Field(default_factory=SearchFiltersDTO)
    max_results: int = Field(default=10, ge=1, le=10)


class DiscoveryFavoriteRequest(BaseModel):
    """Validated metadata snapshot for one project-scoped discovery favorite."""

    model_config = ConfigDict(extra="forbid")

    result_id: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=128)
    source_paper_id: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=4_000)
    authors: list[str] = Field(default_factory=list, max_length=50)
    year: int | None = Field(default=None, ge=1800, le=2200)
    venue: str | None = Field(default=None, max_length=1_000)
    abstract: str | None = Field(default=None, max_length=20_000)
    doi: str | None = Field(default=None, max_length=1_000)
    paper_url: str | None = Field(default=None, max_length=4_000)
    pdf_url: str | None = Field(default=None, max_length=4_000)
    language: str | None = Field(default=None, max_length=32)
    publication_type: str | None = Field(default=None, max_length=128)
    fields: list[str] = Field(default_factory=list, max_length=30)
    citation_count: int | None = Field(default=None, ge=0)
    open_access: bool | None = None

    @field_validator("source", "source_paper_id", "title", "venue", "doi", "paper_url", "pdf_url", "language", "publication_type", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("authors", "fields")
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        return _unique_terms(values)


class DiscoveryFavoriteResponse(DiscoveryFavoriteRequest):
    favorite_id: str = Field(min_length=1, max_length=128)
    saved_at: str = Field(min_length=1, max_length=64)
    download_available: bool = False
    import_available: bool = False


class DiscoveryImportRequest(BaseModel):
    """Import only a validated approved source identifier, never an arbitrary URL."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["arxiv"]
    source_paper_id: str = Field(min_length=5, max_length=80)
    approved_pdf_locator: str | None = Field(default=None, min_length=5, max_length=512)
    result_id: str | None = Field(default=None, min_length=1, max_length=128)
    role: Literal["core", "related", "background"] = "related"
    tags: list[str] = Field(default_factory=list, max_length=30)
    notes: str = Field(default="", max_length=2_000)
    reading_priority: int = Field(default=3, ge=1, le=5)

    @field_validator("source_paper_id", "approved_pdf_locator", "result_id", "notes", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        return _unique_terms(values)

    @model_validator(mode="after")
    def require_approved_locator_or_result(self) -> "DiscoveryImportRequest":
        if not self.approved_pdf_locator and not self.result_id:
            raise ValueError("必须提供 approved_pdf_locator 或 result_id")
        return self


class DiscoveryImportResponse(BaseModel):
    source: Literal["arxiv"]
    source_paper_id: str
    status: Literal["queued", "processing", "imported", "failed"]
    message: str
    task_id: str | None = None
    paper_id: str | None = None


class SearchPlanDTO(BaseModel):
    queries: list[SearchText] = Field(min_length=1, max_length=3)
    rationale_summary: str | None = Field(default=None, max_length=2_000)

    @field_validator("queries")
    @classmethod
    def normalize_queries(cls, values: list[str]) -> list[str]:
        return _unique_terms(values)


class ProviderCapabilities(BaseModel):
    supports_year: bool
    supports_language: bool
    supports_field: bool
    supports_publication_type: bool
    returns_abstract: bool
    returns_pdf_url: bool
    returns_citation_count: bool


class ProviderPaperDTO(BaseModel):
    """Provider-specific response normalized to a fixed internal record shape."""

    source_paper_id: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=4_000)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1800, le=2200)
    venue: str | None = Field(default=None, max_length=1_000)
    abstract: str | None = None
    doi: str | None = Field(default=None, max_length=1_000)
    paper_url: str | None = Field(default=None, max_length=4_000)
    pdf_url: str | None = Field(default=None, max_length=4_000)
    language: str | None = Field(default=None, max_length=32)
    publication_type: str | None = Field(default=None, max_length=128)
    fields: list[str] = Field(default_factory=list)
    citation_count: int | None = Field(default=None, ge=0)
    open_access: bool | None = None

    @field_validator("authors", "fields")
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        return _unique_terms(values)

    @field_validator("abstract", mode="before")
    @classmethod
    def preserve_abstract(cls, value: object) -> str | None:
        text = str(value) if value is not None else ""
        return text or None

    @field_validator("doi", "paper_url", "pdf_url", "language", "publication_type", "venue", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None


class PaperSearchResultDTO(ProviderPaperDTO):
    """Stable, frontend-facing result record. User state arrives in Block 2C."""

    result_id: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=128)
    recommendation_reason: str | None = Field(default=None, max_length=2_000)
    is_favorite: bool = False
    download_available: bool = False
    import_available: bool = False


class LiteratureSearchResponse(BaseModel):
    """Final bounded workflow response and its user-readable execution summary."""

    execution_id: str = Field(min_length=1, max_length=128)
    papers: list[PaperSearchResultDTO] = Field(default_factory=list, max_length=10)
    provider: str
    result_count: int = Field(ge=0, le=10)
    search_rounds: int = Field(ge=1, le=3)
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @property
    def items(self) -> list[PaperSearchResultDTO]:
        """Compatibility accessor for callers that used the early Block 2A shape."""
        return self.papers


def _unique_terms(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        term = str(value or "").strip()
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            normalized.append(term)
    return normalized
