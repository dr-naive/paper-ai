from __future__ import annotations

from dataclasses import asdict, dataclass
import re
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
    abstained: bool
    abstention_correct: float | None
    over_abstention: float | None
    answer_number_count: int
    unsupported_number_count: int
    unsupported_number_rate: float
    critical_hallucination: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _citation_chunk(citation: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any] | None:
    source_id = str(citation.get("source_id") or "").upper()
    if source_id.startswith("S") and source_id[1:].isdigit():
        index = int(source_id[1:]) - 1
        if 0 <= index < len(chunks):
            return chunks[index]
    return None


_ABSTENTION_PATTERNS = [
    r"未(?:提及|说明|报告|给出|找到)",
    r"没有(?:提及|说明|报告|给出|找到|相关)",
    r"无法(?:确定|回答|判断|从.*得出)",
    r"不能(?:确定|回答|判断)",
    r"no\s+(?:evidence|mention|information)",
    r"not\s+(?:mentioned|reported|specified|found)",
    r"cannot\s+(?:determine|answer)",
    r"insufficient\s+(?:evidence|information)",
]


def is_abstention_answer(answer: str) -> bool:
    normalized = str(answer or "").strip().lower()
    if not normalized:
        return False
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _ABSTENTION_PATTERNS)


def _strip_list_markers(text: str) -> str:
    return re.sub(r"(?m)^\s*(?:[-*]|\d+[.)、])\s+", "", str(text or ""))


def _normalize_number(value: str) -> str:
    value = value.replace(",", "").strip().lower()
    value = value.rstrip("%％")
    try:
        numeric = float(value)
    except ValueError:
        return value
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.10g}"


def _extract_numbers(text: str) -> set[str]:
    cleaned = _strip_list_markers(text)
    # Keep decimals, comma-grouped values and percentages; skip standalone years is
    # intentionally not done because paper claims often hinge on years.
    matches = re.findall(r"(?<![A-Za-z0-9_.])-?\d+(?:,\d{3})*(?:\.\d+)?\s*[%％]?", cleaned)
    return {_normalize_number(match) for match in matches if match.strip()}


def _support_corpus(row: dict[str, Any]) -> str:
    case = row.get("case", {})
    evidence_text = "\n".join(str(item.get("quote", "")) for item in case.get("evidence", []))
    retrieved_text = "\n".join(str(chunk.get("content", "")) for chunk in row.get("retrieved", []))
    citation_text = "\n".join(str(item.get("text", "")) for item in row.get("citations", []))
    return "\n".join([
        str(case.get("reference_answer", "")),
        "\n".join(str(claim) for claim in case.get("reference_claims", [])),
        evidence_text,
        retrieved_text,
        citation_text,
    ])


def _unsupported_answer_numbers(row: dict[str, Any]) -> tuple[int, int]:
    answer_numbers = _extract_numbers(row.get("answer", ""))
    support_numbers = _extract_numbers(_support_corpus(row))
    unsupported = answer_numbers - support_numbers
    return len(answer_numbers), len(unsupported)


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
    answer_number_count, unsupported_number_count = _unsupported_answer_numbers(row)
    must_abstain = bool(case.get("must_abstain", False))
    answerable = bool(case.get("answerable", not must_abstain))
    abstained = is_abstention_answer(answer)
    abstention_correct = float(abstained) if must_abstain else None
    over_abstention = float(abstained) if answerable else None
    unsupported_number_rate = (
        unsupported_number_count / answer_number_count if answer_number_count else 0.0
    )
    critical_hallucination = float(
        (must_abstain and not abstained) or unsupported_number_count > 0
    )

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
        abstained=abstained,
        abstention_correct=abstention_correct,
        over_abstention=over_abstention,
        answer_number_count=answer_number_count,
        unsupported_number_count=unsupported_number_count,
        unsupported_number_rate=unsupported_number_rate,
        critical_hallucination=critical_hallucination,
    )


def aggregate_e2e_metrics(rows: list[E2ECaseMetrics]) -> dict[str, Any]:
    def mean(field: str, values: list[E2ECaseMetrics] = rows) -> float:
        return round(sum(float(getattr(row, field)) for row in values) / len(values), 4) if values else 0.0

    page_rows = [row for row in rows if row.page_accuracy is not None]
    abstention_rows = [row for row in rows if row.abstention_correct is not None]
    answerable_rows = [row for row in rows if row.over_abstention is not None]
    return {
        "case_count": len(rows),
        "citation_precision": mean("citation_precision"),
        "citation_recall": mean("citation_recall"),
        "page_accuracy": mean("page_accuracy", page_rows) if page_rows else None,
        "claim_coverage_proxy": mean("claim_coverage_proxy"),
        "abstention_accuracy": mean("abstention_correct", abstention_rows) if abstention_rows else None,
        "over_abstention_rate": mean("over_abstention", answerable_rows) if answerable_rows else None,
        "unsupported_number_rate": mean("unsupported_number_rate"),
        "critical_hallucination_rate": mean("critical_hallucination"),
        "citation_count": sum(row.citation_count for row in rows),
        "grounded_citations": sum(row.grounded_citations for row in rows),
        "unsupported_number_count": sum(row.unsupported_number_count for row in rows),
        "answer_number_count": sum(row.answer_number_count for row in rows),
    }
