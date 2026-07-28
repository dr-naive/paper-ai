"""Deterministic evidence validation and table calculations before generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from app.rag.hybrid_retrieval import tokenize


_NOISE_TYPES = {"header", "footer", "page_number", "watermark"}
_NUMBER = re.compile(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?")


@dataclass
class EvidenceReview:
    chunks: list[dict[str, Any]]
    sufficient: bool
    coverage: float
    issues: list[str] = field(default_factory=list)
    calculation: str = ""


def _numeric_calculation(question: str, chunks: list[dict[str, Any]]) -> str:
    operation = None
    if re.search(r"最高|最大|max(?:imum)?", question, re.I):
        operation = "最大值"
    elif re.search(r"最低|最小|min(?:imum)?", question, re.I):
        operation = "最小值"
    elif re.search(r"平均|均值|average|mean", question, re.I):
        operation = "平均值"
    if not operation:
        return ""
    values: list[tuple[float, str, str]] = []
    for chunk in chunks:
        for field in chunk.get("fields") or []:
            raw = str(field.get("value") or "")
            match = _NUMBER.search(raw.replace(",", ""))
            if match:
                values.append((float(match.group()), str(field.get("label") or ""), raw))
    if not values:
        return ""
    if operation == "最大值":
        value, label, raw = max(values, key=lambda item: item[0])
        return f"确定性计算：{label}的最大值为{raw}（参与比较{len(values)}个数值）。"
    if operation == "最小值":
        value, label, raw = min(values, key=lambda item: item[0])
        return f"确定性计算：{label}的最小值为{raw}（参与比较{len(values)}个数值）。"
    result = mean(item[0] for item in values)
    return f"确定性计算：{len(values)}个数值的平均值为{result:.4g}。"


def review_evidence(
    question: str,
    chunks: list[dict[str, Any]],
    intent: str,
) -> EvidenceReview:
    query_tokens = set(tokenize(question))
    cleaned = [
        chunk for chunk in chunks
        if chunk.get("element_type") not in _NOISE_TYPES
        and str(chunk.get("content") or "").strip()
    ]
    relevant = []
    for chunk in cleaned:
        tokens = set(tokenize(f"{chunk.get('section', '')} {chunk.get('content', '')}"))
        if not query_tokens or query_tokens & tokens or chunk.get("retrieval_method") == "exact_table_number":
            relevant.append(chunk)
    issues = []
    if len(relevant) < min(3, len(cleaned)):
        issues.append("直接相关证据较少")
    sections = {str(chunk.get("section") or "") for chunk in relevant}
    if intent == "comparison" and len(sections) < 2:
        issues.append("比较对象覆盖不完整")
    if intent == "table" and not any(
        chunk.get("chunk_type") in {"table", "table_row"} for chunk in relevant
    ):
        issues.append("缺少结构化表格证据")
    coverage = min(1.0, len(relevant) / max(min(len(query_tokens), 5), 1))
    return EvidenceReview(
        chunks=relevant or cleaned,
        sufficient=bool(relevant) and not issues,
        coverage=round(coverage, 4),
        issues=issues,
        calculation=_numeric_calculation(question, relevant),
    )
