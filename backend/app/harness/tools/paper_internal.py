"""paper_internal skill 的 tool 集合。

封装"论文内部信息查询"相关 6 个能力,作为 agent 与现有 API 共用的原子接口。
所有 tool 通过 `make_paper_internal_tools(db)` 工厂创建,db 由闭包注入。

设计原则:
- 复用现有 RAG 实现(hybrid_retrieval / table_retrieval / evidence_review),不重写
- 行为与现有 paper_analysis.ask_question / enhanced_graph 节点等价,只是入口统一
- tool docstring 详细(这是 LLM 选择 tool 的依据)
- 输入 schema 干净,只暴露业务参数,paper_id 等通过闭包/参数注入
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from langchain_core.tools import StructuredTool
# LangChain Core 仍走 pydantic v1 兼容层,args_schema 必须用 v1 的 BaseModel
from pydantic.v1 import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper, Section
from app.rag.evidence_review import review_evidence
from app.rag.hybrid_retrieval import HybridPaperRetriever
from app.rag.table_retrieval import (
    extract_table_numbers,
    get_exact_table_chunks,
    table_to_chunk,
)

logger = logging.getLogger(__name__)


# ============================================================
# 输入 schema 定义(LLM 看到的 tool 参数)
# ============================================================

class GetPaperMetadataInput(BaseModel):
    """获取论文元数据(标题/作者/摘要/年份/DOI 等)。"""
    paper_id: str = Field(..., description="论文 ID,UUID 格式")


class ListPaperSectionsInput(BaseModel):
    """列出论文的章节大纲。"""
    paper_id: str = Field(..., description="论文 ID,UUID 格式")
    include_summary: bool = Field(
        False,
        description="是否包含每章的 LLM 摘要。默认 False,只返回标题与定位信息。设为 True 会增大返回体积。",
    )


class SearchPaperContentInput(BaseModel):
    """对论文正文做混合检索(向量 + BM25 + 表格行 + 图片)。"""
    paper_id: str = Field(..., description="论文 ID,UUID 格式")
    query: str = Field(..., description="检索问题或关键词,自然语言即可")
    intent: str = Field(
        "general",
        description="问题类型,影响检索通道与 top_k:general/table/image/comparison。默认 general,带表号的用 table,跨章节对比用 comparison。",
    )
    top_k: Optional[int] = Field(
        None,
        description="返回的片段数量上限。不传则由系统按问题复杂度动态决定(通常 4-10)。",
    )


class LookupTableDataInput(BaseModel):
    """精确查指定编号的表格数据(从关系库直查,不走 RAG)。"""
    paper_id: str = Field(..., description="论文 ID,UUID 格式")
    table_number: int = Field(
        ...,
        description="表格编号,如论文里的'表3'就传 3。如不确定编号,改用 search_paper_content。",
    )


class ComputeOverTablesInput(BaseModel):
    """基于论文表格做确定性算术(最大/最小/平均值)。"""
    paper_id: str = Field(..., description="论文 ID,UUID 格式")
    question: str = Field(
        ...,
        description="算术问题,需包含表号与运算信号词。例:'表3中哪个方法的F1最高'、'表4里各项的平均延迟'。",
    )


class ExportCitationFormatInput(BaseModel):
    """导出论文引用格式(BibTeX/GB-T 7714 等)。"""
    paper_id: str = Field(..., description="论文 ID,UUID 格式")
    format: str = Field(
        "bibtex",
        description="引用格式:bibtex(LaTeX)/gbt7714(国标)/endnote/ris。默认 bibtex。",
    )


# ============================================================
# 内部辅助函数(纯函数,不暴露给 LLM)
# ============================================================

def _format_authors(authors: Any) -> str:
    """把 authors 字段统一成逗号分隔字符串。"""
    if not authors:
        return ""
    if isinstance(authors, list):
        return ", ".join(str(a).strip() for a in authors if a)
    return str(authors).strip()


def _format_bibtex(paper: Paper) -> str:
    """生成 BibTeX 引用条目。"""
    # BibTeX key 取第一作者姓 + 年份
    authors = _format_authors(paper.authors)
    first_author = authors.split(",")[0].split()[-1] if authors else "unknown"
    year = paper.publication_year or "nd"
    key = f"{first_author.lower()}{year}"

    lines = [f"@article{{{key},"]
    if paper.title:
        lines.append(f"  title = {{{paper.title}}},")
    if authors:
        lines.append(f"  author = {{{authors}}},")
    if paper.venue:
        lines.append(f"  journal = {{{paper.venue}}},")
    if paper.publication_year:
        lines.append(f"  year = {{{paper.publication_year}}},")
    if paper.doi:
        lines.append(f"  doi = {{{paper.doi}}},")
    lines.append("}")
    return "\n".join(lines)


def _format_gbt7714(paper: Paper) -> str:
    """生成 GB-T 7714 国标引用格式。"""
    parts = []
    if _format_authors(paper.authors):
        parts.append(_format_authors(paper.authors))
    if paper.title:
        parts.append(f"{paper.title}")
    if paper.venue:
        parts.append(f"{paper.venue}")
    if paper.publication_year:
        parts.append(f"{paper.publication_year}")
    return ". ".join(parts) + "." if parts else ""


def _format_endnote(paper: Paper) -> str:
    """生成 EndNote 格式。"""
    lines = [
        "%0 Journal Article",
        f"%T {paper.title}" if paper.title else "",
        f"%A {_format_authors(paper.authors)}" if paper.authors else "",
        f"%J {paper.venue}" if paper.venue else "",
        f"%D {paper.publication_year}" if paper.publication_year else "",
        f"%R {paper.doi}" if paper.doi else "",
    ]
    return "\n".join(line for line in lines if line)


def _format_ris(paper: Paper) -> str:
    """生成 RIS 格式。"""
    lines = ["TY  - JOUR"]
    if paper.title:
        lines.append(f"TI  - {paper.title}")
    if _format_authors(paper.authors):
        for author in _format_authors(paper.authors).split(","):
            author = author.strip()
            if author:
                lines.append(f"AU  - {author}")
    if paper.venue:
        lines.append(f"JO  - {paper.venue}")
    if paper.publication_year:
        lines.append(f"PY  - {paper.publication_year}")
    if paper.doi:
        lines.append(f"DO  - {paper.doi}")
    lines.append("ER  - ")
    return "\n".join(lines)


# ============================================================
# Tool 工厂
# ============================================================

async def _get_paper_metadata_impl(db: AsyncSession, paper_id: str) -> str:
    """get_paper_metadata 的实现:查 Paper 表返回元数据 JSON。"""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalars().first()
    if not paper:
        return json.dumps({"error": f"未找到论文: {paper_id}"}, ensure_ascii=False)

    # 字段映射沿用 enhanced_graph.answer_metadata 的语义
    metadata = {
        "title": paper.title,
        "authors": _format_authors(paper.authors),
        "abstract": (paper.abstract or "")[:500],  # 摘要过长截断,LLM 不需要全文
        "keywords": paper.keywords or [],
        "venue": paper.venue,
        "publication_year": paper.publication_year,
        "doi": paper.doi,
        "research_area": paper.research_area,
        "citation_count": paper.citation_count,
    }
    return json.dumps(metadata, ensure_ascii=False)


async def _list_paper_sections_impl(
    db: AsyncSession, paper_id: str, include_summary: bool = False
) -> str:
    """list_paper_sections 的实现:查 Section 表返回章节大纲。"""
    result = await db.execute(
        select(Section)
        .where(Section.paper_id == paper_id)
        .order_by(Section.order_index)
    )
    sections = result.scalars().all()
    if not sections:
        return json.dumps({"error": f"未找到章节: {paper_id}"}, ensure_ascii=False)

    outline = []
    for section in sections:
        item: dict[str, Any] = {
            "section_id": section.id,
            "order_index": section.order_index,
            "title": section.section_title,
            "start_page": section.start_page,
            "table_count": len(section.tables or []),
            "figure_count": len(section.figures or []),
        }
        # 字数估算(粗略,够 LLM 感知章节体量)
        content = str(section.content or "")
        item["approx_word_count"] = len(content)
        if include_summary and section.summary:
            item["summary"] = section.summary
        outline.append(item)
    return json.dumps({"sections": outline, "total": len(outline)}, ensure_ascii=False)


async def _search_paper_content_impl(
    db: AsyncSession,
    paper_id: str,
    query: str,
    intent: str = "general",
    top_k: Optional[int] = None,
) -> str:
    """search_paper_content 的实现:复用 HybridPaperRetriever。"""
    retriever = HybridPaperRetriever(db)
    # HybridPaperRetriever.retrieve 内部会按 intent 动态决定 top_k,
    # 这里只在用户显式指定时覆盖(通过裁剪结果实现,不改 retriever 内部)
    result = await retriever.retrieve(
        paper_id=paper_id,
        question=query,
        history_context="",
        intent=intent,
    )
    chunks = result.chunks
    if top_k is not None and top_k > 0:
        chunks = chunks[:top_k]

    # 给每个 chunk 加 S 编号,与 enhanced_graph.build_deterministic_citations 对齐
    # 保留全部字段(content 截断防过长),供 citation 溯源使用
    serialized = []
    for index, chunk in enumerate(chunks, start=1):
        item = dict(chunk)  # 保留原始全部字段(element_id/bbox/table_number 等)
        item["source_id"] = f"S{index}"
        # content 截断,防止单 chunk 过长拖累 LLM 上下文
        item["content"] = (chunk.get("content") or "")[:1000]
        serialized.append(item)
    return json.dumps(
        {
            "chunks": serialized,
            "standalone_question": result.standalone_question,
            "top_k": result.top_k,
            "second_pass": result.second_pass,
        },
        ensure_ascii=False,
    )


async def _lookup_table_data_impl(
    db: AsyncSession, paper_id: str, table_number: int
) -> str:
    """lookup_table_data 的实现:复用 table_retrieval 的 table_to_chunk。"""
    # 直接按 table_number 查 Table 表,不走 question 解析
    from app.models.paper import Table

    result = await db.execute(
        select(Table).where(
            Table.paper_id == paper_id,
            Table.table_number == table_number,
        )
    )
    table = result.scalars().first()
    if not table:
        return json.dumps(
            {"error": f"未找到表 {table_number}"}, ensure_ascii=False
        )

    chunk = table_to_chunk(table)
    return json.dumps(
        {
            "table_number": table.table_number,
            "caption": table.caption,
            "page": table.page_number,
            "content": chunk["content"],
            "analysis": table.analysis_result or {},
        },
        ensure_ascii=False,
    )


async def _compute_over_tables_impl(
    db: AsyncSession, paper_id: str, question: str
) -> str:
    """compute_over_tables 的实现:复用 review_evidence 的 _numeric_calculation。"""
    # 1. 自动从 question 解析表号
    table_numbers = extract_table_numbers(question)
    if not table_numbers:
        return json.dumps(
            {"error": "问题中未识别到表号(如'表3')", "question": question},
            ensure_ascii=False,
        )

    # 2. 取对应表格 chunks(走 get_exact_table_chunks 复用现有逻辑)
    chunks = await get_exact_table_chunks(db, paper_id, question)

    if not chunks:
        return json.dumps(
            {"error": f"未找到表 {table_numbers}", "question": question},
            ensure_ascii=False,
        )

    # 3. 调 review_evidence,从 .calculation 字段拿确定性算术结果
    review = review_evidence(question=question, chunks=chunks, intent="table")
    if not review.calculation:
        return json.dumps(
            {
                "calculation": "",
                "hint": "问题未命中算术信号词(最高/最低/平均),或表格中无可参与计算的数值字段。",
                "table_numbers": table_numbers,
            },
            ensure_ascii=False,
        )
    return json.dumps(
        {"calculation": review.calculation, "table_numbers": table_numbers},
        ensure_ascii=False,
    )


async def _export_citation_format_impl(
    db: AsyncSession, paper_id: str, format: str = "bibtex"
) -> str:
    """export_citation_format 的实现:查元数据 + 套模板。"""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalars().first()
    if not paper:
        return json.dumps({"error": f"未找到论文: {paper_id}"}, ensure_ascii=False)

    formatters = {
        "bibtex": _format_bibtex,
        "gbt7714": _format_gbt7714,
        "endnote": _format_endnote,
        "ris": _format_ris,
    }
    formatter = formatters.get(format.lower())
    if not formatter:
        return json.dumps(
            {"error": f"不支持的格式: {format}", "supported": list(formatters.keys())},
            ensure_ascii=False,
        )
    return json.dumps(
        {"format": format.lower(), "citation": formatter(paper)},
        ensure_ascii=False,
    )


# ============================================================
# 工厂入口
# ============================================================

def make_paper_internal_tools(db: AsyncSession) -> list:
    """创建 paper_internal skill 的全部 tool,db 通过闭包注入。

    Args:
        db: SQLAlchemy 异步 session,生命周期由调用方管理

    Returns:
        LangChain BaseTool 实例列表,可直接传给 agent / ToolNode / .ainvoke()
    """
    async def get_paper_metadata(paper_id: str) -> str:
        """获取论文元数据(标题/作者/摘要/年份/DOI 等)。

        适用场景:用户问"作者是谁""标题是什么""发表在哪""DOI 是多少"等元数据类问题。
        不适用:正文内容问题(用 search_paper_content)、表格数据(用 lookup_table_data)。
        """
        return await _get_paper_metadata_impl(db, paper_id)

    async def list_paper_sections(paper_id: str, include_summary: bool = False) -> str:
        """列出论文的章节大纲(标题/起始页/包含的图表数量)。

        适用场景:用户问"论文结构是什么""有哪些章节""方法在第几页""哪一章有图表"。
        也可作为多步任务的前置步骤(先看大纲,再决定查哪章)。
        """
        return await _list_paper_sections_impl(db, paper_id, include_summary)

    async def search_paper_content(
        paper_id: str,
        query: str,
        intent: str = "general",
        top_k: Optional[int] = None,
    ) -> str:
        """对论文正文做混合检索(向量 + BM25 + 表格行 + 图片描述)。

        适用场景:用户问方法/实验/结果/讨论等正文内容,如"用了什么损失函数"
        "实验用了哪些数据集""主要贡献是什么"。
        多跳问题可以多次调用,每次聚焦一个子问题。
        """
        return await _search_paper_content_impl(db, paper_id, query, intent, top_k)

    async def lookup_table_data(paper_id: str, table_number: int) -> str:
        """精确查指定编号的表格数据(从关系库直查,不走 RAG)。

        适用场景:用户明确提到表号,如"表3里有哪些方法""表2的数据"。
        不适用:不知道表号、需要语义匹配的(用 search_paper_content 配合 intent=table)。
        """
        return await _lookup_table_data_impl(db, paper_id, table_number)

    async def compute_over_tables(paper_id: str, question: str) -> str:
        """基于论文表格做确定性算术(最大/最小/平均值)。

        适用场景:用户问"表3里哪个方法F1最高""表4各项的平均延迟""表2最大值"。
        问题必须包含表号与运算信号词(最高/最低/平均/max/min/average)。
        返回确定性计算结果,不走 LLM,数值可信。
        """
        return await _compute_over_tables_impl(db, paper_id, question)

    async def export_citation_format(paper_id: str, format: str = "bibtex") -> str:
        """导出论文引用格式(BibTeX/GB-T 7714/EndNote/RIS)。

        适用场景:用户要"导出引用""给我 BibTeX""按国标格式引用"。
        纯元数据派生,无 LLM 调用,格式规范。
        """
        return await _export_citation_format_impl(db, paper_id, format)

    return [
        StructuredTool.from_function(
            get_paper_metadata,
            name="get_paper_metadata",
            description="获取论文元数据(标题/作者/摘要/年份/DOI/venue 等)。用于元数据类问题。",
            args_schema=GetPaperMetadataInput,
            coroutine=get_paper_metadata,
        ),
        StructuredTool.from_function(
            list_paper_sections,
            name="list_paper_sections",
            description="列出论文章节大纲(标题/起始页/图表数量)。用于结构类问题或定位章节。",
            args_schema=ListPaperSectionsInput,
            coroutine=list_paper_sections,
        ),
        StructuredTool.from_function(
            search_paper_content,
            name="search_paper_content",
            description="对论文正文做混合检索(向量+BM25+表格行+图片)。用于方法/实验/结果等正文问题。多跳可多次调用。",
            args_schema=SearchPaperContentInput,
            coroutine=search_paper_content,
        ),
        StructuredTool.from_function(
            lookup_table_data,
            name="lookup_table_data",
            description="精确查指定编号表格(如 表3)。用户明确提到表号时用。不知道表号用 search_paper_content。",
            args_schema=LookupTableDataInput,
            coroutine=lookup_table_data,
        ),
        StructuredTool.from_function(
            compute_over_tables,
            name="compute_over_tables",
            description="基于表格做确定性算术(最大/最小/平均)。问题需含表号+运算信号词(最高/最低/平均)。",
            args_schema=ComputeOverTablesInput,
            coroutine=compute_over_tables,
        ),
        StructuredTool.from_function(
            export_citation_format,
            name="export_citation_format",
            description="导出引用格式(BibTeX/GB-T 7714/EndNote/RIS)。用于引用格式化需求。",
            args_schema=ExportCitationFormatInput,
            coroutine=export_citation_format,
        ),
    ]
