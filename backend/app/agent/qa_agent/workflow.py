"""Unified, event-driven QA workflow used by streaming and blocking APIs."""

from __future__ import annotations

import logging
import math
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.qa_helpers import (
    build_deterministic_citations,
    calculate_evidence_confidence,
    detect_metadata_intent,
)
from app.llm.client import get_llm_client
from app.models.chat import ChatMessage, ChatSession
from app.models.paper import Paper
from app.rag.hybrid_retrieval import HybridPaperRetriever
from app.rag.evidence_review import review_evidence

logger = logging.getLogger(__name__)

WorkflowEvent = tuple[str, dict[str, Any]]


@dataclass
class QAWorkflowState:
    session_id: str
    user_id: str
    question: str
    enable_thinking: bool = False
    persist_message: bool = True
    paper_id: str = ""
    paper_metadata: dict[str, Any] = field(default_factory=dict)
    history_context: str = ""
    intent: str = "general"
    metadata_field: Optional[str] = None
    chunks: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    evidence_confidence: float = 0.0
    message_id: str = ""
    sources: list[str] = field(default_factory=list)
    error_stage: str = ""
    retrieval_query: str = ""
    retrieval_top_k: int = 0
    retrieval_second_pass: bool = False
    evidence_issues: list[str] = field(default_factory=list)
    deterministic_calculation: str = ""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace: dict[str, Any] = field(default_factory=dict)


def build_answer_prompt(
    question: str,
    chunks: list,
    history_context: str,
    deterministic_calculation: str = "",
) -> str:
    context_parts = []
    for index, chunk in enumerate(chunks):
        table_label = "[表格]\n" if chunk.get("chunk_type") == "table" else ""
        context_parts.append(
            f"[来源 S{index + 1}]\n"
            f"[章节 {chunk.get('section', '未知章节')}]\n"
            f"{table_label}{chunk.get('content', '')}"
        )
    context = "\n\n---\n\n".join(context_parts)
    history = f"\n【历史对话】\n{history_context}\n" if history_context else ""
    calculation = (
        f"\n【程序核算结果】\n{deterministic_calculation}\n"
        if deterministic_calculation else ""
    )
    return f"""
请只依据下方论文资料回答用户问题。

要求：
1. 推理过程和最终回答均使用简体中文。专业术语、模型名称、变量、公式和通用缩写可保留英文；英文术语首次出现时，适合的情况下补充中文含义。
2. 即使用户问题、历史对话或论文资料包含英文，也不要因此切换为整段英文推理或回答。
3. 直接输出 Markdown 正文，不要输出 JSON，不要写“答案：”。
4. 回答准确、有条理；论文未提及时明确说明，不得自行补全。
5. 每个关键结论后必须标注对应来源编号，如 [S1]、[S2]；只能使用已提供的来源编号。
6. 段落之间空一行，并列内容分行；比较数据适合时使用 Markdown 表格。
7. 表格数据必须逐项核对，缺失值写“-”，不要推测。
{history}
{calculation}
【用户问题】
{question}

【论文资料】
{context}
""".strip()


class UnifiedQAWorkflow:
    """A small node graph that preserves token-level streaming events."""

    START = "load_context"
    END = "__end__"

    def __init__(
        self,
        state: QAWorkflowState,
        db: Optional[AsyncSession] = None,
    ):
        self.state = state
        self.db = db
        self._trace_started_at = time.perf_counter()
        self._reasoning_parts: list[str] = []
        self.state.trace = {
            "trace_id": self.state.trace_id,
            "status": "running",
            "stage_timings_ms": {},
            "intent_ms": 0.0,
            "retrieval_ms": 0.0,
            "rerank_ms": 0.0,
            "first_token_ms": None,
            "thinking_tokens": 0,
            "answer_tokens": 0,
            "token_count_type": "estimated",
            "total_ms": 0.0,
            "model_calls": 0,
            "citation_count": 0,
            "retry_count": 0,
            "failure_stage": None,
        }
        self.visited_nodes: list[str] = []
        self._nodes = {
            "load_context": self._load_context,
            "classify_intent": self._classify_intent,
            "retrieve_evidence": self._retrieve_evidence,
            "evaluate_evidence": self._evaluate_evidence,
            "answer_without_evidence": self._answer_without_evidence,
            "generate_answer": self._generate_answer,
            "organize_citations": self._organize_citations,
            "persist_message": self._persist_message,
            "finalize": self._finalize,
        }
        self._edges = {
            "load_context": "classify_intent",
            "classify_intent": "retrieve_evidence",
            "retrieve_evidence": "evaluate_evidence",
            "answer_without_evidence": "persist_message",
            "generate_answer": "organize_citations",
            "organize_citations": "persist_message",
            "persist_message": "finalize",
            "finalize": self.END,
        }

    @classmethod
    def graph_definition(cls) -> dict[str, Any]:
        return {
            "start": cls.START,
            "end": cls.END,
            "nodes": [
                "load_context",
                "classify_intent",
                "retrieve_evidence",
                "evaluate_evidence",
                "answer_without_evidence",
                "generate_answer",
                "organize_citations",
                "persist_message",
                "finalize",
            ],
            "edges": [
                ("load_context", "classify_intent"),
                ("classify_intent", "retrieve_evidence"),
                ("retrieve_evidence", "evaluate_evidence"),
                ("evaluate_evidence", "generate_answer", "有证据"),
                ("evaluate_evidence", "answer_without_evidence", "无证据"),
                ("generate_answer", "organize_citations"),
                ("organize_citations", "persist_message"),
                ("answer_without_evidence", "persist_message"),
                ("persist_message", "finalize"),
                ("finalize", cls.END),
            ],
        }

    async def stream(self) -> AsyncIterator[WorkflowEvent]:
        node_name = self.START
        while node_name != self.END:
            self.visited_nodes.append(node_name)
            logger.info(
                "QA 节点开始 node=%s session_id=%s",
                node_name,
                self.state.session_id,
            )
            node_started_at = time.perf_counter()
            try:
                async for event in self._nodes[node_name]():
                    yield event
            except Exception:
                self.state.error_stage = node_name
                self.state.trace["status"] = "failed"
                self.state.trace["failure_stage"] = node_name
                self.state.trace["total_ms"] = round(
                    (time.perf_counter() - self._trace_started_at) * 1000, 3
                )
                logger.exception(
                    "QA 节点失败 node=%s session_id=%s",
                    node_name,
                    self.state.session_id,
                )
                yield "error", {
                    "stage": node_name,
                    "message": self._node_error_message(node_name),
                }
                return
            finally:
                elapsed_ms = round((time.perf_counter() - node_started_at) * 1000, 3)
                self.state.trace["stage_timings_ms"][node_name] = elapsed_ms
                if node_name == "classify_intent":
                    self.state.trace["intent_ms"] = elapsed_ms
                elif node_name == "retrieve_evidence":
                    self.state.trace["retrieval_ms"] = elapsed_ms
            node_name = self._next_node(node_name)

    def _next_node(self, node_name: str) -> str:
        if node_name == "evaluate_evidence":
            return "generate_answer" if self.state.chunks else "answer_without_evidence"
        return self._edges[node_name]

    async def _load_context(self) -> AsyncIterator[WorkflowEvent]:
        yield "status", {"stage": "loading_context", "message": "正在读取论文与对话"}
        if self.state.paper_id and self.state.paper_metadata:
            return
        if self.db is None:
            # Preloaded analysis callers may intentionally provide only chunks.
            return

        session_result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == self.state.session_id,
                ChatSession.user_id == self.state.user_id,
            )
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            raise LookupError("会话不存在")

        paper_result = await self.db.execute(select(Paper).where(Paper.id == session.paper_id))
        paper = paper_result.scalar_one_or_none()
        if paper is None:
            raise LookupError("论文不存在")

        history_result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == self.state.session_id)
            .order_by(ChatMessage.order_index)
        )
        history_messages = history_result.scalars().all()
        self.state.paper_id = str(session.paper_id)
        self.state.history_context = "\n\n".join(
            f"用户: {message.question}\nAI: {message.answer}"
            for message in history_messages[-5:]
        )
        self.state.paper_metadata = {
            "title": paper.title or "",
            "authors": paper.authors or "",
            "abstract": paper.abstract or "",
            "keywords": paper.keywords or [],
            "venue": getattr(paper, "venue", "") or "",
            "publication_year": getattr(paper, "publication_year", "") or "",
            "doi": getattr(paper, "doi", "") or "",
        }

    async def _classify_intent(self) -> AsyncIterator[WorkflowEvent]:
        yield "status", {"stage": "understanding", "message": "正在理解问题"}
        question = self.state.question
        self.state.metadata_field = detect_metadata_intent(question)
        if self.state.metadata_field:
            self.state.intent = "metadata"
        elif re.search(r"表格|(?:表|table)\s*\d+", question, re.IGNORECASE):
            self.state.intent = "table"
        elif re.search(r"图片|图像|插图|(?:图|figure)\s*\d+", question, re.IGNORECASE):
            self.state.intent = "image"
        elif re.search(r"比较|对比|区别|difference|compare", question, re.IGNORECASE):
            self.state.intent = "comparison"
        else:
            self.state.intent = "general"

    async def _retrieve_evidence(self) -> AsyncIterator[WorkflowEvent]:
        yield "status", {"stage": "retrieving", "message": "正在检索论文"}
        if self.state.chunks:
            return
        if self.state.metadata_field:
            metadata = self.state.paper_metadata
            self.state.chunks = [{
                "section": "论文元数据",
                "content": "\n".join([
                    f"标题：{metadata.get('title') or '-'}",
                    f"作者：{metadata.get('authors') or '-'}",
                    f"摘要：{metadata.get('abstract') or '-'}",
                    f"关键词：{'、'.join(metadata.get('keywords') or []) or '-'}",
                    f"期刊或会议：{metadata.get('venue') or '-'}",
                    f"发表年份：{metadata.get('publication_year') or '-'}",
                    f"DOI：{metadata.get('doi') or '-'}",
                ]),
                "chunk_type": "metadata",
            }]
            return
        if self.db is None:
            return

        retrieval = await HybridPaperRetriever(self.db).retrieve(
            self.state.paper_id,
            self.state.question,
            self.state.history_context,
            self.state.intent,
        )
        self.state.chunks = retrieval.chunks
        self.state.retrieval_query = retrieval.standalone_question
        self.state.retrieval_top_k = retrieval.top_k
        self.state.retrieval_second_pass = retrieval.second_pass
        self.state.trace["rerank_ms"] = retrieval.rerank_ms

    async def _evaluate_evidence(self) -> AsyncIterator[WorkflowEvent]:
        review = review_evidence(
            self.state.question, self.state.chunks, self.state.intent
        )
        self.state.chunks = review.chunks
        self.state.evidence_issues = review.issues
        self.state.deterministic_calculation = review.calculation
        yield "status", {
            "stage": "evaluating_evidence",
            "message": "正在检查检索证据",
            "source_count": len(self.state.chunks),
            "coverage": review.coverage,
            "issues": review.issues,
        }

    async def _answer_without_evidence(self) -> AsyncIterator[WorkflowEvent]:
        self.state.answer = "未在论文中找到相关内容，请尝试换一种问法。"
        self.state.citations = []
        self.state.evidence_confidence = 0.0
        yield "answer_delta", {"text": self.state.answer}

    async def _generate_answer(self) -> AsyncIterator[WorkflowEvent]:
        yield "status", {
            "stage": "generating",
            "message": "正在组织回答",
            "source_count": len(self.state.chunks),
        }
        prompt = build_answer_prompt(
            self.state.question,
            self.state.chunks,
            self.state.history_context,
            self.state.deterministic_calculation,
        )
        answer_parts: list[str] = []
        reasoning_started = False
        reasoning_finished = False
        self.state.trace["model_calls"] += 1
        async for content_kind, delta in get_llm_client().astream_content(
            prompt,
            enable_thinking=self.state.enable_thinking,
        ):
            if content_kind == "reasoning":
                if self.state.trace["first_token_ms"] is None:
                    self.state.trace["first_token_ms"] = round(
                        (time.perf_counter() - self._trace_started_at) * 1000, 3
                    )
                reasoning_started = True
                self._reasoning_parts.append(delta)
                yield "reasoning_delta", {"text": delta}
                continue
            if self.state.trace["first_token_ms"] is None:
                self.state.trace["first_token_ms"] = round(
                    (time.perf_counter() - self._trace_started_at) * 1000, 3
                )
            if reasoning_started and not reasoning_finished:
                reasoning_finished = True
                yield "reasoning_done", {}
            answer_parts.append(delta)
            yield "answer_delta", {"text": delta}
        if reasoning_started and not reasoning_finished:
            yield "reasoning_done", {}
        self.state.answer = "".join(answer_parts).strip()
        self.state.trace["thinking_tokens"] = _estimate_tokens(
            "".join(self._reasoning_parts)
        )
        self.state.trace["answer_tokens"] = _estimate_tokens(self.state.answer)
        if not self.state.answer:
            raise RuntimeError("模型未返回回答内容")

    async def _organize_citations(self) -> AsyncIterator[WorkflowEvent]:
        yield "status", {"stage": "organizing_citations", "message": "正在整理引用"}
        self.state.citations = build_deterministic_citations(
            self.state.answer,
            self.state.chunks,
        )
        self.state.sources = [
            str(item.get("section") or "") for item in self.state.citations
        ]
        self.state.evidence_confidence = calculate_evidence_confidence(
            self.state.answer,
            self.state.citations,
            self.state.chunks,
            self.state.intent,
        )
        self.state.trace["citation_count"] = len(self.state.citations)

    async def _persist_message(self) -> AsyncIterator[WorkflowEvent]:
        yield "status", {"stage": "persisting", "message": "正在保存回答"}
        if not self.state.persist_message:
            return
        if self.db is None:
            raise RuntimeError("保存回答时缺少数据库会话")
        session_result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == self.state.session_id,
                ChatSession.user_id == self.state.user_id,
            )
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            raise LookupError("会话不存在")
        message_count = await self.db.execute(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == self.state.session_id)
        )
        order_index = message_count.scalar() or 0
        message = ChatMessage(
            session_id=self.state.session_id,
            order_index=order_index + 1,
            question=self.state.question,
            answer=self.state.answer,
            citations=self.state.citations,
            follow_up_questions=[],
            confidence=self.state.evidence_confidence,
        )
        self.db.add(message)
        if order_index == 0:
            session.title = self.state.question[:20] + (
                "..." if len(self.state.question) > 20 else ""
            )
            session.updated_at = datetime.utcnow()
        await self.db.flush()
        self.state.message_id = str(message.id)
        await self.db.commit()

    async def _finalize(self) -> AsyncIterator[WorkflowEvent]:
        self.state.trace["status"] = "completed"
        self.state.trace["total_ms"] = round(
            (time.perf_counter() - self._trace_started_at) * 1000, 3
        )
        yield "citations", {"items": self.state.citations}
        yield "done", {
            "message_id": self.state.message_id,
            "intent": self.state.intent,
            "sources": self.state.sources,
            "evidence_confidence": self.state.evidence_confidence,
            "confidence": self.state.evidence_confidence,
            "confidence_type": "evidence_support",
            "follow_up_pending": bool(self.state.message_id),
            "retrieval": {
                "query": self.state.retrieval_query or self.state.question,
                "top_k": self.state.retrieval_top_k or len(self.state.chunks),
                "second_pass": self.state.retrieval_second_pass,
            },
            "nodes": self.visited_nodes,
            "trace_id": self.state.trace_id,
            "trace": self.state.trace,
        }

    @staticmethod
    def _node_error_message(node_name: str) -> str:
        messages = {
            "load_context": "读取论文与对话失败",
            "classify_intent": "理解问题失败",
            "retrieve_evidence": "检索论文失败",
            "evaluate_evidence": "检查检索证据失败",
            "generate_answer": "生成回答失败",
            "organize_citations": "整理引用失败",
            "persist_message": "保存回答失败",
        }
        return messages.get(node_name, "回答处理失败")


def _estimate_tokens(text: str) -> int:
    """Network-free estimate when streaming APIs do not return usage metadata."""
    if not text:
        return 0
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_words = re.findall(r"[A-Za-z0-9_]+", text)
    punctuation = re.findall(r"[^\w\s\u4e00-\u9fff]", text)
    latin_tokens = sum(max(1, math.ceil(len(word) / 4)) for word in latin_words)
    return chinese + latin_tokens + math.ceil(len(punctuation) / 2)


async def run_preloaded_qa_workflow(
    *,
    paper_id: str,
    question: str,
    chunks: list[dict[str, Any]],
    paper_metadata: Optional[dict[str, Any]] = None,
    history_context: str = "",
    enable_thinking: bool = False,
) -> dict[str, Any]:
    """Compatibility entry point for analysis APIs with pre-retrieved evidence."""
    state = QAWorkflowState(
        session_id="",
        user_id="",
        paper_id=paper_id,
        question=question,
        chunks=list(chunks),
        paper_metadata=paper_metadata or {},
        history_context=history_context,
        enable_thinking=enable_thinking,
        persist_message=False,
    )
    workflow = UnifiedQAWorkflow(state)
    async for _event, _payload in workflow.stream():
        pass
    return {
        "answer": state.answer,
        "intent": state.intent,
        "sources": state.sources,
        "citations": state.citations,
        "follow_up_questions": [],
        "intent_confidence": 1.0 if state.intent == "metadata" else 0.8,
        "evidence_confidence": state.evidence_confidence,
        "confidence": state.evidence_confidence,
        "confidence_type": "evidence_support",
        "nodes": workflow.visited_nodes,
    }
