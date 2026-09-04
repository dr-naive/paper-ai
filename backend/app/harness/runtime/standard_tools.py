"""First standardized read/network tools, backed by existing PaperAI services."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.harness.runtime.tool_runtime import ToolContext, ToolResult, ToolRuntime, ToolSpec
from app.harness.tools.external_literature import _search_arxiv_impl
from app.harness.tools.literature_research import make_project_tools
from app.harness.tools.paper_internal import _get_paper_metadata_impl, _list_paper_sections_impl, _search_paper_content_impl
from app.models.paper import Paper
from app.models.project import ProjectPaper, ResearchProject


class PaperIdInput(BaseModel):
    paper_id: str = Field(min_length=1)

class PaperOutlineInput(PaperIdInput):
    include_summary: bool = False

class PaperSearchInput(PaperIdInput):
    query: str = Field(min_length=1, max_length=4000)
    intent: str = "general"
    top_k: int | None = Field(default=None, ge=1, le=20)

class ProjectSearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    intent: str = "general"
    top_k: int = Field(default=10, ge=2, le=20)
    max_papers: int = Field(default=8, ge=1, le=20)

class ExternalSearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    max_results: int = Field(default=5, ge=1, le=20)

class ProjectListInput(BaseModel):
    pass


def _decode(raw: str) -> ToolResult:
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return ToolResult(ok=False, summary="工具返回了无法解析的数据", error_code="TOOL_RESULT_INVALID")
    if isinstance(data, dict) and data.get("error"):
        return ToolResult(ok=False, summary=str(data["error"]), data=data, error_code="TOOL_UPSTREAM_ERROR", retryable=True)
    return ToolResult(ok=True, summary="查询完成", data=data)


async def _owned_project(context: ToolContext) -> ResearchProject | None:
    if not context.project_id:
        return None
    project = await context.db.get(ResearchProject, context.project_id)
    return project if project and project.user_id == context.user_id else None


async def _owned_paper(context: ToolContext, paper_id: str) -> Paper | None:
    paper = (await context.db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == context.user_id))).scalar_one_or_none()
    if paper is None:
        return None
    if context.project_id:
        linked = await context.db.scalar(select(ProjectPaper.id).where(ProjectPaper.project_id == context.project_id,
                                                                         ProjectPaper.paper_id == paper_id))
        if linked is None:
            return None
    return paper


def _forbidden(resource: str) -> ToolResult:
    return ToolResult(ok=False, summary=f"{resource}不存在或无访问权限", error_code="TOOL_RESOURCE_FORBIDDEN")


async def paper_metadata(context: ToolContext, value: PaperIdInput) -> ToolResult:
    if not await _owned_paper(context, value.paper_id): return _forbidden("论文")
    return _decode(await _get_paper_metadata_impl(context.db, value.paper_id))

async def paper_outline(context: ToolContext, value: PaperOutlineInput) -> ToolResult:
    if not await _owned_paper(context, value.paper_id): return _forbidden("论文")
    return _decode(await _list_paper_sections_impl(context.db, value.paper_id, value.include_summary))

async def paper_search(context: ToolContext, value: PaperSearchInput) -> ToolResult:
    if not await _owned_paper(context, value.paper_id): return _forbidden("论文")
    return _decode(await _search_paper_content_impl(context.db, **value.model_dump()))

async def project_list(context: ToolContext, value: BaseModel) -> ToolResult:
    if not await _owned_project(context): return _forbidden("项目")
    rows = (await context.db.execute(select(ProjectPaper, Paper).join(Paper, Paper.id == ProjectPaper.paper_id)
                                     .where(ProjectPaper.project_id == context.project_id, Paper.user_id == context.user_id))).all()
    return ToolResult(ok=True, summary=f"项目中有 {len(rows)} 篇论文", data=[{"paper_id": str(p.id), "title": p.title,
                       "role": pp.role, "tags": pp.tags or [], "reading_priority": pp.reading_priority} for pp, p in rows])

async def project_search(context: ToolContext, value: ProjectSearchInput) -> ToolResult:
    if not await _owned_project(context): return _forbidden("项目")
    tool = next(item for item in make_project_tools(context.db, context.project_id or "", context.user_id)
                if item.name == "project_search_content")
    return _decode(await tool.ainvoke(value.model_dump()))

async def external_search(context: ToolContext, value: ExternalSearchInput) -> ToolResult:
    if context.project_id and not await _owned_project(context): return _forbidden("项目")
    return _decode(await _search_arxiv_impl(value.query, value.max_results))


def build_standard_tool_runtime() -> ToolRuntime:
    runtime = ToolRuntime()
    definitions: list[tuple[ToolSpec, Any]] = [
        (ToolSpec("paper.get_metadata", "1.0.0", "读取论文元数据", "read", False, 10, True, PaperIdInput), paper_metadata),
        (ToolSpec("paper.get_outline", "1.0.0", "读取论文大纲", "read", False, 10, True, PaperOutlineInput), paper_outline),
        (ToolSpec("paper.search_content", "1.0.0", "检索论文正文", "read", False, 30, True, PaperSearchInput), paper_search),
        (ToolSpec("project.list_papers", "1.0.0", "列出项目论文", "read", False, 10, True, ProjectListInput), project_list),
        (ToolSpec("project.search_content", "1.0.0", "跨项目论文检索", "read", False, 60, True, ProjectSearchInput), project_search),
        (ToolSpec("literature.search_external", "1.0.0", "检索外部文献", "network", False, 20, True, ExternalSearchInput), external_search),
    ]
    for spec, handler in definitions:
        runtime.register(spec, handler)
    return runtime
