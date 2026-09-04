from __future__ import annotations

import pytest

from app.research.discovery.providers.base import AcademicSearchRateLimitError
from app.research.discovery.schemas import (
    LiteratureSearchRequest,
    ProviderPaperDTO,
    SearchFiltersDTO,
    SearchIntentDTO,
)
from app.research.discovery.workflow import (
    DiscoveryProviderFailure,
    LiteratureDiscoveryWorkflow,
)


def _request(*, max_results: int = 10, filters: SearchFiltersDTO | None = None) -> LiteratureSearchRequest:
    return LiteratureSearchRequest(
        project_id="project-1",
        intent=SearchIntentDTO(
            topic="retrieval augmented generation",
            research_question="How does retrieval improve academic writing?",
            keywords=["retrieval", "academic writing"],
            preferred_methods=["evaluation"],
            target_contexts=["research assistants"],
        ),
        filters=filters or SearchFiltersDTO(),
        max_results=max_results,
    )


def _paper(identifier: str, *, title: str = "Retrieval augmented generation for academic writing") -> ProviderPaperDTO:
    return ProviderPaperDTO(
        source_paper_id=identifier,
        title=title,
        abstract="This study evaluates retrieval augmented generation for academic writing.",
        year=2024,
        doi=f"10.1000/{identifier}",
    )


class RecordingProvider:
    name = "fake_primary"

    def __init__(self, responses: dict[str, list[ProviderPaperDTO]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, SearchFiltersDTO, int]] = []

    def capabilities(self):
        return None

    async def search(self, query: str, filters: SearchFiltersDTO, limit: int) -> list[ProviderPaperDTO]:
        self.calls.append((query, filters, limit))
        return list(self.responses.get(query, []))


class AlwaysResultProvider(RecordingProvider):
    def __init__(self, *, count: int) -> None:
        super().__init__()
        self.count = count

    async def search(self, query: str, filters: SearchFiltersDTO, limit: int) -> list[ProviderPaperDTO]:
        self.calls.append((query, filters, limit))
        return [
            _paper(
                f"{self.name}-{index}-{len(self.calls)}",
                title=f"Retrieval augmented generation for academic writing {self.name} {index} {len(self.calls)}",
            )
            for index in range(self.count)
        ]


class FailingProvider(RecordingProvider):
    name = "failing_primary"

    async def search(self, query: str, filters: SearchFiltersDTO, limit: int) -> list[ProviderPaperDTO]:
        self.calls.append((query, filters, limit))
        raise AcademicSearchRateLimitError("rate limited")


class FallbackProvider(AlwaysResultProvider):
    name = "crossref"


@pytest.mark.asyncio
async def test_round_one_sufficient_stops_without_unbounded_research() -> None:
    provider = AlwaysResultProvider(count=2)
    events: list[dict[str, object]] = []

    async def record_event(event: dict[str, object]) -> None:
        events.append(event)

    workflow = LiteratureDiscoveryWorkflow(
        primary_provider=provider,
        progress=record_event,
        execution_id="exec-round-one",
    )

    response = await workflow.run(_request(max_results=2))

    assert response.execution_id == "exec-round-one"
    assert response.result_count == 2
    assert len(response.papers) == 2
    assert response.search_rounds == 1
    assert len(provider.calls) == 1
    assert [event["stage"] for event in events] == [
        "preparing",
        "searching",
        "screening",
        "finalizing",
        "completed",
    ]


@pytest.mark.asyncio
async def test_max_rounds_return_real_partial_results_without_fabrication() -> None:
    provider = AlwaysResultProvider(count=1)
    workflow = LiteratureDiscoveryWorkflow(primary_provider=provider, execution_id="exec-partial")

    response = await workflow.run(_request(max_results=10))

    assert response.search_rounds == 3
    assert response.result_count == 9
    assert len(response.papers) == 9
    assert any("仅找到 9" in warning for warning in response.warnings)
    assert len(provider.calls) == 9


@pytest.mark.asyncio
async def test_zero_results_are_not_fabricated_and_are_bounded() -> None:
    provider = RecordingProvider()
    workflow = LiteratureDiscoveryWorkflow(primary_provider=provider, execution_id="exec-empty")

    response = await workflow.run(_request(max_results=10))

    assert response.search_rounds == 3
    assert response.papers == []
    assert response.result_count == 0
    assert "当前没有符合条件的真实论文。" in response.warnings
    assert len(provider.calls) == 9


@pytest.mark.asyncio
async def test_strong_filters_are_passed_to_each_provider_query() -> None:
    provider = AlwaysResultProvider(count=2)
    filters = SearchFiltersDTO(year_from=2020, year_to=2024, language="en", fields=["computer_science"])

    await LiteratureDiscoveryWorkflow(primary_provider=provider).run(_request(max_results=2, filters=filters))

    assert provider.calls[0][1] == filters


@pytest.mark.asyncio
async def test_primary_rate_limit_uses_configured_fallback_once_per_query() -> None:
    primary = FailingProvider()
    fallback = FallbackProvider(count=2)
    workflow = LiteratureDiscoveryWorkflow(
        primary_provider=primary,
        fallback_providers=(fallback,),
        execution_id="exec-fallback",
    )

    response = await workflow.run(_request(max_results=2))

    assert response.result_count == 2
    assert response.provider == "crossref"
    assert any("补充 metadata Provider" in warning for warning in response.warnings)
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 1


@pytest.mark.asyncio
async def test_provider_failure_without_fallback_is_typed_and_not_retried() -> None:
    provider = FailingProvider()
    workflow = LiteratureDiscoveryWorkflow(primary_provider=provider, execution_id="exec-failed")

    with pytest.raises(DiscoveryProviderFailure) as error:
        await workflow.run(_request(max_results=2))

    assert error.value.provider_name == "failing_primary"
    assert len(provider.calls) == 9


@pytest.mark.asyncio
async def test_provider_error_is_not_hidden_when_fallback_also_fails() -> None:
    primary = FailingProvider()
    fallback = FailingProvider()
    fallback.name = "crossref"
    workflow = LiteratureDiscoveryWorkflow(
        primary_provider=primary,
        fallback_providers=(fallback,),
        execution_id="exec-both-failed",
    )

    with pytest.raises(DiscoveryProviderFailure):
        await workflow.run(_request(max_results=2))

    assert len(primary.calls) == 9
    assert len(fallback.calls) == 9
