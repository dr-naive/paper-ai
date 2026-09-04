"""High-recall hybrid retrieval for multi-section paper questions."""

from __future__ import annotations

import math
import json
import logging
import re
import time
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import get_llm_client
from app.models.paper import Image, Section, Table, TableStructure
from app.rag.knowledge_base import get_knowledge_base
from app.rag.table_retrieval import get_exact_table_chunks

logger = logging.getLogger(__name__)

_REFERENTIAL = re.compile(r"这个|这种|该方法|上述|前面|刚才|它|其|this|that|it|above", re.I)
_COMPLEX = re.compile(
    r"比较|对比|区别|异同|分别|各自|关系|影响|原因|证据|跨章节|compare|difference|versus|\bvs\.?\b",
    re.I,
)
_STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "及", "对", "中", "有", "什么", "如何",
    "为什么", "论文", "本文", "请问", "进行", "the", "a", "an", "of", "to", "and",
    "is", "are", "what", "how", "why", "paper",
}


@dataclass(frozen=True)
class QueryPlan:
    intent: str
    channels: tuple[str, ...]
    top_k: int
    candidate_k: int
    comparison_queries: tuple[str, ...] = ()


def plan_query(question: str, intent: str = "general") -> QueryPlan:
    normalized = str(question or "")
    if re.search(r"表格|数据|数值|最高|最低|平均|(?:表|table)\s*\d+", normalized, re.I):
        intent = "table"
    elif re.search(r"图片|图像|图中|曲线|柱状|(?:图|figure)\s*\d+", normalized, re.I):
        intent = "image"
    elif _COMPLEX.search(normalized):
        intent = "comparison"
    top_k = dynamic_top_k(normalized, intent)
    channels = ("vector", "bm25")
    if intent == "table":
        channels = ("table_row", "table", "vector", "bm25")
    elif intent == "image":
        channels = ("image", "vector", "bm25")
    comparison = tuple(split_comparison_question(normalized)) if intent == "comparison" else ()
    return QueryPlan(intent, channels, top_k, min(40, max(20, top_k * 3)), comparison)


def tokenize(text: str) -> list[str]:
    """Tokenize Chinese with character bigrams and keep Latin technical terms."""
    normalized = str(text or "").lower()
    latin = re.findall(r"[a-z0-9][a-z0-9_.+-]*", normalized)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", normalized)
    chinese: list[str] = []
    for run in chinese_runs:
        chinese.extend(char for char in run if char not in _STOPWORDS)
        chinese.extend(run[index:index + 2] for index in range(len(run) - 1))
    return [token for token in latin + chinese if token and token not in _STOPWORDS]


def rewrite_standalone_question(question: str, history_context: str) -> str:
    """Resolve lightweight references without adding another model round trip."""
    question = question.strip()
    if not history_context or not _REFERENTIAL.search(question):
        return question
    previous = re.findall(r"用户:\s*(.+)", history_context)
    if not previous:
        return question
    return f"{previous[-1].strip()}；追问：{question}"


def dynamic_top_k(question: str, intent: str = "general") -> int:
    if intent == "comparison" or _COMPLEX.search(question):
        return 10
    if len(tokenize(question)) <= 8 and len(question) <= 32:
        return 4
    return 6


def split_comparison_question(question: str) -> list[str]:
    """Create two focused retrieval queries for common A/B comparisons."""
    patterns = (
        r"(?:比较|对比)\s*(.+?)\s*(?:和|与|及|跟|以及|vs\.?|versus)\s*(.+?)(?:的)?(?:区别|差异|异同|优缺点|表现|$)",
        r"(.+?)\s*(?:和|与|及|跟|以及|vs\.?|versus)\s*(.+?)(?:有何|有什么)?(?:区别|差异|异同)",
    )
    for pattern in patterns:
        match = re.search(pattern, question, re.I)
        if match:
            left, right = (part.strip(" ，。？?") for part in match.groups())
            if left and right and left != right:
                return [f"{left} 论文证据", f"{right} 论文证据"]
    return []


def _paragraphs(section: Section, max_chars: int = 900) -> list[dict[str, Any]]:
    content = "\n".join(
        line for line in str(section.content or "").splitlines()
        if not re.fullmatch(r"\s*(?:page\s*)?\d+\s*", line, re.I)
        and not re.match(
            r"^\s*(?:published as (?:a )?conference paper|"
            r"accepted (?:at|by)|arxiv preprint)\b",
            line,
            re.I,
        )
    ).strip()
    if not content:
        return []
    blocks = [part.strip() for part in re.split(r"\n\s*\n|(?<=[。！？.!?])\s+", content) if part.strip()]
    chunks: list[str] = []
    current = ""
    for block in blocks:
        if current and len(current) + len(block) > max_chars:
            chunks.append(current)
            current = block
        else:
            current = f"{current}\n{block}".strip()
    if current:
        chunks.append(current)
    return [{
        "content": chunk,
        "section": section.section_title,
        "section_id": str(getattr(section, "id", "")) or None,
        "page": section.start_page,
        "chunk_index": f"bm25-{getattr(section, 'id', section.order_index)}-{index}",
        "chunk_type": "text",
        "retrieval_method": "bm25",
    } for index, chunk in enumerate(chunks)]


def bm25_search(query: str, documents: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    if not documents:
        return []
    query_tokens = tokenize(query)
    tokenized = [tokenize(document.get("content", "")) for document in documents]
    document_frequency = Counter()
    for tokens in tokenized:
        document_frequency.update(set(tokens))
    average_length = sum(len(tokens) for tokens in tokenized) / max(len(tokenized), 1)
    scores: list[tuple[float, dict[str, Any]]] = []
    for document, tokens in zip(documents, tokenized):
        frequencies = Counter(tokens)
        score = 0.0
        for token in query_tokens:
            frequency = frequencies[token]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (len(documents) - document_frequency[token] + 0.5)
                / (document_frequency[token] + 0.5)
            )
            denominator = frequency + 1.5 * (
                1 - 0.75 + 0.75 * len(tokens) / max(average_length, 1)
            )
            score += inverse_frequency * frequency * 2.5 / denominator
        if score > 0:
            item = dict(document)
            item["bm25_score"] = round(score, 6)
            scores.append((score, item))
    scores.sort(key=lambda item: item[0], reverse=True)
    return [document for _score, document in scores[:top_k]]


def _chunk_key(chunk: dict[str, Any]) -> tuple[Any, ...]:
    if chunk.get("chunk_type") == "table" and chunk.get("table_number") is not None:
        return ("table", str(chunk["table_number"]))
    return (
        str(chunk.get("section") or ""),
        str(chunk.get("page") or ""),
        re.sub(r"\s+", "", str(chunk.get("content") or ""))[:180],
    )


def _normalized_evidence_text(value: Any) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(value or "").lower())


def _is_duplicate_evidence(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Detect the same physical/semantic evidence recalled by different channels."""
    left_element = str(left.get("element_id") or "")
    right_element = str(right.get("element_id") or "")
    if left_element and left_element == right_element:
        return True
    if str(left.get("page") or "") != str(right.get("page") or ""):
        return False
    left_text = _normalized_evidence_text(left.get("content"))
    right_text = _normalized_evidence_text(right.get("content"))
    if not left_text or not right_text:
        return False
    if (
        min(len(left_text), len(right_text)) >= 160
        and left_text[:160] == right_text[:160]
    ):
        return True
    shorter, longer = sorted((left_text, right_text), key=len)
    if len(shorter) >= 80 and shorter in longer:
        return len(shorter) / max(len(longer), 1) >= 0.72
    return (
        min(len(left_text), len(right_text)) >= 100
        and SequenceMatcher(None, left_text, right_text).ratio() >= 0.88
    )


def _evidence_precision(chunk: dict[str, Any], question: str) -> tuple[int, int, int]:
    numeric_question = bool(re.search(r"数值|指标|最高|最低|平均|准确率|F1|ACC", question, re.I))
    chunk_type = str(chunk.get("chunk_type") or "")
    structured_row = int(numeric_question and chunk_type == "table_row")
    physical = int(bool(chunk.get("element_id") and chunk.get("bbox")))
    structured = int(bool(chunk.get("table_id") or chunk.get("fields")))
    return structured_row, physical, structured


def deduplicate_evidence(
    chunks: list[dict[str, Any]],
    question: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Collapse cross-channel duplicates while retaining the most precise source."""
    unique: list[dict[str, Any]] = []
    for candidate in chunks:
        duplicate_index = next(
            (
                index for index, existing in enumerate(unique)
                if _is_duplicate_evidence(existing, candidate)
            ),
            None,
        )
        if duplicate_index is None:
            unique.append(candidate)
        elif _evidence_precision(candidate, question) > _evidence_precision(
            unique[duplicate_index], question
        ):
            unique[duplicate_index] = candidate
    return unique[:top_k]


class EvidenceReranker:
    """Deterministic query/chunk reranker applied after multi-channel recall."""

    def rerank(
        self,
        question: str,
        ranked_groups: list[list[dict[str, Any]]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        query_tokens = set(tokenize(question))
        candidates: dict[tuple[Any, ...], dict[str, Any]] = {}
        reciprocal_scores: Counter = Counter()
        for group in ranked_groups:
            for rank, chunk in enumerate(group, start=1):
                key = _chunk_key(chunk)
                candidates.setdefault(key, dict(chunk))
                reciprocal_scores[key] += 1 / (60 + rank)

        scored = []
        normalized_question = re.sub(r"\s+", "", question.lower())
        for key, chunk in candidates.items():
            text = f"{chunk.get('section', '')} {chunk.get('content', '')}"
            document_tokens = set(tokenize(text))
            overlap = len(query_tokens & document_tokens) / max(len(query_tokens), 1)
            phrase_bonus = 0.12 if normalized_question and normalized_question in re.sub(
                r"\s+", "", text.lower()
            ) else 0.0
            exact_bonus = 0.35 if chunk.get("retrieval_method") == "exact_table_number" else 0.0
            score = reciprocal_scores[key] + overlap * 0.8 + phrase_bonus + exact_bonus
            chunk["rerank_score"] = round(score, 6)
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _score, chunk in scored[:top_k]]


class SemanticReranker:
    """Model-based relevance and evidence-quality reranker with safe fallback."""

    async def rerank(
        self,
        question: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if len(candidates) <= top_k:
            return candidates
        summaries = "\n".join(
            f"C{index + 1}: {str(item.get('content') or '')[:500]}"
            for index, item in enumerate(candidates[:40])
        )
        prompt = (
            "你是论文证据重排器。按与问题的直接相关性、信息完整性、是否包含可核验数据排序；"
            "页眉页脚、出版声明和仅有关键词但不回答问题的内容应降权。"
            f"\n问题：{question}\n候选：\n{summaries}\n"
            f"只返回JSON：{{\"order\":[候选编号整数]}}，最多{top_k}项。"
        )
        try:
            response = await get_llm_client().agenerate(
                [prompt], json_mode=True, enable_thinking=False
            )
            payload = json.loads(response.generations[0][0].text.strip())
            indexes = [
                int(value) - 1 for value in payload.get("order", [])
                if str(value).isdigit() and 1 <= int(value) <= len(candidates)
            ]
            ordered = [candidates[index] for index in dict.fromkeys(indexes)]
            if ordered:
                return ordered[:top_k]
        except Exception:
            logger.warning("语义 reranker 失败，使用确定性重排结果", exc_info=True)
        return candidates[:top_k]


@dataclass
class HybridRetrievalResult:
    chunks: list[dict[str, Any]]
    standalone_question: str
    top_k: int
    second_pass: bool = False
    comparison_queries: list[str] | None = None
    rerank_ms: float = 0.0


class HybridPaperRetriever:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.reranker = EvidenceReranker()
        self.semantic_reranker = SemanticReranker()

    async def _section_documents(self, paper_id: str) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Section)
            .where(Section.paper_id == paper_id)
            .order_by(Section.order_index)
        )
        return [
            chunk
            for section in result.scalars().all()
            for chunk in _paragraphs(section)
        ]

    async def _recall(
        self,
        paper_id: str,
        query: str,
        documents: list[dict[str, Any]],
        candidate_k: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        vector = await get_knowledge_base().query(paper_id, query, top_k=candidate_k)
        keyword = bm25_search(query, documents, candidate_k)
        return vector, keyword

    async def _structured_documents(self, paper_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        table_result = await self.db.execute(
            select(Table, TableStructure)
            .join(TableStructure, TableStructure.table_id == Table.id)
            .where(Table.paper_id == paper_id)
        )
        table_rows = []
        for table, structure in table_result.all():
            for record in structure.row_records or []:
                table_rows.append({
                    "content": record.get("text", ""),
                    "section": table.caption or f"表{table.table_number}",
                    "page": record.get("page") or table.page_number,
                    "chunk_type": "table_row",
                    "table_id": str(table.id),
                    "section_id": str(table.section_id) if table.section_id else None,
                    "table_number": table.table_number,
                    "row_index": record.get("row_index"),
                    "fields": record.get("fields", []),
                    "retrieval_method": "structured_table_row",
                })
        image_result = await self.db.execute(
            select(Image).where(Image.paper_id == paper_id, Image.is_filtered.is_(False))
        )
        images = []
        for image in image_result.scalars().all():
            analysis = image.analysis_result or {}
            text = "\n".join(str(analysis.get(key) or "") for key in (
                "core_conclusion", "description", "qa_context", "key_data_points"
            ))
            if text.strip():
                images.append({
                    "content": text,
                    "section": f"图{image.image_index or ''}",
                    "page": image.page_number,
                    "chunk_type": "image",
                    "image_id": str(image.id),
                    "section_id": str(image.section_id) if image.section_id else None,
                    # Image stores do not currently persist a bbox (unlike
                    # DocumentElement/TableCell). Keep the optional locator
                    # field stable without assuming a model attribute that
                    # is absent in the current schema.
                    "bbox": list(getattr(image, "bbox", None) or []),
                    "retrieval_method": "structured_image",
                })
        return table_rows, images

    async def retrieve(
        self,
        paper_id: str,
        question: str,
        history_context: str = "",
        intent: str = "general",
    ) -> HybridRetrievalResult:
        standalone = rewrite_standalone_question(question, history_context)
        plan = plan_query(standalone, intent)
        top_k = plan.top_k
        candidate_k = plan.candidate_k
        documents = await self._section_documents(paper_id)
        table_rows, image_documents = await self._structured_documents(paper_id)
        exact = await get_exact_table_chunks(self.db, paper_id, standalone)
        vector, keyword = await self._recall(
            paper_id, standalone, documents, candidate_k
        )

        comparison_queries = list(plan.comparison_queries)
        comparison_groups: list[list[dict[str, Any]]] = []
        for focused_query in comparison_queries:
            focused_vector, focused_keyword = await self._recall(
                paper_id, focused_query, documents, max(6, top_k // 2)
            )
            comparison_groups.extend([focused_vector, focused_keyword])

        table_group = bm25_search(standalone, table_rows, candidate_k)
        image_group = bm25_search(standalone, image_documents, candidate_k)
        routed = {
            "table_row": table_group,
            "table": exact,
            "image": image_group,
            "vector": vector,
            "bm25": keyword,
        }
        groups = [routed[channel] for channel in plan.channels if channel in routed]
        groups.extend(comparison_groups)
        rerank_started = time.perf_counter()
        preliminary = self.reranker.rerank(standalone, groups, candidate_k)
        semantic = await self.semantic_reranker.rerank(
            standalone, preliminary, min(len(preliminary), top_k * 2)
        )
        chunks = deduplicate_evidence(semantic, standalone, top_k)
        rerank_ms = (time.perf_counter() - rerank_started) * 1000
        second_pass = self._needs_second_pass(chunks, top_k, comparison_queries)
        if second_pass:
            broad_query = self._broaden_query(standalone)
            broad_vector, broad_keyword = await self._recall(
                paper_id, broad_query, documents, candidate_k
            )
            second_rerank_started = time.perf_counter()
            preliminary = self.reranker.rerank(
                standalone, [*groups, broad_vector, broad_keyword], candidate_k
            )
            semantic = await self.semantic_reranker.rerank(
                standalone, preliminary, min(len(preliminary), top_k * 2)
            )
            chunks = deduplicate_evidence(semantic, standalone, top_k)
            rerank_ms += (time.perf_counter() - second_rerank_started) * 1000
        return HybridRetrievalResult(
            chunks=chunks,
            standalone_question=standalone,
            top_k=top_k,
            second_pass=second_pass,
            comparison_queries=comparison_queries,
            rerank_ms=round(rerank_ms, 3),
        )

    @staticmethod
    def _needs_second_pass(
        chunks: list[dict[str, Any]],
        top_k: int,
        comparison_queries: list[str],
    ) -> bool:
        if len(chunks) < min(top_k, 4):
            return True
        sections = {str(chunk.get("section") or "") for chunk in chunks}
        if comparison_queries and len(sections) < 2:
            return True
        return max((float(chunk.get("rerank_score", 0)) for chunk in chunks), default=0) < 0.08

    @staticmethod
    def _broaden_query(question: str) -> str:
        terms = list(dict.fromkeys(tokenize(question)))
        return " ".join(terms[:20]) or question
