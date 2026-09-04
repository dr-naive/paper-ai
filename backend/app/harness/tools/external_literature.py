"""Harness Tools: external_literature —— 外部文献检索 tool。

提供 arXiv 和 Semantic Scholar 两个免费 API 的检索能力。
- arXiv API: 无需 key,按关键词查论文,返回标题/作者/摘要/arxiv_id/PDF链接
- Semantic Scholar API: 无需 key(有 rate limit),查引用关系

设计要点:
- 不需要 db,纯 HTTP 调用,所以工厂不接受 db 参数(但保持工厂签名一致以便 registry 统一加载)
- 超时 15s,失败时返回错误提示而非抛异常(让 LLM 能优雅降级)
- 返回 JSON 字符串,与 paper_internal tool 风格一致
"""
from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from langchain_core.tools import StructuredTool
from pydantic.v1 import BaseModel, Field

logger = logging.getLogger(__name__)

# arXiv API: 免费,无需 key,Atom XML 格式(必须用 https,http 会被超时)
ARXIV_API_URL = "https://export.arxiv.org/api/query"
# Semantic Scholar API: 免费,无需 key(有 rate limit ~100 req/5min)
S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper"
HTTP_TIMEOUT_SECONDS = 15.0
# 外部 API 重试配置:最大 2 次重试(共 3 次尝试),退避 1s → 2s
HTTP_MAX_RETRIES = 2
HTTP_RETRY_BASE_DELAY = 1.0


async def _http_get_with_retry(
    url: str,
    *,
    params: dict | None = None,
) -> httpx.Response:
    """带指数退避重试的 HTTP GET。仅重试超时和 5xx,4xx 不重试。
    
    重试耗尽后抛出原始异常,由调用方 catch 做降级处理。
    """
    import asyncio as _aio
    last_exc: Exception | None = None
    for attempt in range(HTTP_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status = exc.response.status_code
            # 仅 5xx 重试,4xx 不重试(4xx 是客户端错误,重试也没用)
            if 500 <= status < 600 and attempt < HTTP_MAX_RETRIES:
                delay = HTTP_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("HTTP %d(第 %d/%d 次重试),%ss 后重试: %s",
                               status, attempt + 1, HTTP_MAX_RETRIES, delay, url)
                await _aio.sleep(delay)
            else:
                raise
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            last_exc = exc
            if attempt < HTTP_MAX_RETRIES:
                delay = HTTP_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("HTTP 超时/连接错误(第 %d/%d 次重试),%ss 后重试: %s: %s",
                               attempt + 1, HTTP_MAX_RETRIES, delay, url, exc)
                await _aio.sleep(delay)
            else:
                raise
    raise last_exc  # 理论上不会到这里


class SearchArxivInput(BaseModel):
    query: str = Field(..., description="检索关键词,如论文标题、方法名、作者名")
    max_results: int = Field(5, description="最大返回条数,默认5", ge=1, le=20)


class SearchSemanticScholarInput(BaseModel):
    paper_title: str = Field(..., description="论文标题(用于查引用关系)")
    field: str = Field(
        "citations",
        description="查询类型: 'references'(本文引用了谁) / 'citations'(谁引用了本文) / 'related'(相关论文)",
    )
    max_results: int = Field(5, description="最大返回条数,默认5", ge=1, le=20)


async def _search_arxiv_impl(query: str, max_results: int = 5) -> str:
    """调用 arXiv API 检索论文。

    arXiv API 文档: https://info.arxiv.org/help/api/index.html
    返回 Atom XML,我们解析出标题/作者/摘要/arxiv_id/PDF链接。
    """
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
    }
    try:
        response = await _http_get_with_retry(ARXIV_API_URL, params=params)
    except httpx.HTTPError as exc:
        logger.warning("arXiv API 调用失败: %s", exc)
        return json.dumps(
            {"error": f"arXiv API 不可用: {type(exc).__name__}", "papers": []},
            ensure_ascii=False,
        )

    # 解析 Atom XML
    papers: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(response.text)
        # Atom 命名空间
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            arxiv_url = entry.find("atom:id", ns)
            arxiv_id = arxiv_url.text.strip().split("/")[-1] if arxiv_url is not None and arxiv_url.text else ""
            title_el = entry.find("atom:title", ns)
            title = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else ""
            summary_el = entry.find("atom:summary", ns)
            summary = summary_el.text.strip().replace("\n", " ") if summary_el is not None and summary_el.text else ""
            # 作者列表
            authors: list[str] = []
            for author in entry.findall("atom:author", ns):
                name_el = author.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())
            # PDF 链接
            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break
            # 发表日期
            published_el = entry.find("atom:published", ns)
            published = published_el.text[:10] if published_el is not None and published_el.text else ""

            papers.append({
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": authors,
                "abstract": summary[:500],  # 截断防过长
                "published": published,
                "pdf_url": pdf_url,
                "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
            })
    except ET.ParseError as exc:
        logger.exception("arXiv XML 解析失败")
        return json.dumps(
            {"error": f"arXiv 响应解析失败: {exc}", "papers": []},
            ensure_ascii=False,
        )

    return json.dumps(
        {"query": query, "count": len(papers), "papers": papers},
        ensure_ascii=False,
    )


async def _search_semantic_scholar_impl(
    paper_title: str, field: str = "citations", max_results: int = 5
) -> str:
    """调用 Semantic Scholar API 查引用关系。

    S2 API 文档: https://api.semanticscholar.org/api-docs/graph
    field 参数:
    - citations: 谁引用了本文(后续工作 / follow-up)
    - references: 本文引用了谁(参考文献)
    - related: 相关论文(近似)
    """
    # 第一步:用标题搜 paper,拿到 paper_id
    search_params = {"query": paper_title, "limit": 1, "fields": "title,year,citationCount"}
    try:
        search_resp = await _http_get_with_retry(f"{S2_API_URL}/search", params=search_params)
        search_data = search_resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Semantic Scholar 搜索失败: %s", exc)
        return json.dumps(
            {"error": f"Semantic Scholar API 不可用: {type(exc).__name__}", "papers": []},
            ensure_ascii=False,
        )

    if not search_data.get("data"):
        return json.dumps(
            {"error": f"未找到标题匹配的论文: {paper_title}", "papers": []},
            ensure_ascii=False,
        )

    target_paper = search_data["data"][0]
    s2_paper_id = target_paper.get("paperId", "")
    if not s2_paper_id:
        return json.dumps(
            {"error": "找到论文但无 paperId", "papers": []},
            ensure_ascii=False,
        )

    # 第二步:查引用关系
    # field 必须是 citations / references 之一,related 走另一个端点
    if field == "related":
        # related 走 recommendations 端点,逻辑不同,这里降级为 citations
        logger.info("Semantic Scholar related 降级为 citations")
        field = "citations"

    detail_params = {
        "fields": "title,authors,year,citationCount,abstract",
        "limit": max_results,
    }
    try:
        detail_resp = await _http_get_with_retry(
            f"{S2_API_URL}/{s2_paper_id}/{field}", params=detail_params
        )
        detail_data = detail_resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Semantic Scholar 引用查询失败: %s", exc)
        return json.dumps(
            {"error": f"引用关系查询失败: {type(exc).__name__}", "papers": []},
            ensure_ascii=False,
        )

    # 解析引用列表
    # citations 字段格式: [{"citingPaper": {...}}], references 字段格式: [{"citedPaper": {...}}]
    raw_items = detail_data.get(field, [])
    papers: list[dict[str, Any]] = []
    for item in raw_items[:max_results]:
        paper = item.get("citingPaper") or item.get("citedPaper") or item
        if not paper or not paper.get("title"):
            continue
        authors = [a.get("name", "") for a in (paper.get("authors") or []) if a.get("name")]
        papers.append({
            "title": paper.get("title", ""),
            "authors": authors,
            "year": paper.get("year"),
            "citation_count": paper.get("citationCount", 0),
            "abstract": (paper.get("abstract") or "")[:500],
            "s2_paper_id": paper.get("paperId", ""),
        })

    return json.dumps(
        {
            "query_paper": {
                "title": target_paper.get("title", ""),
                "year": target_paper.get("year"),
                "citation_count": target_paper.get("citationCount", 0),
                "s2_paper_id": s2_paper_id,
            },
            "field": field,
            "count": len(papers),
            "papers": papers,
        },
        ensure_ascii=False,
    )


def make_external_literature_tools(db: Any = None) -> list:
    """创建 external_literature skill 的全部 tool。

    注意:外部 API tool 不需要 db,但保持工厂签名 (db) 以便 SkillRegistry 统一调用。
    db 参数会被忽略。
    """
    return [
        StructuredTool.from_function(
            _search_arxiv_impl,
            name="search_arxiv",
            description=(
                "在 arXiv 上检索论文。返回标题/作者/摘要/arxiv_id/PDF链接。"
                "用于查 baseline 原论文、相关工作、follow-up 工作。"
                "输入:query=检索关键词(如方法名/论文标题),max_results=最大返回数。"
            ),
            args_schema=SearchArxivInput,
            coroutine=_search_arxiv_impl,
        ),
        StructuredTool.from_function(
            _search_semantic_scholar_impl,
            name="search_semantic_scholar",
            description=(
                "在 Semantic Scholar 查论文引用关系。"
                "field='citations' 查谁引用了本文(follow-up),"
                "field='references' 查本文引用了谁(参考文献)。"
                "输入:paper_title=论文标题,field=查询类型,max_results=最大返回数。"
            ),
            args_schema=SearchSemanticScholarInput,
            coroutine=_search_semantic_scholar_impl,
        ),
    ]
