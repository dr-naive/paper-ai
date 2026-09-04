"""Harness Tools: reading_assistant —— 阅读辅助 tool。

提供 2 个 tool:
- get_reading_progress: 聚合用户对该论文的历史问答/摘要/解读
- locate_term_definition: 基于 RAG 二次过滤,精确定位术语定义句

设计要点:
- get_reading_progress 需要 db 查 3 张表(QAPair/SummaryCache/InterpretCache)
- locate_term_definition 复用 HybridPaperRetriever 做一次检索,再用信号词 regex 二次过滤
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic.v1 import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import InterpretCache, SummaryCache  # noqa
from app.models.paper import QAPair

logger = logging.getLogger(__name__)

# 术语定义的信号词模式(中英双语,覆盖常见定义句式)
# 命中其中任一即认为是定义句,优先级高于普通检索结果
TERM_DEFINITION_PATTERNS = [
    # 中文信号词
    r"指的是",
    r"是指",
    r"定义为",
    r"是指代",
    r"被称为",
    r"称为",
    r"的意思是",
    r"表示",
    r"即",
    # 英文信号词
    r"is defined as",
    r"refers to",
    r"is called",
    r"is known as",
    r"is a ",
    r"are defined as",
    r"which is",
    r"denotes",
    r"means",
]


class GetReadingProgressInput(BaseModel):
    paper_id: str = Field(..., description="论文 ID")
    user_id: str = Field(..., description="用户 ID,用于查该用户的历史")


class LocateTermDefinitionInput(BaseModel):
    paper_id: str = Field(..., description="论文 ID")
    term: str = Field(..., description="要查定义的术语,如 'contrastive loss' 或 '注意力机制'")
    top_k: int = Field(5, description="检索候选句数量,默认5", ge=1, le=15)


async def _get_reading_progress_impl(db: AsyncSession, paper_id: str, user_id: str) -> str:
    """聚合用户对该论文的历史阅读进度。

    数据源:
    - QAPair: 历史问答(最近 N 条)
    - SummaryCache: 是否已生成摘要 + 摘要概览
    - InterpretCache: 是否已生成解读 + 解读类型
    """
    # 查最近 10 条 QA
    qa_result = await db.execute(
        select(QAPair)
        .where(QAPair.paper_id == paper_id)
        .order_by(QAPair.order_index.desc())
        .limit(10)
    )
    qa_pairs = qa_result.scalars().all()
    qa_list = [
        {
            "order_index": qa.order_index,
            "question": qa.question,
            "answer_preview": (qa.answer or "")[:150],
            "created_at": qa.created_at.isoformat() if qa.created_at else None,
        }
        for qa in reversed(qa_pairs)  # 反转让最早的在前
    ]

    # 查摘要
    summary_result = await db.execute(
        select(SummaryCache).where(
            SummaryCache.paper_id == paper_id, SummaryCache.user_id == user_id
        )
    )
    summary = summary_result.scalar_one_or_none()
    summary_info = None
    if summary:
        summary_info = {
            "generated_at": summary.generated_at.isoformat() if summary.generated_at else None,
            "has_overview": bool(summary.overview),
            "has_methodology": bool(summary.methodology),
            "has_experiments": bool(summary.experiments),
            "has_contributions": bool(summary.contributions),
        }

    # 查解读
    interpret_result = await db.execute(
        select(InterpretCache)
        .where(
            InterpretCache.paper_id == paper_id, InterpretCache.user_id == user_id
        )
    )
    interprets = interpret_result.scalars().all()
    interpret_info = [
        {
            "type": it.interpret_type,
            "generated_at": it.generated_at.isoformat() if it.generated_at else None,
        }
        for it in interprets
    ]

    return json.dumps(
        {
            "paper_id": paper_id,
            "user_id": user_id,
            "qa_count": len(qa_list),
            "qa_history": qa_list,
            "has_summary": summary_info is not None,
            "summary": summary_info,
            "has_interpret": len(interpret_info) > 0,
            "interprets": interpret_info,
            "is_first_read": len(qa_list) == 0 and summary_info is None and len(interpret_info) == 0,
        },
        ensure_ascii=False,
    )


async def _locate_term_definition_impl(
    db: AsyncSession, paper_id: str, term: str, top_k: int = 5
) -> str:
    """基于 RAG 二次过滤,精确定位术语定义句。

    流程:
    1. 用 HybridPaperRetriever 检索 top_k 个候选 chunk
    2. 用信号词 regex 扫描每个 chunk,找出包含定义句式的句子
    3. 优先返回命中信号词的句子,其次返回检索相关度高的句子

    若都没命中,返回最相关的 chunk 让 LLM 自行解释。
    """
    # 延迟导入,避免循环依赖
    from app.rag.hybrid_retrieval import HybridPaperRetriever

    retriever = HybridPaperRetriever(db)
    # retrieve 不接受 top_k 参数,内部由 plan_query 决定;
    # top_k 参数保留在 tool schema 里供未来扩展(目前忽略)
    result = await retriever.retrieve(paper_id, term, intent="general")
    chunks = result.chunks if hasattr(result, "chunks") else []

    if not chunks:
        return json.dumps(
            {"term": term, "definitions": [], "note": "未检索到相关内容"},
            ensure_ascii=False,
        )

    # 二次过滤:扫描每个 chunk,找包含信号词的句子
    definitions: list[dict[str, Any]] = []
    fallback_chunks: list[dict[str, Any]] = []

    # 编译信号词 regex(忽略大小写)
    pattern = re.compile("|".join(TERM_DEFINITION_PATTERNS), re.IGNORECASE)

    for chunk in chunks:
        content = chunk.get("content", "")
        section = chunk.get("section", "")
        page = chunk.get("page")
        source_id = chunk.get("source_id", "")

        # 按句切分(中英文句号/问号/感叹号)
        sentences = re.split(r"[。.!?！？\n]+", content)
        for sent in sentences:
            sent = sent.strip()
            # 句子里必须包含 term 本身(避免无关句子)
            if not sent or term.lower() not in sent.lower():
                continue
            if pattern.search(sent):
                definitions.append({
                    "sentence": sent,
                    "section": section,
                    "page": page,
                    "source_id": source_id,
                    "match_type": "signal_word",
                })

        # 同时保留 chunk 作为 fallback
        fallback_chunks.append({
            "content_preview": content[:300],
            "section": section,
            "page": page,
            "source_id": source_id,
        })

    return json.dumps(
        {
            "term": term,
            "definitions": definitions[:3],  # 最多返回 3 个定义句
            "fallback_chunks": fallback_chunks[:2],  # 没命中信号词时用
            "has_definition": len(definitions) > 0,
        },
        ensure_ascii=False,
    )


def make_reading_assistant_tools(db: AsyncSession) -> list:
    """创建 reading_assistant skill 的全部 tool,db 通过闭包注入。"""
    # user_id 通过 tool 参数传入(因为 lead_agent 不一定知道 user_id,让 LLM 从上下文拿)
    async def get_reading_progress(paper_id: str, user_id: str) -> str:
        """获取用户对指定论文的阅读进度。

        返回历史问答、已生成摘要、已生成解读。用于判断用户是否首次阅读、
        之前问过什么、是否已生成摘要/解读。
        """
        return await _get_reading_progress_impl(db, paper_id, user_id)

    async def locate_term_definition(paper_id: str, term: str, top_k: int = 5) -> str:
        """精确定位术语在论文中的定义句。

        基于 RAG 检索 + 信号词二次过滤(如"定义为""refers to""is called"等)。
        用于解释论文里的专业术语,返回带出处的定义句。
        """
        return await _locate_term_definition_impl(db, paper_id, term, top_k)

    return [
        StructuredTool.from_function(
            get_reading_progress,
            name="get_reading_progress",
            description=(
                "查询用户对某论文的历史阅读进度。"
                "返回历史问答、是否已生成摘要、是否已生成解读。"
                "用于回答'我之前问过什么''读到哪了''我是不是第一次读这篇'。"
                "输入:paper_id,user_id。"
            ),
            args_schema=GetReadingProgressInput,
            coroutine=get_reading_progress,
        ),
        StructuredTool.from_function(
            locate_term_definition,
            name="locate_term_definition",
            description=(
                "精确定位术语在论文中的定义句(基于 RAG 二次过滤)。"
                "用于解释论文里的专业术语,如'contrastive loss 是什么意思'。"
                "返回带出处的定义句(章节/页码)。"
                "输入:paper_id,term=术语,top_k=候选句数。"
            ),
            args_schema=LocateTermDefinitionInput,
            coroutine=locate_term_definition,
        ),
    ]
