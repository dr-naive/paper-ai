"""Bounded Literature Discovery workflow for the V1 search API."""
from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import uuid4

from app.config import settings

from .normalize import deduplicate_results, normalize_provider_paper
from .providers.base import AcademicSearchProvider, AcademicSearchProviderError
from .providers.crossref import CrossrefMetadataProvider
from .providers.semantic_scholar import SemanticScholarAcademicSearchProvider
from .schemas import (
    LiteratureSearchRequest,
    LiteratureSearchResponse,
    PaperSearchResultDTO,
    SearchFiltersDTO,
    SearchIntentDTO,
    SearchPlanDTO,
)


DiscoveryStage = Literal[
    "preparing",
    "searching",
    "screening",
    "retrying",
    "finalizing",
    "completed",
    "failed",
]
ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class QualityDecision:
    enough: bool
    relevant_count: int
    reason: str


class SearchPlanner(Protocol):
    def plan(
        self,
        intent: SearchIntentDTO,
        filters: SearchFiltersDTO,
        *,
        round_number: int,
        previous_queries: set[str],
        project_summary: str | None = None,
    ) -> SearchPlanDTO:
        ...


class DeterministicSearchPlanner:
    """Generate a small set of complementary queries without exposing model reasoning."""

    def __init__(self, max_queries: int | None = None) -> None:
        self._max_queries = max_queries or settings.SEARCH_MAX_QUERIES_PER_ROUND

    def plan(
        self,
        intent: SearchIntentDTO,
        filters: SearchFiltersDTO,
        *,
        round_number: int,
        previous_queries: set[str],
        project_summary: str | None = None,
    ) -> SearchPlanDTO:
        del filters
        topic = intent.topic.strip() or (project_summary or "").strip()
        keywords = " ".join(intent.keywords[:8])
        question = (intent.research_question or "").strip()
        methods = " ".join(intent.preferred_methods[:4])
        contexts = " ".join(intent.target_contexts[:4])

        candidates: list[str] = []
        if round_number == 1:
            candidates.extend(
                value
                for value in (
                    " ".join(part for part in (topic, keywords) if part),
                    " ".join(part for part in (question, topic) if part),
                    " ".join(part for part in (topic, methods, contexts) if part),
                )
                if value
            )
        else:
            modifier = "review" if round_number == 2 else "empirical study"
            candidates.extend(
                value
                for value in (
                    " ".join(part for part in (topic, keywords, modifier) if part),
                    " ".join(part for part in (question, modifier) if part),
                    " ".join(part for part in (topic, methods, contexts, modifier) if part),
                )
                if value
            )

        queries: list[str] = []
        seen = {query.casefold().strip() for query in previous_queries}
        for candidate in candidates:
            query = " ".join(candidate.split())
            key = query.casefold()
            if query and key not in seen:
                seen.add(key)
                queries.append(query)
            if len(queries) >= self._max_queries:
                break
        if not queries and not previous_queries and topic:
            queries = [topic]
        rationale = f"第 {round_number} 轮使用主题、问题、方法和场景的互补检索式。"
        return SearchPlanDTO(queries=queries, rationale_summary=rationale)


class DiscoveryProviderFailure(RuntimeError):
    """All configured providers failed for a bounded query attempt."""

    def __init__(self, provider_name: str, cause: Exception) -> None:
        self.provider_name = provider_name
        self.cause = cause
        super().__init__(f"{provider_name} academic search failed: {cause}")


def build_default_providers() -> tuple[AcademicSearchProvider, tuple[AcademicSearchProvider, ...]]:
    """Build the configured primary and the credential-free metadata fallback."""
    primary = SemanticScholarAcademicSearchProvider()
    fallback = (CrossrefMetadataProvider(),)
    return primary, fallback


def evaluate_result_quality(
    intent: SearchIntentDTO,
    results: list[PaperSearchResultDTO],
    *,
    target_count: int,
    round_number: int,
) -> QualityDecision:
    """Use a conservative deterministic relevance/coverage gate for V1."""
    if not results:
        return QualityDecision(False, 0, "当前检索没有返回真实论文。")

    terms = _intent_terms(intent)
    relevant_count = sum(1 for result in results if _result_matches(result, terms))
    if relevant_count == 0:
        return QualityDecision(False, 0, "当前结果与研究主题的词面重合不足。")
    if len(results) < target_count:
        return QualityDecision(False, relevant_count, f"当前仅找到 {len(results)} 篇候选论文。")
    return QualityDecision(True, relevant_count, f"第 {round_number} 轮已获得足够的相关候选论文。")


class LiteratureDiscoveryWorkflow:
    """Run one synchronous, bounded discovery search without persistence or Agent runtime coupling."""

    def __init__(
        self,
        *,
        primary_provider: AcademicSearchProvider,
        fallback_providers: Sequence[AcademicSearchProvider] = (),
        planner: SearchPlanner | None = None,
        quality_checker: Callable[..., QualityDecision] = evaluate_result_quality,
        progress: ProgressCallback | None = None,
        execution_id: str | None = None,
    ) -> None:
        self._primary_provider = primary_provider
        self._fallback_providers = tuple(fallback_providers)
        self._planner = planner or DeterministicSearchPlanner()
        self._quality_checker = quality_checker
        self._progress = progress
        self.execution_id = execution_id or str(uuid4())

    async def run(
        self,
        request: LiteratureSearchRequest,
        *,
        project_summary: str | None = None,
    ) -> LiteratureSearchResponse:
        target_count = request.max_results
        warnings: list[str] = []
        previous_queries: set[str] = set()
        normalized_results: list[PaperSearchResultDTO] = []
        providers_used: list[str] = []
        provider_failures: list[DiscoveryProviderFailure] = []
        search_rounds = 0

        await self._emit("preparing", "正在准备检索条件", round_number=0, result_count=0)
        try:
            for round_number in range(1, settings.SEARCH_MAX_ROUNDS + 1):
                search_rounds = round_number
                plan = self._planner.plan(
                    request.intent,
                    request.filters,
                    round_number=round_number,
                    previous_queries=previous_queries,
                    project_summary=project_summary,
                )
                queries = [query for query in plan.queries if query.casefold() not in previous_queries]
                if not queries:
                    break
                previous_queries.update(query.casefold() for query in queries)
                await self._emit("searching", "正在搜索相关论文", round_number=round_number, result_count=len(normalized_results))

                for query in queries[: settings.SEARCH_MAX_QUERIES_PER_ROUND]:
                    try:
                        provider_name, papers = await self._search_with_fallback(query, request.filters, target_count, warnings)
                    except DiscoveryProviderFailure as failure:
                        provider_failures.append(failure)
                        continue
                    if provider_name not in providers_used:
                        providers_used.append(provider_name)
                    normalized_results.extend(
                        normalize_provider_paper(provider_name, paper) for paper in papers
                    )
                    normalized_results = deduplicate_results(normalized_results)
                    if len(normalized_results) >= target_count:
                        interim_decision = self._quality_checker(
                            request.intent,
                            normalized_results,
                            target_count=target_count,
                            round_number=round_number,
                        )
                        if interim_decision.enough:
                            break

                normalized_results = deduplicate_results(normalized_results)
                await self._emit("screening", "正在筛选结果", round_number=round_number, result_count=len(normalized_results))
                decision = self._quality_checker(
                    request.intent,
                    normalized_results,
                    target_count=target_count,
                    round_number=round_number,
                )
                if decision.enough or round_number >= settings.SEARCH_MAX_ROUNDS:
                    if not decision.enough and decision.reason not in warnings:
                        warnings.append(decision.reason)
                    break
                await self._emit("retrying", "正在补充检索", round_number=round_number, result_count=len(normalized_results))

            if not normalized_results and provider_failures:
                raise provider_failures[-1]

            selected = _select_results(request.intent, normalized_results, target_count)
            if len(selected) < target_count:
                warning = f"仅找到 {len(selected)} 篇满足当前检索条件的真实论文。"
                if warning not in warnings:
                    warnings.append(warning)
            if not selected and "当前没有符合条件的真实论文。" not in warnings:
                warnings.append("当前没有符合条件的真实论文。")

            await self._emit("finalizing", "正在整理最终结果", round_number=search_rounds, result_count=len(selected))
            response = LiteratureSearchResponse(
                execution_id=self.execution_id,
                papers=selected,
                provider="+".join(providers_used) or self._primary_provider.name,
                result_count=len(selected),
                search_rounds=max(search_rounds, 1),
                warnings=_unique_warnings(warnings),
            )
            await self._emit("completed", "检索完成", round_number=response.search_rounds, result_count=response.result_count, response=response)
            return response
        except DiscoveryProviderFailure as failure:
            await self._emit("failed", "学术检索服务暂时不可用", round_number=max(search_rounds, 1), result_count=len(normalized_results), error=str(failure))
            raise

    async def _search_with_fallback(
        self,
        query: str,
        filters: SearchFiltersDTO,
        limit: int,
        warnings: list[str],
    ) -> tuple[str, list[Any]]:
        providers = (self._primary_provider, *self._fallback_providers)
        last_error: Exception | None = None
        for index, provider in enumerate(providers):
            try:
                papers = await provider.search(query, filters, limit)
                if index > 0:
                    warning = "主检索服务暂时不可用，已使用补充 metadata Provider。"
                    if warning not in warnings:
                        warnings.append(warning)
                return provider.name, papers
            except AcademicSearchProviderError as exc:
                last_error = exc
                if index == 0 and self._fallback_providers:
                    continue
                break
        raise DiscoveryProviderFailure(self._primary_provider.name, last_error or RuntimeError("unknown provider error"))

    async def _emit(
        self,
        stage: DiscoveryStage,
        message: str,
        *,
        round_number: int,
        result_count: int,
        response: LiteratureSearchResponse | None = None,
        error: str | None = None,
    ) -> None:
        if self._progress is None:
            return
        payload: dict[str, Any] = {
            "execution_id": self.execution_id,
            "stage": stage,
            "status": stage,
            "message": message,
            "search_rounds": round_number,
            "result_count": result_count,
        }
        if response is not None:
            payload.update(response.model_dump(mode="json"))
        if error:
            payload["error"] = error
        await self._progress(payload)


def _intent_terms(intent: SearchIntentDTO) -> list[str]:
    values = [intent.topic, intent.research_question or "", *intent.keywords]
    terms: list[str] = []
    for value in values:
        for term in re.findall(r"[\w\u4e00-\u9fff]+", value.casefold()):
            if len(term) >= 2 and term not in terms:
                terms.append(term)
    return terms


def _result_matches(result: PaperSearchResultDTO, terms: list[str]) -> bool:
    if not terms:
        return True
    haystack = " ".join((result.title, result.abstract or "")).casefold()
    return any(term in haystack for term in terms)


def _select_results(
    intent: SearchIntentDTO,
    results: list[PaperSearchResultDTO],
    target_count: int,
) -> list[PaperSearchResultDTO]:
    terms = _intent_terms(intent)

    def score(result: PaperSearchResultDTO) -> tuple[int, int, int]:
        haystack = " ".join((result.title, result.abstract or "")).casefold()
        relevance = sum(term in haystack for term in terms)
        completeness = sum(
            value is not None and value != ""
            for value in (result.abstract, result.doi, result.venue, result.paper_url)
        )
        return relevance, completeness, int(result.citation_count or 0)

    ranked = sorted(enumerate(results), key=lambda item: (*score(item[1]), -item[0]), reverse=True)
    return [result for _, result in ranked[:target_count]]


def _unique_warnings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
