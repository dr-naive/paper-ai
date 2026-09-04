"""Crossref REST metadata adapter used for optional enrichment/search fallback."""
from __future__ import annotations

import asyncio
import html
import re
import time
from collections.abc import Awaitable, Callable
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

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


CROSSREF_WORKS_URL = "https://api.crossref.org/v1/works"
_TAG_RE = re.compile(r"<[^>]+>")


class CrossrefMetadataProvider:
    """Use Crossref's public REST API for structured metadata enrichment."""

    name = "crossref"

    def __init__(
        self,
        *,
        mailto: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        endpoint: str = CROSSREF_WORKS_URL,
    ) -> None:
        self._mailto = mailto if mailto is not None else settings.CROSSREF_MAILTO
        self._timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.SEARCH_TIMEOUT_SECONDS
        self._max_retries = max_retries if max_retries is not None else settings.SEARCH_MAX_RETRIES
        self._client = client
        self._sleep = sleep
        self._endpoint = endpoint

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_year=True,
            supports_language=False,
            supports_field=False,
            supports_publication_type=False,
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
            "query.bibliographic": query.strip(),
            "rows": limit,
        }
        if self._mailto:
            params["mailto"] = self._mailto.strip()
        date_filters: list[str] = []
        if filters.year_from is not None:
            date_filters.append(f"from-pub-date:{filters.year_from}-01-01")
        if filters.year_to is not None:
            date_filters.append(f"until-pub-date:{filters.year_to}-12-31")
        if date_filters:
            params["filter"] = ",".join(date_filters)
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
            raise AcademicSearchMalformedResponseError("Crossref 返回了无效 JSON") from exc
        message = payload.get("message") if isinstance(payload, dict) else None
        rows = message.get("items") if isinstance(message, dict) else None
        if not isinstance(rows, list):
            raise AcademicSearchMalformedResponseError("Crossref 响应缺少 message.items 数组")
        papers: list[ProviderPaperDTO] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            paper = _parse_item(row)
            if paper is not None:
                papers.append(paper)
        return papers

    async def _get(self, params: dict[str, str | int]) -> httpx.Response:
        headers = {"User-Agent": "PaperAI/1.0 academic-search"}
        if self._mailto:
            headers["User-Agent"] = f"PaperAI/1.0 academic-search (mailto:{self._mailto.strip()})"
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
                raise AcademicSearchTimeoutError("Crossref 请求超时") from exc
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    await self._sleep(2**attempt)
                    continue
                raise AcademicSearchProviderError("Crossref 连接失败") from exc

            if response.status_code in {401, 403}:
                raise AcademicSearchAuthenticationError("Crossref 拒绝访问")
            if response.status_code == 429:
                raise AcademicSearchRateLimitError(
                    "Crossref 请求超过速率限制",
                    retry_after_seconds=_retry_after_seconds(response.headers.get("Retry-After")),
                )
            if 500 <= response.status_code < 600 and attempt < self._max_retries:
                await self._sleep(2**attempt)
                continue
            if response.is_error:
                raise AcademicSearchProviderError(f"Crossref 请求失败: HTTP {response.status_code}")
            return response
        raise AcademicSearchProviderError("Crossref 请求失败")


def _parse_item(item: dict[str, Any]) -> ProviderPaperDTO | None:
    doi = _as_text(item.get("DOI"))
    paper_url = _as_text(item.get("URL")) or (f"https://doi.org/{doi}" if doi else None)
    source_paper_id = doi or paper_url or ""
    title = _first_text(item.get("title"))
    if not source_paper_id or not title:
        return None
    return ProviderPaperDTO(
        source_paper_id=source_paper_id,
        title=title,
        authors=_authors(item.get("author")),
        year=_publication_year(item),
        venue=_first_text(item.get("container-title")),
        abstract=_clean_abstract(item.get("abstract")),
        doi=doi,
        paper_url=paper_url,
        pdf_url=_pdf_url(item.get("link")),
        publication_type=_as_text(item.get("type")),
        fields=_text_list(item.get("subject")),
        citation_count=_as_non_negative_int(item.get("is-referenced-by-count")),
        open_access=True if item.get("license") else None,
    )


def _authors(value: object) -> list[str]:
    authors: list[str] = []
    for author in value if isinstance(value, list) else []:
        if not isinstance(author, dict):
            continue
        literal = _as_text(author.get("name"))
        if literal:
            authors.append(literal)
            continue
        name = " ".join(
            part for part in (_as_text(author.get("given")), _as_text(author.get("family"))) if part
        )
        if name:
            authors.append(name)
    return authors


def _publication_year(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        value = item.get(key)
        date_parts = value.get("date-parts") if isinstance(value, dict) else None
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list) and date_parts[0]:
            year = _as_year(date_parts[0][0])
            if year is not None:
                return year
    return None


def _pdf_url(value: object) -> str | None:
    for link in value if isinstance(value, list) else []:
        if not isinstance(link, dict):
            continue
        url = _as_text(link.get("URL"))
        if not url:
            continue
        content_type = str(link.get("content-type") or "").casefold()
        path = urlparse(url).path.casefold()
        if content_type == "application/pdf" or path.endswith(".pdf"):
            return url
    return None


def _clean_abstract(value: object) -> str | None:
    if value is None:
        return None
    text = html.unescape(str(value))
    text = _TAG_RE.sub(" ", text)
    text = " ".join(text.split())
    return text or None


def _first_text(value: object) -> str | None:
    values = value if isinstance(value, list) else []
    for item in values:
        text = _as_text(item)
        if text:
            return text
    return None


def _text_list(value: object) -> list[str]:
    return [text for item in value if (text := _as_text(item))] if isinstance(value, list) else []


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
