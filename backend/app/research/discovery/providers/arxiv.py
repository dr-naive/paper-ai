"""arXiv compatibility adapter with complete-abstract Atom normalization."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from app.config import settings

from ..schemas import ProviderCapabilities, ProviderPaperDTO, SearchFiltersDTO
from .base import AcademicSearchMalformedResponseError, AcademicSearchProviderError, AcademicSearchTimeoutError


ARXIV_API_URL = "https://export.arxiv.org/api/query"
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivAcademicSearchProvider:
    name = "arxiv"

    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
        client: httpx.AsyncClient | None = None,
        endpoint: str = ARXIV_API_URL,
    ) -> None:
        self._timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.SEARCH_TIMEOUT_SECONDS
        self._client = client
        self._endpoint = endpoint

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_year=False,
            supports_language=False,
            supports_field=False,
            supports_publication_type=False,
            returns_abstract=True,
            returns_pdf_url=True,
            returns_citation_count=False,
        )

    async def search(
        self,
        query: str,
        filters: SearchFiltersDTO,
        limit: int,
    ) -> list[ProviderPaperDTO]:
        del filters
        if not query.strip():
            raise ValueError("query 不能为空")
        if not 1 <= limit <= settings.SEARCH_RESULT_LIMIT:
            raise ValueError(f"limit 必须在 1 到 {settings.SEARCH_RESULT_LIMIT} 之间")
        params = {
            "search_query": f"all:{query.strip()}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        try:
            if self._client is not None:
                response = await self._client.get(self._endpoint, params=params)
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.get(self._endpoint, params=params)
        except httpx.TimeoutException as exc:
            raise AcademicSearchTimeoutError("arXiv 请求超时") from exc
        except httpx.HTTPError as exc:
            raise AcademicSearchProviderError("arXiv 连接失败") from exc
        if response.status_code == 429:
            raise AcademicSearchProviderError("arXiv 请求超过速率限制")
        if response.is_error:
            raise AcademicSearchProviderError(f"arXiv 请求失败: HTTP {response.status_code}")
        return parse_arxiv_atom(response.text)


def parse_arxiv_atom(xml_text: str) -> list[ProviderPaperDTO]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise AcademicSearchMalformedResponseError("arXiv 返回了无效 Atom XML") from exc
    papers: list[ProviderPaperDTO] = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        paper = _parse_entry(entry)
        if paper is not None:
            papers.append(paper)
    return papers


def _parse_entry(entry: ET.Element) -> ProviderPaperDTO | None:
    source_url = _text(entry.find("atom:id", _ATOM_NS))
    source_id = source_url.rstrip("/").split("/")[-1] if source_url else ""
    title = " ".join((_text(entry.find("atom:title", _ATOM_NS)) or "").split())
    if not source_id or not title:
        return None
    pdf_url = next(
        (link.get("href") for link in entry.findall("atom:link", _ATOM_NS) if link.get("title") == "pdf" and link.get("href")),
        None,
    )
    published = _text(entry.find("atom:published", _ATOM_NS))
    categories = [category.get("term", "").strip() for category in entry.findall("atom:category", _ATOM_NS) if category.get("term")]
    authors = [_text(author.find("atom:name", _ATOM_NS)) for author in entry.findall("atom:author", _ATOM_NS)]
    return ProviderPaperDTO(
        source_paper_id=source_id,
        title=title,
        authors=[author for author in authors if author],
        year=_as_year(published),
        venue=_text(entry.find("arxiv:journal_ref", _ATOM_NS)),
        abstract=_raw_text(entry.find("atom:summary", _ATOM_NS)),
        doi=_text(entry.find("arxiv:doi", _ATOM_NS)),
        paper_url=source_url,
        pdf_url=pdf_url,
        publication_type="preprint",
        fields=categories,
        open_access=True,
    )


def _text(element: ET.Element | None) -> str | None:
    value = str(element.text or "").strip() if element is not None else ""
    return value or None


def _raw_text(element: ET.Element | None) -> str | None:
    value = str(element.text or "") if element is not None else ""
    return value or None


def _as_year(value: str | None) -> int | None:
    try:
        return int((value or "")[:4])
    except ValueError:
        return None
