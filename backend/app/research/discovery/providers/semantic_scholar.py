"""Semantic Scholar Academic Graph adapter for one atomic paper search."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.config import settings

from ..schemas import ProviderCapabilities, ProviderPaperDTO, SearchFiltersDTO
from .base import (
    AcademicSearchAuthenticationError,
    AcademicSearchMalformedResponseError,
    AcademicSearchProviderError,
    AcademicSearchRateLimitError,
    AcademicSearchTimeoutError,
)


S2_PAPER_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = ",".join(
    [
        "title",
        "authors",
        "year",
        "venue",
        "abstract",
        "externalIds",
        "url",
        "openAccessPdf",
        "fieldsOfStudy",
        "publicationTypes",
        "citationCount",
    ]
)

_FIELD_FILTERS = {
    "computer_science": "Computer Science",
    "medicine": "Medicine",
    "biology": "Biology",
    "chemistry": "Chemistry",
    "physics": "Physics",
    "mathematics": "Mathematics",
    "engineering": "Engineering",
    "materials_science": "Materials Science",
    "psychology": "Psychology",
    "economics": "Economics",
}
_PUBLICATION_TYPE_FILTERS = {
    "journal_article": "JournalArticle",
    "conference_paper": "Conference",
    "review": "Review",
    "meta_analysis": "MetaAnalysis",
    "clinical_trial": "ClinicalTrial",
    "editorial": "Editorial",
}


class SemanticScholarAcademicSearchProvider:
    name = "semantic_scholar"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        endpoint: str = S2_PAPER_SEARCH_URL,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.SEMANTIC_SCHOLAR_API_KEY
        self._timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.SEARCH_TIMEOUT_SECONDS
        self._max_retries = max_retries if max_retries is not None else settings.SEARCH_MAX_RETRIES
        self._client = client
        self._sleep = sleep
        self._endpoint = endpoint

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_year=True,
            supports_language=False,
            supports_field=True,
            supports_publication_type=True,
            returns_abstract=True,
            returns_pdf_url=True,
            returns_citation_count=True,
        )

    def build_search_params(self, query: str, filters: SearchFiltersDTO, limit: int) -> dict[str, str | int]:
        if not query.strip():
            raise ValueError("query 不能为空")
        if not 1 <= limit <= settings.SEARCH_RESULT_LIMIT:
            raise ValueError(f"limit 必须在 1 到 {settings.SEARCH_RESULT_LIMIT} 之间")

        params: dict[str, str | int] = {
            "query": query.strip(),
            "limit": limit,
            "fields": S2_FIELDS,
        }
        if filters.year_from is not None or filters.year_to is not None:
            params["year"] = _year_filter(filters.year_from, filters.year_to)
        if filters.fields:
            params["fieldsOfStudy"] = ",".join(_map_fields(filters.fields))
        if filters.publication_types:
            params["publicationTypes"] = ",".join(_map_publication_types(filters.publication_types))
        return params

    async def search(
        self,
        query: str,
        filters: SearchFiltersDTO,
        limit: int,
    ) -> list[ProviderPaperDTO]:
        response = await self._get(self.build_search_params(query, filters, limit))
        try:
            payload = response.json()
        except ValueError as exc:
            raise AcademicSearchMalformedResponseError("Semantic Scholar 返回了无效 JSON") from exc
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise AcademicSearchMalformedResponseError("Semantic Scholar 响应缺少 data 数组")
        papers: list[ProviderPaperDTO] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            paper = _parse_paper(row)
            if paper is not None:
                papers.append(paper)
        return papers

    async def _get(self, params: dict[str, str | int]) -> httpx.Response:
        headers = {"User-Agent": "PaperAI/1.0 academic-search"}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        if self._client is not None:
            return await self._request_with_retry(self._client, params, headers)
        timeout = httpx.Timeout(self._timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await self._request_with_retry(client, params, headers)

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        params: dict[str, str | int],
        headers: dict[str, str],
    ) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = await client.get(self._endpoint, params=params, headers=headers)
            except httpx.TimeoutException as exc:
                if attempt < self._max_retries:
                    await self._sleep(2**attempt)
                    continue
                raise AcademicSearchTimeoutError("Semantic Scholar 请求超时") from exc
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    await self._sleep(2**attempt)
                    continue
                raise AcademicSearchProviderError("Semantic Scholar 连接失败") from exc

            if response.status_code in {401, 403}:
                raise AcademicSearchAuthenticationError("Semantic Scholar 拒绝访问")
            if response.status_code == 429:
                raise AcademicSearchRateLimitError(
                    "Semantic Scholar 请求超过速率限制",
                    retry_after_seconds=_retry_after_seconds(response.headers.get("Retry-After")),
                )
            if 500 <= response.status_code < 600 and attempt < self._max_retries:
                await self._sleep(2**attempt)
                continue
            if response.is_error:
                raise AcademicSearchProviderError(f"Semantic Scholar 请求失败: HTTP {response.status_code}")
            return response
        raise AcademicSearchProviderError("Semantic Scholar 请求失败")


def _year_filter(year_from: int | None, year_to: int | None) -> str:
    if year_from is not None and year_to is not None:
        return f"{year_from}-{year_to}"
    if year_from is not None:
        return f"{year_from}-"
    return f"-{year_to}"


def _map_fields(values: list[str]) -> list[str]:
    return [_FIELD_FILTERS.get(value.strip().casefold(), value.strip()) for value in values if value.strip()]


def _map_publication_types(values: list[str]) -> list[str]:
    return [_PUBLICATION_TYPE_FILTERS.get(value.strip().casefold(), value.strip()) for value in values if value.strip()]


def _parse_paper(row: dict[str, Any]) -> ProviderPaperDTO | None:
    paper_id = str(row.get("paperId") or "").strip()
    title = str(row.get("title") or "").strip()
    if not paper_id or not title:
        return None
    external_ids = row.get("externalIds") if isinstance(row.get("externalIds"), dict) else {}
    open_access_pdf = row.get("openAccessPdf") if isinstance(row.get("openAccessPdf"), dict) else {}
    publication_types = row.get("publicationTypes") or []
    fields = row.get("fieldsOfStudy") or []
    return ProviderPaperDTO(
        source_paper_id=paper_id,
        title=title,
        authors=[str(author.get("name") or "").strip() for author in row.get("authors") or [] if isinstance(author, dict) and author.get("name")],
        year=_as_year(row.get("year")),
        venue=_as_text(row.get("venue")),
        abstract=_as_abstract(row.get("abstract")),
        doi=_as_text(external_ids.get("DOI") or external_ids.get("doi")),
        paper_url=_as_text(row.get("url")),
        pdf_url=_as_text(open_access_pdf.get("url")),
        publication_type=_as_text(publication_types[0]) if publication_types else None,
        fields=[str(field).strip() for field in fields if str(field).strip()],
        citation_count=_as_non_negative_int(row.get("citationCount")),
        open_access=bool(open_access_pdf.get("url")) if open_access_pdf else None,
    )


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        try:
            return max((parsedate_to_datetime(value).timestamp() - time.time()), 0.0)
        except (TypeError, ValueError):
            return None


def _as_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _as_abstract(value: object) -> str | None:
    text = str(value) if value is not None else ""
    return text or None


def _as_year(value: object) -> int | None:
    try:
        year = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return year if 1800 <= year <= 2200 else None


def _as_non_negative_int(value: object) -> int | None:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None
