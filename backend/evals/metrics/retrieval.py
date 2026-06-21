from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from evals.models import EvalCase, Evidence


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text)


def _char_ngrams(text: str, size: int = 3) -> set[str]:
    if len(text) <= size:
        return {text} if text else set()
    return {text[index:index + size] for index in range(len(text) - size + 1)}


def quote_recall(quote: str, content: str) -> float:
    normalized_quote = normalize_text(quote)
    normalized_content = normalize_text(content)
    if not normalized_quote or not normalized_content:
        return 0.0
    if normalized_quote in normalized_content:
        return 1.0
    quote_grams = _char_ngrams(normalized_quote)
    content_grams = _char_ngrams(normalized_content)
    if not quote_grams:
        return 0.0
    return len(quote_grams & content_grams) / len(quote_grams)


def evidence_matches_chunk(evidence: Evidence, chunk: dict[str, Any]) -> bool:
    if evidence.source_type == "table" and evidence.table_number is not None:
        chunk_table = re.sub(r"\D", "", str(chunk.get("table_number", "")))
        if chunk_table and int(chunk_table) == evidence.table_number:
            return True

    content = str(chunk.get("content", ""))
    overlap = quote_recall(evidence.quote, content)
    if overlap >= 0.72:
        return True

    page_matches = evidence.page is not None and str(chunk.get("page")) == str(evidence.page)
    evidence_section = normalize_text(evidence.section)
    chunk_section = normalize_text(chunk.get("section", ""))
    section_matches = bool(
        evidence_section
        and chunk_section
        and (evidence_section in chunk_section or chunk_section in evidence_section)
    )
    return overlap >= 0.48 and (page_matches or section_matches)


@dataclass(frozen=True)
class RetrievalCaseMetrics:
    case_id: str
    hit_at_k: float
    evidence_recall_at_k: float
    precision_at_k: float
    reciprocal_rank: float
    table_hit_at_k: float | None
    matched_evidence: int
    evidence_count: int
    relevant_chunks: int
    returned_chunks: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_retrieval_case(
    case: EvalCase,
    retrieved_chunks: Iterable[dict[str, Any]],
    top_k: int,
) -> RetrievalCaseMetrics:
    chunks = list(retrieved_chunks)[:top_k]
    evidence_matches = [
        [evidence_matches_chunk(evidence, chunk) for chunk in chunks]
        for evidence in case.evidence
    ]
    matched_evidence = sum(any(matches) for matches in evidence_matches)
    relevant_by_rank = [
        any(evidence_matches_chunk(evidence, chunk) for evidence in case.evidence)
        for chunk in chunks
    ]
    first_rank = next((rank for rank, relevant in enumerate(relevant_by_rank, 1) if relevant), None)

    table_hit: float | None = None
    if case.expected_tables:
        retrieved_tables = {
            int(value)
            for chunk in chunks
            if (value := re.sub(r"\D", "", str(chunk.get("table_number", ""))))
        }
        table_hit = float(all(number in retrieved_tables for number in case.expected_tables))

    evidence_count = len(case.evidence)
    return RetrievalCaseMetrics(
        case_id=case.id,
        hit_at_k=float(any(relevant_by_rank)),
        evidence_recall_at_k=(matched_evidence / evidence_count if evidence_count else 0.0),
        precision_at_k=sum(relevant_by_rank) / top_k,
        reciprocal_rank=(1.0 / first_rank if first_rank else 0.0),
        table_hit_at_k=table_hit,
        matched_evidence=matched_evidence,
        evidence_count=evidence_count,
        relevant_chunks=sum(relevant_by_rank),
        returned_chunks=len(chunks),
    )


def aggregate_retrieval_metrics(metrics: Iterable[RetrievalCaseMetrics]) -> dict[str, float | int | None]:
    rows = list(metrics)
    table_rows = [row for row in rows if row.table_hit_at_k is not None]

    def mean(field: str, values=rows) -> float:
        return round(sum(float(getattr(row, field)) for row in values) / len(values), 4) if values else 0.0

    return {
        "case_count": len(rows),
        "hit_at_k": mean("hit_at_k"),
        "evidence_recall_at_k": mean("evidence_recall_at_k"),
        "precision_at_k": mean("precision_at_k"),
        "mrr": mean("reciprocal_rank"),
        "table_case_count": len(table_rows),
        "table_hit_at_k": mean("table_hit_at_k", table_rows) if table_rows else None,
    }

