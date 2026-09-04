"""QA 工具函数:意图检测、引用构建、置信度计算。

从 app/agent/qa_agent/enhanced_graph.py 提取,供 harness 和 api 层共用。
"""
import json
import re
from difflib import SequenceMatcher
from typing import Any


# ====== 意图检测 patterns ======

METADATA_PATTERNS = {
    "title": [r"标题", r"题目", r"title", r"paper name"],
    "authors": [r"作者", r"谁写", r"author", r"authors"],
    "abstract": [r"摘要", r"abstract"],
    "keywords": [r"关键词", r"关键字", r"keywords"],
    "venue": [r"期刊", r"会议", r"venue", r"发表在哪", r"published"],
    "publication_year": [r"年份", r"哪一年", r"year"],
    "doi": [r"\bdoi\b"],
}

CONTEXT_DEPENDENT_PATTERNS = [
    r"这个",
    r"上面",
    r"刚才",
    r"前面",
    r"\bit\b",
    r"\bthat\b",
    r"\babove\b",
    r"\bprevious\b",
]

COMPLEX_REASONING_PATTERNS = [
    r"证明",
    r"推导",
    r"数学",
    r"公式",
    r"为什么.*成立",
    r"derive",
    r"prove",
    r"equation",
    r"formula",
]

DEEP_REASONING_CONTEXT_PATTERNS = [
    r"复杂",
    r"多步",
    r"严格",
    r"数学",
    r"推导",
    r"证明",
    r"公式",
    r"成立",
    r"derive",
    r"prove",
    r"equation",
    r"formula",
    r"theorem",
]


# ====== 意图检测 ======

def detect_metadata_intent(question: str) -> str | None:
    q = question.lower()
    if re.search(r"(?:表|table|图|figure)\s*\d+", q, re.IGNORECASE):
        return None
    for field, patterns in METADATA_PATTERNS.items():
        if any(re.search(pattern, q, re.IGNORECASE) for pattern in patterns):
            return field
    return None


def needs_deep_thinking(question: str) -> bool:
    q = question.lower().strip()
    if any(re.search(pattern, q, re.IGNORECASE) for pattern in COMPLEX_REASONING_PATTERNS):
        return True
    has_mechanism_word = bool(re.search(r"机制|原理|mechanism|principle", q, re.IGNORECASE))
    has_deep_context = any(
        re.search(pattern, q, re.IGNORECASE)
        for pattern in DEEP_REASONING_CONTEXT_PATTERNS
    )
    return has_mechanism_word and has_deep_context


def safe_json_loads(text: str) -> dict:
    """Parse model JSON output with light cleanup."""
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


# ====== 引用构建 ======

def _normalize_locator_text(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(text or "").lower())


def _best_source_excerpt(citation_text: str, source_content: str, max_chars: int = 180) -> str:
    """Choose an exact source sentence for client-side PDF text location."""
    source_content = str(source_content or "").strip()
    if not source_content:
        return ""

    candidates = [
        part.strip()
        for part in re.split(r"(?<=[。！？.!?；;])\s*|\n+", source_content)
        if len(_normalize_locator_text(part)) >= 8
    ]
    if not candidates:
        return source_content[:max_chars]

    normalized_citation = _normalize_locator_text(citation_text)
    if not normalized_citation:
        return candidates[0][:max_chars]

    best = max(
        candidates,
        key=lambda part: SequenceMatcher(
            None,
            normalized_citation,
            _normalize_locator_text(part),
        ).ratio(),
    )
    return best[:max_chars]


def _enrich_citations(citations: list, chunks: list) -> list:
    """Attach deterministic retrieval metadata used for PDF source location."""
    enriched = []
    for citation in citations or []:
        if not isinstance(citation, dict):
            continue

        item = dict(citation)
        source = None
        source_id = str(item.get("source_id") or "").upper()
        if source_id.startswith("S") and source_id[1:].isdigit():
            index = int(source_id[1:]) - 1
            if 0 <= index < len(chunks):
                source = chunks[index]

        if source is None:
            section = str(item.get("section") or "")
            source = next(
                (chunk for chunk in chunks if str(chunk.get("section") or "") == section),
                None,
            )

        if source:
            item["source_id"] = f"S{chunks.index(source) + 1}"
            for field in (
                "paper_id",
                "paper_title",
                "paper_authors",
                "paper_role",
                "project_id",
                "page",
                "table_number",
                "chunk_type",
                "chunk_index",
                "element_id",
                "element_type",
                "bbox",
                "section_path",
                "layout_confidence",
                "table_id",
                "row_index",
                "fields",
                "cell_bboxes",
            ):
                if source.get(field) is not None:
                    item[field] = source[field]
            if source.get("page") is not None:
                item["position"] = f"PDF 第{source['page']}页"
            item["search_text"] = _best_source_excerpt(
                item.get("text", ""),
                source.get("content", ""),
            )
        enriched.append(item)
    return enriched


def build_deterministic_citations(answer: str, chunks: list) -> list:
    """Resolve model source markers to exact retrieval metadata."""
    source_indexes = []
    for value in re.findall(r"\[S(\d+)\]", answer or "", flags=re.IGNORECASE):
        index = int(value) - 1
        if 0 <= index < len(chunks) and index not in source_indexes:
            source_indexes.append(index)

    citations = []
    for index in source_indexes:
        chunk = chunks[index]
        content = str(chunk.get("content") or "").strip()
        citations.append({
            "source_id": f"S{index + 1}",
            "section": chunk.get("section", "未知章节"),
            "text": _best_source_excerpt("", content),
        })
    return _deduplicate_citations(_enrich_citations(citations, chunks))


def _citation_text_signature(value: Any) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(value or "").lower())


def _citation_precision(item: dict) -> tuple[int, int, int]:
    return (
        int(bool(item.get("element_id") and item.get("bbox"))),
        int(bool(item.get("table_id") and item.get("row_index") is not None)),
        int(bool(item.get("search_text"))),
    )


def _deduplicate_citations(citations: list[dict]) -> list[dict]:
    """Remove repeated display citations without changing source provenance."""
    unique: list[dict] = []
    for citation in citations:
        duplicate_index = None
        for index, existing in enumerate(unique):
            if str(existing.get("page") or "") != str(citation.get("page") or ""):
                continue
            same_element = (
                citation.get("element_id")
                and citation.get("element_id") == existing.get("element_id")
            )
            same_bbox = (
                citation.get("bbox")
                and citation.get("bbox") == existing.get("bbox")
            )
            left = _citation_text_signature(
                citation.get("search_text") or citation.get("text")
            )
            right = _citation_text_signature(
                existing.get("search_text") or existing.get("text")
            )
            shorter, longer = sorted((left, right), key=len)
            same_text = bool(
                len(shorter) >= 24
                and (
                    (shorter in longer and len(shorter) / max(len(longer), 1) >= 0.72)
                    or SequenceMatcher(None, left, right).ratio() >= 0.88
                )
            )
            if same_element or same_bbox or same_text:
                duplicate_index = index
                break
        if duplicate_index is None:
            unique.append(citation)
        elif _citation_precision(citation) > _citation_precision(unique[duplicate_index]):
            unique[duplicate_index] = citation
    return unique


# ====== 置信度计算 ======

def calculate_evidence_confidence(
    answer: str,
    citations: list,
    chunks: list,
    intent: str | None = None,
) -> float:
    """Estimate source support, never statistical answer correctness."""
    if not str(answer or "").strip():
        return 0.0
    valid_citations = [item for item in citations or [] if isinstance(item, dict)]
    if intent == "metadata":
        return 0.95 if valid_citations else 0.0
    if not valid_citations or not chunks:
        return 0.0

    grounded = 0
    for citation in valid_citations:
        source_id = str(citation.get("source_id") or "").upper()
        if not (source_id.startswith("S") and source_id[1:].isdigit()):
            continue
        index = int(source_id[1:]) - 1
        if not 0 <= index < len(chunks):
            continue
        citation_text = _normalize_locator_text(citation.get("text", ""))
        source_text = _normalize_locator_text(chunks[index].get("content", ""))
        if citation_text and (
            citation_text in source_text
            or SequenceMatcher(None, citation_text, source_text).ratio() >= 0.55
        ):
            grounded += 1

    grounding_ratio = grounded / len(valid_citations)
    citation_coverage_factor = 0.7 + 0.3 * min(len(valid_citations) / 2, 1.0)
    return round(grounding_ratio * citation_coverage_factor, 4)
