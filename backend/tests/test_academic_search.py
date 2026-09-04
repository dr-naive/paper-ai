import httpx
import pytest

from app.research.discovery.normalize import deduplicate_results, normalize_provider_paper
from app.research.discovery.providers.arxiv import parse_arxiv_atom
from app.research.discovery.providers.base import (
    AcademicSearchMalformedResponseError,
    AcademicSearchRateLimitError,
    AcademicSearchTimeoutError,
)
from app.research.discovery.providers.crossref import CrossrefMetadataProvider
from app.research.discovery.providers.semantic_scholar import S2_FIELDS, SemanticScholarAcademicSearchProvider
from app.research.discovery.schemas import ProviderPaperDTO, SearchFiltersDTO


def _semantic_paper(**overrides):
    paper = {
        "paperId": "s2-1",
        "title": "A Complete Academic Search Result",
        "authors": [{"name": "张伟"}, {"name": "Ada Lovelace"}],
        "year": 2024,
        "venue": "Journal of Test Data",
        "abstract": "完整摘要 " * 300,
        "externalIds": {"DOI": "https://doi.org/10.1000/Example.1"},
        "url": "https://www.semanticscholar.org/paper/s2-1",
        "openAccessPdf": {"url": "https://example.org/open.pdf"},
        "fieldsOfStudy": ["Computer Science"],
        "publicationTypes": ["JournalArticle"],
        "citationCount": 42,
    }
    paper.update(overrides)
    return paper


@pytest.mark.asyncio
async def test_semantic_scholar_maps_supported_filters_and_preserves_full_abstract():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        seen["api_key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={"data": [_semantic_paper()]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SemanticScholarAcademicSearchProvider(api_key="test-key", client=client)
        papers = await provider.search(
            "academic search",
            SearchFiltersDTO(
                year_from=2020,
                year_to=2024,
                language="en",
                fields=["computer_science"],
                publication_types=["journal_article"],
            ),
            5,
        )

    assert seen["api_key"] == "test-key"
    params = seen["params"]
    assert isinstance(params, dict)
    assert params == {
        "query": "academic search",
        "limit": "5",
        "fields": S2_FIELDS,
        "year": "2020-2024",
        "fieldsOfStudy": "Computer Science",
        "publicationTypes": "JournalArticle",
    }
    assert papers[0].abstract == "完整摘要 " * 300
    assert papers[0].doi == "https://doi.org/10.1000/Example.1"
    assert papers[0].language is None


@pytest.mark.asyncio
async def test_semantic_scholar_rate_limit_is_reported_without_retrying():
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(429, headers={"Retry-After": "12"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SemanticScholarAcademicSearchProvider(client=client, max_retries=3)
        with pytest.raises(AcademicSearchRateLimitError) as error:
            await provider.search("query", SearchFiltersDTO(), 1)

    assert requests == 1
    assert error.value.retry_after_seconds == 12.0


@pytest.mark.asyncio
async def test_semantic_scholar_reports_timeout_and_malformed_payloads():
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
        provider = SemanticScholarAcademicSearchProvider(client=client, max_retries=0)
        with pytest.raises(AcademicSearchTimeoutError):
            await provider.search("query", SearchFiltersDTO(), 1)

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": {}}))) as client:
        provider = SemanticScholarAcademicSearchProvider(client=client)
        with pytest.raises(AcademicSearchMalformedResponseError):
            await provider.search("query", SearchFiltersDTO(), 1)


def test_arxiv_normalization_preserves_full_abstract_and_metadata():
    abstract = "long arXiv abstract " * 100
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2401.12345v2</id>
        <title> An arXiv\n Result </title>
        <summary>{abstract}</summary>
        <published>2024-01-02T00:00:00Z</published>
        <author><name>张伟</name></author>
        <link title="pdf" href="https://arxiv.org/pdf/2401.12345v2" />
        <category term="cs.CL" />
        <arxiv:doi>10.1000/arxiv.test</arxiv:doi>
      </entry>
    </feed>"""

    paper = parse_arxiv_atom(xml)[0]

    assert paper.source_paper_id == "2401.12345v2"
    assert paper.abstract == abstract
    assert paper.authors == ["张伟"]
    assert paper.fields == ["cs.CL"]
    assert paper.doi == "10.1000/arxiv.test"


def test_deduplication_prioritizes_doi_and_merges_metadata_without_losing_full_abstract():
    short = normalize_provider_paper(
        "semantic_scholar",
        ProviderPaperDTO(
            source_paper_id="s2-1",
            title="A Study of Search",
            authors=["张伟"],
            year=2023,
            abstract="short",
            doi="doi:10.1000/SEARCH",
        ),
    )
    complete = normalize_provider_paper(
        "arxiv",
        ProviderPaperDTO(
            source_paper_id="2301.00001",
            title="A Study of Search",
            authors=["Ada Lovelace", "张伟"],
            year=2023,
            venue="Conference X",
            abstract="complete abstract " * 200,
            doi="https://doi.org/10.1000/search",
            pdf_url="https://arxiv.org/pdf/2301.00001",
            citation_count=8,
            open_access=True,
        ),
    )

    merged = deduplicate_results([short, complete])

    assert len(merged) == 1
    assert merged[0].doi == "10.1000/search"
    assert merged[0].abstract == "complete abstract " * 200
    assert merged[0].authors == ["Ada Lovelace", "张伟"]
    assert merged[0].venue == "Conference X"
    assert merged[0].pdf_url == "https://arxiv.org/pdf/2301.00001"


def test_deduplication_uses_normalized_title_and_year_when_doi_is_missing():
    first = normalize_provider_paper(
        "semantic_scholar",
        ProviderPaperDTO(source_paper_id="one", title="An   Efficient—Method", authors=["张伟"], year=2022),
    )
    second = normalize_provider_paper(
        "arxiv",
        ProviderPaperDTO(source_paper_id="two", title="An efficient method", authors=["Ada"], year=2022),
    )

    assert len(deduplicate_results([first, second])) == 1


def test_normalization_keeps_unicode_authors_when_optional_metadata_is_missing():
    result = normalize_provider_paper(
        "semantic_scholar",
        ProviderPaperDTO(
            source_paper_id="missing-metadata",
            title="A Paper Without Venue Metadata",
            authors=["李雷", "Márta Kovács"],
            year=None,
            venue=None,
            abstract=None,
            doi=None,
            pdf_url=None,
        ),
    )

    assert result.year is None
    assert result.venue is None
    assert result.authors == ["李雷", "Márta Kovács"]
    assert result.download_available is False
    assert result.import_available is False


def _crossref_work(**overrides):
    work = {
        "DOI": "10.5555/crossref.example",
        "title": ["A Crossref Metadata Result"],
        "author": [{"given": "Ada", "family": "Lovelace"}, {"name": "张伟"}],
        "published-print": {"date-parts": [[2024, 3, 1]]},
        "container-title": ["Journal of Metadata"],
        "abstract": "<jats:p>A complete Crossref abstract.</jats:p>",
        "URL": "https://doi.org/10.5555/crossref.example",
        "link": [{"URL": "https://publisher.example/paper.pdf", "content-type": "application/pdf"}],
        "type": "journal-article",
        "subject": ["Computer Science"],
        "is-referenced-by-count": 13,
        "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}],
    }
    work.update(overrides)
    return work


@pytest.mark.asyncio
async def test_crossref_maps_year_filter_and_preserves_metadata_without_api_key():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        seen["api_key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={"message": {"items": [_crossref_work()]}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CrossrefMetadataProvider(mailto="researcher@example.org", client=client)
        papers = await provider.search(
            "metadata search",
            SearchFiltersDTO(year_from=2020, year_to=2024, fields=["computer_science"]),
            5,
        )

    assert seen["api_key"] is None
    assert seen["params"] == {
        "query.bibliographic": "metadata search",
        "rows": "5",
        "mailto": "researcher@example.org",
        "filter": "from-pub-date:2020-01-01,until-pub-date:2024-12-31",
    }
    assert papers[0].abstract == "A complete Crossref abstract."
    assert papers[0].authors == ["Ada Lovelace", "张伟"]
    assert papers[0].year == 2024
    assert papers[0].pdf_url == "https://publisher.example/paper.pdf"
    assert papers[0].citation_count == 13
    assert papers[0].open_access is True


@pytest.mark.asyncio
async def test_crossref_rate_limit_and_malformed_payload_are_typed():
    requests = 0

    def rate_limit_handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(429, headers={"Retry-After": "7"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(rate_limit_handler)) as client:
        provider = CrossrefMetadataProvider(client=client, max_retries=3)
        with pytest.raises(AcademicSearchRateLimitError) as error:
            await provider.search("query", SearchFiltersDTO(), 1)

    assert requests == 1
    assert error.value.retry_after_seconds == 7.0

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"message": {"items": {}}}))
    ) as client:
        provider = CrossrefMetadataProvider(client=client)
        with pytest.raises(AcademicSearchMalformedResponseError):
            await provider.search("query", SearchFiltersDTO(), 1)
