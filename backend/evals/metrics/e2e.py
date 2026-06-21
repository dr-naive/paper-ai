from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from evals.metrics.retrieval import evidence_matches_chunk, quote_recall
from evals.models import Evidence


@dataclass(frozen=True)
class E2ECaseMetrics:
    case_id: str
    citation_precision: float
    citation_recall: float
    page_accuracy: float | None
    claim_coverage_proxy: float
    citation_count: int
    grounded_citations: int
    evidence_count: int
    covered_evidence: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _citation_chunk(citation: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any] | None:
    source_id = str(citation.get("source_id") or "").upper()
    if source_id.startswith("S") and source_id[1:].isdigit():
        index = int(source_id[1:]) - 1
        if 0 <= index < len(chunks):
            return chunks[index]
    return None


def score_e2e_case(row: dict[str, Any]) -> E2ECaseMetrics:
    case = row.get("case", {})
    chunks = row.get("retrieved", [])
    citations = [item for item in row.get("citations", []) if isinstance(item, dict)]
    mapped = [(citation, _citation_chunk(citation, chunks)) for citation in citations]
    grounded = [
        quote_recall(citation.get("text", ""), chunk.get("content", "")) >= 0.72
        for citation, chunk in mapped
        if chunk is not None
    ]
    grounded_count = sum(grounded)

    evidence = [Evidence.from_dict(item) for item in case.get("evidence", [])]
    cited_chunks = [chunk for _, chunk in mapped if chunk is not None]
    covered_evidence = sum(
        any(evidence_matches_chunk(item, chunk) for chunk in cited_chunks)
        for item in evidence
    )

    page_checks = [
        str(citation.get("page")) == str(chunk.get("page"))
        for citation, chunk in mapped
        if chunk is not None
        and citation.get("page") is not None
        and chunk.get("page") is not None
    ]
    claims = case.get("reference_claims", [])
    answer = row.get("answer", "")
    covered_claims = sum(quote_recall(claim, answer) >= 0.48 for claim in claims)

    return E2ECaseMetrics(
        case_id=str(case.get("id", "")),
        citation_precision=(grounded_count / len(citations) if citations else 0.0),
        citation_recall=(covered_evidence / len(evidence) if evidence else 0.0),
        page_accuracy=(sum(page_checks) / len(page_checks) if page_checks else None),
        claim_coverage_proxy=(covered_claims / len(claims) if claims else 0.0),
        citation_count=len(citations),
        grounded_citations=grounded_count,
        evidence_count=len(evidence),
        covered_evidence=covered_evidence,
    )


def aggregate_e2e_metrics(rows: list[E2ECaseMetrics]) -> dict[str, Any]:
    def mean(field: str, values: list[E2ECaseMetrics] = rows) -> float:
        return round(sum(float(getattr(row, field)) for row in values) / len(values), 4) if values else 0.0

    page_rows = [row for row in rows if row.page_accuracy is not None]
    return {
        "case_count": len(rows),
        "citation_precision": mean("citation_precision"),
        "citation_recall": mean("citation_recall"),
        "page_accuracy": mean("page_accuracy", page_rows) if page_rows else None,
        "claim_coverage_proxy": mean("claim_coverage_proxy"),
        "citation_count": sum(row.citation_count for row in rows),
        "grounded_citations": sum(row.grounded_citations for row in rows),
    }
