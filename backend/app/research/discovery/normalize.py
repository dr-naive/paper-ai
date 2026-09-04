"""Deterministic normalization and metadata-preserving deduplication."""
from __future__ import annotations

import hashlib
import re
import unicodedata

from .schemas import PaperSearchResultDTO, ProviderPaperDTO


_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_TITLE_SEPARATORS = re.compile(r"[^\w]+", re.UNICODE)


def normalize_doi(value: str | None) -> str | None:
    normalized = _DOI_PREFIX.sub("", str(value or "").strip()).strip().rstrip(".,;")
    return normalized.casefold() or None


def normalized_title(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    return _TITLE_SEPARATORS.sub(" ", text).strip()


def normalize_provider_paper(
    provider_name: str,
    paper: ProviderPaperDTO,
) -> PaperSearchResultDTO:
    """Create the V1 result shape without truncating provider abstracts."""

    source = provider_name.strip().casefold()
    source_id = paper.source_paper_id.strip()
    result_id = hashlib.sha256(f"{source}:{source_id}".encode("utf-8")).hexdigest()[:32]
    pdf_url = paper.pdf_url
    return PaperSearchResultDTO(
        result_id=result_id,
        source=source,
        source_paper_id=source_id,
        title=paper.title,
        authors=paper.authors,
        year=paper.year,
        venue=paper.venue,
        abstract=paper.abstract,
        doi=normalize_doi(paper.doi),
        paper_url=paper.paper_url,
        pdf_url=pdf_url,
        language=paper.language,
        publication_type=paper.publication_type,
        fields=paper.fields,
        citation_count=paper.citation_count,
        open_access=paper.open_access,
        download_available=bool(pdf_url),
        import_available=source == "arxiv" and bool(pdf_url),
    )


def deduplicate_results(results: list[PaperSearchResultDTO]) -> list[PaperSearchResultDTO]:
    """Merge duplicates by DOI, stable provider ID, then normalized title plus year."""

    merged: list[PaperSearchResultDTO] = []
    for candidate in results:
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(merged)
                if _is_duplicate(existing, candidate)
            ),
            None,
        )
        if duplicate_index is None:
            merged.append(candidate)
        else:
            merged[duplicate_index] = _merge_results(merged[duplicate_index], candidate)
    return merged


def _is_duplicate(left: PaperSearchResultDTO, right: PaperSearchResultDTO) -> bool:
    left_doi, right_doi = normalize_doi(left.doi), normalize_doi(right.doi)
    if left_doi and right_doi and left_doi == right_doi:
        return True
    if left.source == right.source and left.source_paper_id == right.source_paper_id:
        return True
    return bool(
        left.year == right.year
        and left.year is not None
        and normalized_title(left.title) == normalized_title(right.title)
    )


def _merge_results(left: PaperSearchResultDTO, right: PaperSearchResultDTO) -> PaperSearchResultDTO:
    primary, secondary = (left, right) if _completeness(left) >= _completeness(right) else (right, left)
    return PaperSearchResultDTO(
        result_id=primary.result_id,
        source=primary.source,
        source_paper_id=primary.source_paper_id,
        title=_prefer_text(primary.title, secondary.title) or primary.title,
        authors=_prefer_list(primary.authors, secondary.authors),
        year=primary.year if primary.year is not None else secondary.year,
        venue=_prefer_text(primary.venue, secondary.venue),
        abstract=_prefer_abstract(primary.abstract, secondary.abstract),
        doi=normalize_doi(primary.doi) or normalize_doi(secondary.doi),
        paper_url=_prefer_text(primary.paper_url, secondary.paper_url),
        pdf_url=_prefer_text(primary.pdf_url, secondary.pdf_url),
        language=_prefer_text(primary.language, secondary.language),
        publication_type=_prefer_text(primary.publication_type, secondary.publication_type),
        fields=_prefer_list(primary.fields, secondary.fields),
        citation_count=_prefer_count(primary.citation_count, secondary.citation_count),
        open_access=True if primary.open_access or secondary.open_access else primary.open_access if primary.open_access is not None else secondary.open_access,
        recommendation_reason=_prefer_text(primary.recommendation_reason, secondary.recommendation_reason),
        is_favorite=primary.is_favorite or secondary.is_favorite,
        download_available=bool(primary.pdf_url or secondary.pdf_url),
        import_available=primary.import_available or secondary.import_available,
    )


def _completeness(result: PaperSearchResultDTO) -> int:
    values = (
        result.abstract,
        result.doi,
        result.pdf_url,
        result.paper_url,
        result.venue,
        result.citation_count,
    )
    return sum(value is not None and value != "" for value in values) + min(len(result.abstract or ""), 10_000) // 1_000


def _prefer_text(primary: str | None, secondary: str | None) -> str | None:
    return primary or secondary


def _prefer_abstract(primary: str | None, secondary: str | None) -> str | None:
    return max((value for value in (primary, secondary) if value), key=len, default=None)


def _prefer_list(primary: list[str], secondary: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in [*primary, *secondary]:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _prefer_count(primary: int | None, secondary: int | None) -> int | None:
    return max((value for value in (primary, secondary) if value is not None), default=None)
