"""研究项目 REST API。

提供项目 CRUD、文档库管理、写作产物管理、长期记忆管理 4 类端点。
所有端点都校验项目所有权(project.user_id == current_user_id)。

Endpoint 清单:
  项目:
    GET    /api/v1/projects                       列出当前用户项目(分页+筛选)
    POST   /api/v1/projects                       创建项目
    GET    /api/v1/projects/{project_id}          项目详情
    PATCH  /api/v1/projects/{project_id}          更新项目字段
    DELETE /api/v1/projects/{project_id}          级联删除项目
  文档库:
    GET    /api/v1/projects/{project_id}/papers   列出项目文档
    POST   /api/v1/projects/{project_id}/papers   加入/更新论文(幂等)
    DELETE /api/v1/projects/{project_id}/papers/{paper_id}  移除论文
  写作产物:
    GET    /api/v1/projects/{project_id}/artifacts           列出产物(可按 type 筛)
    POST   /api/v1/projects/{project_id}/artifacts           创建产物
    GET    /api/v1/projects/{project_id}/artifacts/{artifact_id}  详情
    PATCH  /api/v1/projects/{project_id}/artifacts/{artifact_id}  更新内容
    DELETE /api/v1/projects/{project_id}/artifacts/{artifact_id}  删除
  长期记忆:
    GET    /api/v1/projects/{project_id}/memory             读取 memory JSON
    PATCH  /api/v1/projects/{project_id}/memory             覆写 memory(供 UI 编辑)
    POST   /api/v1/projects/{project_id}/memory/note        追加一条 memory note
"""
from __future__ import annotations

import logging
import json
import time
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_id
from app.database import get_db
from app.application.project_service import (
    PaperNotFoundError,
    ProjectNotFoundError,
    ProjectService,
)
from app.job_queue import enqueue_job
from app.redis_client import get_json, set_json
from app.models.project import (
    ARTIFACT_STATUS_DRAFT,
    PAPER_ROLE_BACKGROUND,
    PAPER_ROLE_CORE,
    PAPER_ROLE_RELATED,
    PROJECT_PHASE_ARCHIVED,
    PROJECT_PHASE_READING,
    PROJECT_PHASE_REFINEMENT,
    PROJECT_PHASE_RESEARCH,
    PROJECT_PHASE_WRITING,
    PROJECT_STATUS_ACTIVE,
    PROJECT_STATUS_COMPLETED,
    PROJECT_STATUS_PAUSED,
    ProjectPaper,
    ResearchProject,
    WritingArtifact,
)
from app.utils.manuscript_export import build_docx, build_submission_package, markdown_to_latex

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
READING_EXECUTION_PREFIX = "paperai:reading-execution:"
READING_EXECUTION_TTL = 7 * 24 * 60 * 60

# 合法枚举值(用于校验,避免无效字符串入库)
_VALID_PHASES = {
    PROJECT_PHASE_RESEARCH,
    PROJECT_PHASE_READING,
    PROJECT_PHASE_WRITING,
    PROJECT_PHASE_REFINEMENT,
    PROJECT_PHASE_ARCHIVED,
}
_VALID_STATUSES = {PROJECT_STATUS_ACTIVE, PROJECT_STATUS_PAUSED, PROJECT_STATUS_COMPLETED}
_VALID_PAPER_ROLES = {PAPER_ROLE_CORE, PAPER_ROLE_RELATED, PAPER_ROLE_BACKGROUND}
_VALID_ARTIFACT_TYPES = {
    "research_brief",
    "literature_screening",
    "research_map",
    "reading_plan",
    "evidence_matrix",
    "experiment_design",
    "experiment_results",
    "paper_blueprint",
    "outline",
    "literature_review",
    "reference_list",
    "section_draft",
    "full_draft",
    "review_report",
    "submission_suggestion",
    "final_manuscript",
}
_RESERVED_ARTIFACT_META_KEYS = {"audit_kind", "finalized_at"}
_RESERVED_GENERATORS = {"deterministic_reference_builder"}


def _validate_artifact_create_integrity(body: "ArtifactCreate") -> None:
    if body.artifact_type in {"experiment_results", "final_manuscript"}:
        raise HTTPException(status_code=409, detail=f"{body.artifact_type} 只能通过受约束的 Agent 工具生成")
    if _RESERVED_ARTIFACT_META_KEYS.intersection(body.meta) or body.meta.get("generated_by") in _RESERVED_GENERATORS:
        raise HTTPException(status_code=400, detail="meta 包含系统保留的完整性字段")


def _artifact_integrity_locked(artifact: WritingArtifact) -> bool:
    return (
        artifact.artifact_type in {"experiment_results", "final_manuscript"}
        or (artifact.meta or {}).get("audit_kind") == "full_draft"
        or (artifact.meta or {}).get("generated_by") in _RESERVED_GENERATORS
    )


def _build_workflow_status(
    project_papers: list[ProjectPaper], artifacts: list[WritingArtifact], imports: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Derive the next safe research action from persisted project evidence."""
    latest = {}
    for artifact in sorted(artifacts, key=lambda item: item.updated_at or item.created_at or datetime.min, reverse=True):
        latest.setdefault(artifact.artifact_type, artifact)
    paper_count = len(project_papers)
    completed_cards = sum(1 for item in project_papers if (item.analysis_card or {}).get("summary"))
    blueprint = latest.get("paper_blueprint")
    experiment_design = latest.get("experiment_design")
    experiment_results = latest.get("experiment_results")
    needs_results = bool(experiment_design and (experiment_design.content or {}).get("requires_empirical_results", True))
    results_done = bool(
        experiment_design
        and (not needs_results or (
            experiment_results
            and str((experiment_results.content or {}).get("experiment_design_id")) == str(experiment_design.id)
        ))
    )
    blueprint_sections = list((blueprint.content or {}).get("sections") or []) if blueprint else []
    drafts = [item for item in artifacts if item.artifact_type == "section_draft" and blueprint and item.parent_id == blueprint.id]
    drafted_ids = {str((item.meta or {}).get("section_id")) for item in drafts}
    unresolved = sum(len((item.meta or {}).get("unresolved_items") or []) for item in drafts)
    drafting_done = bool(blueprint_sections) and all(str(item.get("section_id")) in drafted_ids for item in blueprint_sections) and unresolved == 0
    full_draft = latest.get("full_draft")
    reports = [item for item in artifacts if item.artifact_type == "review_report" and full_draft and item.parent_id == full_draft.id and (item.meta or {}).get("audit_kind") == "full_draft"]
    report = max(reports, key=lambda item: item.updated_at or item.created_at or datetime.min) if reports else None
    audit_passed = bool(report and int(((report.content or {}).get("counts") or {}).get("blocker") or 0) == 0)
    screening = latest.get("literature_screening")
    screening_content = dict(screening.content or {}) if screening else {}
    screening_candidates = list(screening_content.get("candidates") or [])
    screening_done = bool(
        screening_content.get("query_runs")
        and any(isinstance(item, dict) and item.get("decision") == "include" for item in screening_candidates)
    )
    specs = [
        ("research_brief", "澄清题材与检索边界", bool(latest.get("research_brief")), "请先基于项目主题澄清研究对象、目标、约束和未知项，制定中英文关键词、检索式、纳入排除标准与选题评价准则，并保存研究任务书。不要把尚未检索的判断写成事实。"),
        ("literature_screening", "检索并筛选候选文献", screening_done, "请按研究任务书执行多组学术检索，保存候选文献筛选台账；每篇标记纳入、排除或待定，并记录稳定标识、相关性维度和决策理由。"),
        ("library", "建立项目文档库", paper_count > 0, "请从筛选台账中优先导入已纳入的核心、相关和背景论文；不要导入已排除候选。"),
        ("research_map", "了解领域并选择方向", bool(latest.get("research_map")), "请跨论文检索当前题材，生成领域地图、研究空白和可验证候选选题并保存。"),
        ("reading_plan", "制定精读计划", bool(latest.get("reading_plan")), "请根据领域地图制定精读计划，说明每篇论文的阅读理由、重点和问题。"),
        ("deep_reading", "完成核心论文精读", paper_count > 0 and completed_cards == paper_count, "请按精读计划继续阅读未完成论文，保存论文卡片和带来源的关键记忆。"),
        ("evidence_matrix", "构建跨论文证据", bool(latest.get("evidence_matrix")), "请基于已完成论文卡片生成跨论文证据矩阵，标出冲突结论和证据缺口。"),
        ("experiment_design", "形成研究与实验方案", bool(experiment_design), "请基于证据矩阵制定可证伪假设、变量、基线、指标、实验步骤和风险并保存；若研究不需要实证结果，必须明确标记。"),
        ("experiment_results", "登记可信研究结果", results_done, "请仅根据用户提供的实验输出、数据文件或追踪记录登记结果，绑定实验设计、运行标识、来源和指标；没有真实结果时不要编造，保留在当前阶段。"),
        ("paper_blueprint", "规划论文论证结构", bool(blueprint), "请根据实验设计生成论文蓝图，为每节定义主张、证据需求和字数目标。"),
        ("section_drafts", "逐节撰写与补证", drafting_done, "请按论文蓝图继续撰写或定向修订未完成章节，缺少的证据保留为未解决项。"),
        ("reference_list", "统一正文引用", bool(latest.get("reference_list")), "请从章节实际 evidence_refs 生成参考文献列表，然后重新组装带稳定引用键的全文。"),
        ("full_draft", "组装完整草稿", bool(full_draft), "请检查章节和参考文献完整性，按蓝图顺序组装完整草稿。"),
        ("audit", "审校并解决阻断项", audit_passed, "请审计全文的事实、引用、证据覆盖和结构；按报告定向修订后重新组装和审计。"),
        ("final", "锁定并导出终稿", bool(latest.get("final_manuscript")), "最新审计通过后，请锁定论文终稿。"),
    ]
    first_incomplete = next((index for index, item in enumerate(specs) if not item[2]), len(specs))
    stages = [{"key": key, "label": label, "status": "completed" if done else "current" if index == first_incomplete else "pending"}
              for index, (key, label, done, _prompt) in enumerate(specs)]
    next_prompt = specs[first_incomplete][3] if first_incomplete < len(specs) else "论文终稿已完成，可下载投稿包或根据目标期刊继续格式适配。"
    import_items = [dict(item) for item in (imports or [])]
    active_imports = [item for item in import_items if item.get("status") in {"queued", "processing"}]
    if first_incomplete < len(specs) and specs[first_incomplete][0] == "library" and active_imports:
        next_prompt = f"已有 {len(active_imports)} 篇 arXiv 论文正在下载或解析，请等待完成；完成后会自动加入项目文档库。"
    topic_outputs = sum(bool(latest.get(kind)) for kind in ("research_brief", "literature_screening", "research_map"))
    reading_outputs = completed_cards + int(bool(latest.get("evidence_matrix")))
    writing_outputs = sum(bool(latest.get(kind)) for kind in ("paper_blueprint", "full_draft", "review_report", "final_manuscript")) + len(drafts)

    def area_status(outputs: int, ready: bool) -> str:
        return "ready" if ready else "active" if outputs else "empty"

    areas = [
        {
            "key": "topic", "label": "选题研究",
            "description": "探索题材、检索外部文献、比较方向并确定研究问题。",
            "status": area_status(topic_outputs, bool(latest.get("research_map"))),
            "summary": f"{topic_outputs} 类研究产物，{len(screening_candidates)} 篇候选论文",
            "primary_action": "继续选题" if topic_outputs else "开始选题",
            "prompt": "请基于当前主题帮我完成选题研究：可先澄清研究对象与约束，也可以直接检索外部候选论文、比较方向并形成候选选题。请区分事实、摘要判断和待验证假设。",
            "metrics": {"outputs": topic_outputs, "candidates": len(screening_candidates)},
        },
        {
            "key": "reading", "label": "论文阅读",
            "description": "管理文献、阅读原文、生成论文卡片并比较多篇证据。",
            "status": area_status(reading_outputs, bool(latest.get("evidence_matrix"))),
            "summary": f"{paper_count} 篇论文，{completed_cards} 篇已精读",
            "primary_action": "继续阅读" if paper_count else "查找论文",
            "prompt": "请帮助我了解项目论文：根据我的问题检索或导入论文，解释论文解决的问题、方法、证据、局限和与其他论文的关系。需要全文证据时请明确来源。",
            "metrics": {"papers": paper_count, "completed_cards": completed_cards},
        },
        {
            "key": "writing", "label": "论文写作",
            "description": "围绕明确主张组织材料、撰写章节、管理引用并审校终稿。",
            "status": area_status(writing_outputs, bool(latest.get("final_manuscript"))),
            "summary": f"{len(drafts)} 个章节草稿，{'已有完整稿' if full_draft else '尚无完整稿'}",
            "primary_action": "继续写作" if writing_outputs else "开始写作",
            "prompt": "请帮助我开始或继续论文写作：先询问论文类型、核心主张、目标读者和已有材料，再选择制定结构、撰写章节、检查引用或审校全文。不要虚构证据和实验结果。",
            "metrics": {"section_drafts": len(drafts), "has_full_draft": bool(full_draft), "unresolved_items": unresolved},
        },
    ]
    return {
        "mode": "workbench", "areas": areas,
        "stages": stages, "completed": sum(1 for _key, _label, done, _prompt in specs if done),
        "total": len(specs), "progress_percent": round(sum(1 for _key, _label, done, _prompt in specs if done) / len(specs) * 100),
        "next_stage": specs[first_incomplete][0] if first_incomplete < len(specs) else "complete",
        "next_prompt": next_prompt, "paper_count": paper_count, "completed_cards": completed_cards,
        "unresolved_items": unresolved, "imports": import_items[-30:], "active_imports": len(active_imports),
    }


# ---------- 通用 helper ----------
async def _get_owned_project(
    db: AsyncSession, project_id: str, user_id: str
) -> ResearchProject:
    """加载项目并校验所有权,不存在或不属于该用户统一返回 404(避免泄漏存在性)。"""
    try:
        return await ProjectService(db).get_owned_project(project_id, user_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="项目不存在或无访问权限")


# =====================================================================
# Pydantic 请求/响应模型
# =====================================================================
class ProjectScope(BaseModel):
    field: str = Field("", max_length=200)
    research_subject: str = Field("", max_length=500)
    research_question: str = Field("", max_length=2000)
    research_goal: str = Field("", max_length=2000)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    method_direction: str = Field("", max_length=1000)
    notes: str = Field("", max_length=4000)

    @field_validator(
        "field",
        "research_subject",
        "research_question",
        "research_goal",
        "method_direction",
        "notes",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            keyword = value.strip()
            if not keyword or keyword in normalized:
                continue
            if len(keyword) > 100:
                raise ValueError("keyword 长度不能超过 100")
            normalized.append(keyword)
        return normalized


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    research_topic: str = Field(..., min_length=1, max_length=300)
    abstract: str = ""
    phase: str = PROJECT_PHASE_RESEARCH
    preferences: dict[str, Any] = Field(default_factory=dict)
    research_scope: ProjectScope | None = None

    @field_validator("title", "research_topic")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("项目名称和研究主题不能为空")
        return normalized


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    research_topic: Optional[str] = None
    abstract: Optional[str] = None
    phase: Optional[str] = None
    status: Optional[str] = None
    preferences: Optional[dict[str, Any]] = None
    research_scope: Optional[ProjectScope] = None

    @field_validator("title", "research_topic")
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("项目名称和研究主题不能为空")
        return normalized


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    title: str
    research_topic: str
    abstract: str
    phase: str
    status: str
    memory: dict[str, Any]
    preferences: dict[str, Any]
    research_scope: ProjectScope
    paper_count: int | None = None
    artifact_count: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int


class ExternalPaperSearch(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    max_results: int = Field(10, ge=1, le=20)


class ExternalPaperImport(BaseModel):
    arxiv_id: str = Field(..., min_length=5, max_length=80)
    role: Literal["core", "related", "background"] = "related"
    notes: str = Field("", max_length=2000)
    reading_priority: int = Field(3, ge=1, le=5)


class ProjectPaperAdd(BaseModel):
    paper_id: str
    role: str = PAPER_ROLE_RELATED
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    reading_priority: int = Field(3, ge=1, le=5)


class ProjectPaperReadingPlan(BaseModel):
    order: int = Field(1, ge=1)
    status: Literal["pending", "reading", "completed", "skipped", "failed"] = "pending"
    reason: str = Field("", max_length=1000)
    focus: list[str] = Field(default_factory=list, max_length=20)
    questions: list[str] = Field(default_factory=list, max_length=20)


class ProjectPaperUpdate(BaseModel):
    role: Optional[str] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    reading_priority: Optional[int] = None
    reading_plan: Optional[ProjectPaperReadingPlan] = None


class PaperCardEvidence(BaseModel):
    source_id: Optional[str] = Field(None, max_length=30)
    page: Optional[int] = Field(None, ge=1)
    section: Optional[str] = Field(None, max_length=300)
    text: str = Field(..., min_length=1, max_length=2000)


class ProjectPaperCardUpdate(BaseModel):
    summary: str = ""
    research_questions: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    contributions: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence: list[PaperCardEvidence] = Field(default_factory=list)


class ArtifactCreate(BaseModel):
    artifact_type: str
    title: str = Field(..., min_length=1, max_length=400)
    content: dict[str, Any] = Field(default_factory=dict)
    markdown_text: str = ""
    html_text: str = ""
    status: str = ARTIFACT_STATUS_DRAFT
    parent_id: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ArtifactUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[dict[str, Any]] = None
    markdown_text: Optional[str] = None
    html_text: Optional[str] = None
    status: Optional[str] = None
    parent_id: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


class MemoryNoteCreate(BaseModel):
    text: str = Field(..., min_length=1)
    tag: str = ""
    source_type: Literal["user", "agent", "paper"] = "user"
    paper_id: Optional[str] = None
    paper_title: Optional[str] = None
    page: Optional[int] = Field(None, ge=1)
    source_id: Optional[str] = Field(None, max_length=30)


class MemoryOverwrite(BaseModel):
    summary: Optional[str] = None
    notes: Optional[list[dict[str, Any]]] = None


class ReadingExecutionStart(BaseModel):
    max_items: int = Field(10, ge=1, le=20)


# =====================================================================
# 项目 CRUD
# =====================================================================
@router.get("", response_model=ProjectListResponse)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="按标题/主题模糊搜索"),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的研究项目(分页 + 状态/关键字筛选)。"""
    user_id = await get_current_user_id(authorization, db)
    if status:
        if status not in _VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"非法 status: {status}")
    return await ProjectService(db).list_projects(
        user_id=user_id,
        page=page,
        page_size=page_size,
        status=status,
        query=q,
    )


@router.post("", status_code=201, response_model=ProjectResponse)
async def create_project(
    body: ProjectCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """创建研究项目。"""
    user_id = await get_current_user_id(authorization, db)
    if body.phase not in _VALID_PHASES:
        raise HTTPException(status_code=400, detail=f"非法 phase: {body.phase}")
    result = await ProjectService(db).create_project(
        user_id=user_id,
        title=body.title,
        research_topic=body.research_topic,
        abstract=body.abstract or "",
        phase=body.phase,
        status=PROJECT_STATUS_ACTIVE,
        preferences=body.preferences or {},
        research_scope=body.research_scope.model_dump() if body.research_scope else None,
    )
    logger.info("用户 %s 创建项目 %s topic=%s", user_id, result["id"], result["research_topic"][:50])
    return result


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """项目详情(含文档数/产物数统计)。"""
    user_id = await get_current_user_id(authorization, db)
    try:
        return await ProjectService(db).get_project_detail(
            project_id=project_id,
            user_id=user_id,
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="项目不存在或无访问权限")


@router.get("/{project_id}/workflow-status")
async def get_project_workflow_status(
    project_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """返回研究到投稿各阶段的确定性完成度与下一条可执行 Agent 指令。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    papers = (await db.execute(select(ProjectPaper).where(ProjectPaper.project_id == project_id))).scalars().all()
    artifacts = (await db.execute(select(WritingArtifact).where(WritingArtifact.project_id == project_id))).scalars().all()
    project = await db.get(ResearchProject, project_id)
    imports = list(((project.preferences or {}) if project else {}).get("paper_imports") or [])
    return _build_workflow_status(list(papers), list(artifacts), imports)


@router.post("/{project_id}/external-papers/search")
async def search_external_papers(
    project_id: str,
    body: ExternalPaperSearch,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """直接搜索 arXiv 候选论文，供选题界面使用，不依赖 Agent 对话。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    from app.harness.tools.external_literature import _search_arxiv_impl

    payload = json.loads(await _search_arxiv_impl(body.query.strip(), body.max_results))
    if payload.get("error"):
        raise HTTPException(status_code=502, detail=payload["error"])
    return payload


@router.post("/{project_id}/external-papers/import", status_code=202)
async def import_external_paper(
    project_id: str,
    body: ExternalPaperImport,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """下载并解析一篇 arXiv 论文，完成后自动加入项目文档库。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    from app.harness.tools.literature_research import make_project_tools

    tool = next(item for item in make_project_tools(db, project_id, user_id) if item.name == "project_import_arxiv_paper")
    message = await tool.ainvoke(body.model_dump())
    if str(message).startswith("错误:"):
        raise HTTPException(status_code=502, detail=str(message).removeprefix("错误:"))
    return {"message": str(message), "arxiv_id": body.arxiv_id}


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """更新项目可变字段(部分更新)。"""
    user_id = await get_current_user_id(authorization, db)
    if body.phase is not None:
        if body.phase not in _VALID_PHASES:
            raise HTTPException(status_code=400, detail=f"非法 phase: {body.phase}")
    if body.status is not None:
        if body.status not in _VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"非法 status: {body.status}")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    research_scope = changes.pop("research_scope", None)
    try:
        return await ProjectService(db).update_project(
            project_id=project_id,
            user_id=user_id,
            changes=changes,
            research_scope=research_scope,
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="项目不存在或无访问权限")


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """级联删除项目(关联的 ProjectPaper / WritingArtifact / ChatSession 一并清理)。"""
    user_id = await get_current_user_id(authorization, db)
    try:
        await ProjectService(db).delete_project(project_id=project_id, user_id=user_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="项目不存在或无访问权限")
    logger.info("用户 %s 删除项目 %s", user_id, project_id)
    return None


# =====================================================================
# 项目文档库
# =====================================================================
@router.get("/{project_id}/papers")
async def list_project_papers(
    project_id: str,
    role: Optional[str] = Query(None),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """列出项目文档库(含论文元信息)。"""
    user_id = await get_current_user_id(authorization, db)
    if role:
        if role not in _VALID_PAPER_ROLES:
            raise HTTPException(status_code=400, detail=f"非法 role: {role}")
    try:
        return await ProjectService(db).list_project_papers(
            project_id=project_id,
            user_id=user_id,
            role=role,
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="项目不存在或无访问权限")


@router.post("/{project_id}/papers", status_code=201)
async def add_project_paper(
    project_id: str,
    body: ProjectPaperAdd,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """加入论文到项目(幂等:已存在则更新 role/tags/notes/priority)。"""
    user_id = await get_current_user_id(authorization, db)
    if body.role not in _VALID_PAPER_ROLES:
        raise HTTPException(status_code=400, detail=f"非法 role: {body.role}")
    if not body.paper_id:
        raise HTTPException(status_code=400, detail="paper_id 必填")
    try:
        return await ProjectService(db).add_project_paper(
            project_id=project_id,
            user_id=user_id,
            paper_id=body.paper_id,
            role=body.role,
            tags=body.tags,
            notes=body.notes,
            reading_priority=body.reading_priority,
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="项目不存在或无访问权限")
    except PaperNotFoundError:
        raise HTTPException(status_code=404, detail="论文不存在或无访问权限")


@router.patch("/{project_id}/papers/{paper_id}")
async def update_project_paper(
    project_id: str,
    paper_id: str,
    body: ProjectPaperUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """更新项目内某篇论文的 role/tags/notes/priority。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    pp = (
        await db.execute(
            select(ProjectPaper).where(
                ProjectPaper.project_id == project_id,
                ProjectPaper.paper_id == paper_id,
            )
        )
    ).scalars().first()
    if pp is None:
        raise HTTPException(status_code=404, detail="该论文不在项目中")
    if body.role is not None:
        if body.role not in _VALID_PAPER_ROLES:
            raise HTTPException(status_code=400, detail=f"非法 role: {body.role}")
        pp.role = body.role
    if body.tags is not None:
        pp.tags = body.tags
    if body.notes is not None:
        pp.notes = body.notes
    if body.reading_priority is not None:
        pp.reading_priority = body.reading_priority
    if body.reading_plan is not None:
        plan = body.reading_plan
        pp.reading_plan = {
            "order": plan.order,
            "status": plan.status,
            "reason": plan.reason,
            "focus": [value[:300] for value in plan.focus],
            "questions": [value[:500] for value in plan.questions],
            "updated_at": datetime.utcnow().isoformat(),
        }
    await db.commit()
    await db.refresh(pp)
    return pp.to_dict()


@router.get("/{project_id}/papers/{paper_id}/card")
async def get_project_paper_card(
    project_id: str,
    paper_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """读取论文在当前项目语境下的结构化阅读卡片。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    pp = (await db.execute(select(ProjectPaper).where(
        ProjectPaper.project_id == project_id,
        ProjectPaper.paper_id == paper_id,
    ))).scalars().first()
    if pp is None:
        raise HTTPException(status_code=404, detail="该论文不在项目中")
    return {"project_id": project_id, "paper_id": paper_id, "card": pp.analysis_card or {}}


@router.patch("/{project_id}/papers/{paper_id}/card")
async def update_project_paper_card(
    project_id: str,
    paper_id: str,
    body: ProjectPaperCardUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """创建或整体更新结构化论文卡片。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    pp = (await db.execute(select(ProjectPaper).where(
        ProjectPaper.project_id == project_id,
        ProjectPaper.paper_id == paper_id,
    ))).scalars().first()
    if pp is None:
        raise HTTPException(status_code=404, detail="该论文不在项目中")
    card = body.model_dump()
    card["updated_at"] = datetime.utcnow().isoformat()
    card["generated_by"] = "user"
    pp.analysis_card = card
    await db.commit()
    await db.refresh(pp)
    return {"project_id": project_id, "paper_id": paper_id, "card": pp.analysis_card}


@router.delete("/{project_id}/papers/{paper_id}", status_code=204)
async def remove_project_paper(
    project_id: str,
    paper_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """从项目移除论文(仅删除关联,不删论文本身)。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    pp = (
        await db.execute(
            select(ProjectPaper).where(
                ProjectPaper.project_id == project_id,
                ProjectPaper.paper_id == paper_id,
            )
        )
    ).scalars().first()
    if pp is None:
        raise HTTPException(status_code=404, detail="该论文不在项目中")
    await db.delete(pp)
    await db.commit()
    return None


# =====================================================================
# 写作产物
# =====================================================================
@router.get("/{project_id}/artifacts")
async def list_artifacts(
    project_id: str,
    type: Optional[str] = Query(None, description="按 artifact_type 筛选"),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """列出项目写作产物(可按 type 筛选,按 updated_at 倒序)。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    stmt = select(WritingArtifact).where(WritingArtifact.project_id == project_id)
    if type:
        if type not in _VALID_ARTIFACT_TYPES:
            raise HTTPException(status_code=400, detail=f"非法 artifact_type: {type}")
        stmt = stmt.where(WritingArtifact.artifact_type == type)
    stmt = stmt.order_by(WritingArtifact.updated_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    # 列表只返回摘要,不含 markdown 全文(避免响应过大)
    items = []
    for a in rows:
        d = a.to_dict()
        d.pop("markdown_text", None)
        d.pop("html_text", None)
        d.pop("content", None)
        d["markdown_preview"] = (a.markdown_text or "")[:200]
        items.append(d)
    return {"items": items, "total": len(items)}


@router.post("/{project_id}/artifacts", status_code=201)
async def create_artifact(
    project_id: str,
    body: ArtifactCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """创建写作产物。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    if body.artifact_type not in _VALID_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=400, detail=f"非法 artifact_type: {body.artifact_type}"
        )
    _validate_artifact_create_integrity(body)
    # parent_id 校验(若提供)
    if body.parent_id:
        parent = await db.get(WritingArtifact, body.parent_id)
        if parent is None or parent.project_id != project_id:
            raise HTTPException(status_code=400, detail="parent_id 无效")
    artifact = WritingArtifact(
        project_id=project_id,
        author_id=user_id,
        artifact_type=body.artifact_type,
        title=body.title.strip(),
        version=1,
        parent_id=body.parent_id,
        content=body.content or {},
        markdown_text=body.markdown_text or "",
        html_text=body.html_text or "",
        status=body.status,
        meta=body.meta or {},
    )
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    logger.info(
        "用户 %s 在项目 %s 创建产物 %s type=%s",
        user_id, project_id, artifact.id, artifact.artifact_type,
    )
    return artifact.to_dict()


@router.get("/{project_id}/artifacts/{artifact_id}")
async def get_artifact(
    project_id: str,
    artifact_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """产物详情(含 markdown 全文)。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    artifact = await db.get(WritingArtifact, artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise HTTPException(status_code=404, detail="产物不存在")
    return artifact.to_dict()


@router.get("/{project_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    project_id: str,
    artifact_id: str,
    format: Literal["md", "tex", "docx", "zip"] = Query("md"),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """以 UTF-8 Markdown 下载写作产物，文件名由服务端安全生成。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    artifact = await db.get(WritingArtifact, artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise HTTPException(status_code=404, detail="产物不存在")
    safe_title = "".join(
        char if char.isascii() and (char.isalnum() or char in "-_") else "_"
        for char in artifact.title
    ).strip("_")
    basename = (safe_title or "paperai-manuscript")[:100]
    payload: bytes | str = artifact.markdown_text or ""
    media_type = "text/markdown; charset=utf-8"
    extension = "md"
    if format in {"tex", "docx", "zip"} and artifact.artifact_type != "final_manuscript":
        raise HTTPException(status_code=400, detail="LaTeX、Word 和投稿包仅支持已审计的论文终稿")
    if format in {"tex", "zip"}:
        reference_list = await db.get(WritingArtifact, str((artifact.content or {}).get("reference_list_id") or ""))
        if reference_list is None or reference_list.project_id != project_id or reference_list.artifact_type != "reference_list":
            raise HTTPException(status_code=409, detail="终稿缺少有效参考文献列表")
        bibtex = str((reference_list.content or {}).get("bibtex") or "")
        if format == "tex":
            payload = markdown_to_latex(artifact.title, artifact.markdown_text or "")
            media_type, extension = "application/x-tex; charset=utf-8", "tex"
        else:
            report = await db.get(WritingArtifact, str((artifact.content or {}).get("review_report_id") or ""))
            if report is None or report.project_id != project_id or report.artifact_type != "review_report":
                raise HTTPException(status_code=409, detail="终稿缺少有效审计报告")
            payload = build_submission_package(artifact.title, artifact.markdown_text or "", bibtex, report.markdown_text or "")
            media_type, extension = "application/zip", "zip"
    elif format == "docx":
        payload = build_docx(artifact.title, artifact.markdown_text or "")
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        extension = "docx"
    filename = f"{basename}.{extension}"
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{project_id}/artifacts/{artifact_id}")
async def update_artifact(
    project_id: str,
    artifact_id: str,
    body: ArtifactUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """更新产物字段(部分更新)。内容更新时 version 自增。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    artifact = await db.get(WritingArtifact, artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise HTTPException(status_code=404, detail="产物不存在")
    integrity_locked = _artifact_integrity_locked(artifact)
    if integrity_locked and not body.model_fields_set.issubset({"title"}):
        raise HTTPException(status_code=409, detail="该产物参与审计或定稿完整性校验，只允许修改标题")
    if body.meta is not None and (
        _RESERVED_ARTIFACT_META_KEYS.intersection(body.meta)
        or body.meta.get("generated_by") in _RESERVED_GENERATORS
    ):
        raise HTTPException(status_code=400, detail="meta 包含系统保留的完整性字段")
    content_changed = False
    if body.title is not None:
        if not body.title.strip():
            raise HTTPException(status_code=400, detail="title 不能为空")
        artifact.title = body.title.strip()
    if body.content is not None:
        artifact.content = body.content
        content_changed = True
    if body.markdown_text is not None:
        artifact.markdown_text = body.markdown_text
        content_changed = True
    if body.html_text is not None:
        artifact.html_text = body.html_text
        content_changed = True
    if body.status is not None:
        artifact.status = body.status
    if body.parent_id is not None:
        if body.parent_id:
            parent = await db.get(WritingArtifact, body.parent_id)
            if parent is None or parent.project_id != project_id:
                raise HTTPException(status_code=400, detail="parent_id 无效")
        artifact.parent_id = body.parent_id
    if body.meta is not None:
        artifact.meta = body.meta
    if content_changed:
        artifact.version = (artifact.version or 1) + 1
    await db.commit()
    await db.refresh(artifact)
    return artifact.to_dict()


@router.delete("/{project_id}/artifacts/{artifact_id}", status_code=204)
async def delete_artifact(
    project_id: str,
    artifact_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """删除写作产物。"""
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    artifact = await db.get(WritingArtifact, artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise HTTPException(status_code=404, detail="产物不存在")
    if _artifact_integrity_locked(artifact):
        raise HTTPException(status_code=409, detail="该产物参与结果、审计或定稿完整性校验；请保留历史版本，必要时删除整个项目")
    await db.delete(artifact)
    await db.commit()
    return None


# =====================================================================
# 长期记忆(Memory)
# =====================================================================
@router.get("/{project_id}/memory")
async def get_memory(
    project_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """读取项目长期记忆 JSON。"""
    user_id = await get_current_user_id(authorization, db)
    project = await _get_owned_project(db, project_id, user_id)
    memory = project.memory or {"summary": "", "notes": []}
    # 防御性补全
    memory.setdefault("summary", "")
    memory.setdefault("notes", [])
    return {
        "project_id": project_id,
        "summary": memory.get("summary", ""),
        "notes": memory.get("notes", []),
        "note_count": len(memory.get("notes", [])),
    }


@router.patch("/{project_id}/memory")
async def overwrite_memory(
    project_id: str,
    body: MemoryOverwrite,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """覆写项目记忆(整体替换 summary / notes)。供 UI 手动编辑记忆。"""
    user_id = await get_current_user_id(authorization, db)
    project = await _get_owned_project(db, project_id, user_id)
    memory = project.memory or {"summary": "", "notes": []}
    memory.setdefault("summary", "")
    memory.setdefault("notes", [])
    if body.summary is not None:
        memory["summary"] = body.summary[:5000]  # 上限防滥用
    if body.notes is not None:
        # 限制最多 200 条,每条 text 上限 2000 字
        trimmed = []
        for n in body.notes[-200:]:
            if not isinstance(n, dict):
                continue
            text = str(n.get("text", ""))[:2000]
            if not text:
                continue
            trimmed.append({
                "time": n.get("time", datetime.utcnow().isoformat()),
                "text": text,
                "tag": str(n.get("tag", ""))[:50],
                "source_type": str(n.get("source_type", "user"))[:20],
                "paper_id": n.get("paper_id"),
                "paper_title": str(n.get("paper_title", ""))[:400] or None,
                "page": n.get("page"),
                "source_id": str(n.get("source_id", ""))[:30] or None,
            })
        memory["notes"] = trimmed
    project.memory = memory
    await db.commit()
    await db.refresh(project)
    return {
        "project_id": project_id,
        "summary": memory.get("summary", ""),
        "notes": memory.get("notes", []),
        "note_count": len(memory.get("notes", [])),
    }


@router.post("/{project_id}/memory/note", status_code=201)
async def append_memory_note(
    project_id: str,
    body: MemoryNoteCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """追加一条 memory note(不覆盖已有内容)。

    note 结构:{"time": iso, "text": str, "tag": str}
    summary 字段不在此处更新;由 agent 在合适时机重新生成(后续 Phase 实现)。
    """
    user_id = await get_current_user_id(authorization, db)
    project = await _get_owned_project(db, project_id, user_id)
    memory = project.memory or {"summary": "", "notes": []}
    memory.setdefault("summary", "")
    memory.setdefault("notes", [])
    note = {
        "time": datetime.utcnow().isoformat(),
        "text": body.text[:2000],
        "tag": (body.tag or "")[:50],
        "source_type": (body.source_type or "user")[:20],
        "paper_id": body.paper_id,
        "paper_title": (body.paper_title or "")[:400] or None,
        "page": body.page,
        "source_id": (body.source_id or "")[:30] or None,
    }
    memory["notes"].append(note)
    # 上限 200 条,超出则丢最早的
    if len(memory["notes"]) > 200:
        memory["notes"] = memory["notes"][-200:]
    project.memory = memory
    await db.commit()
    await db.refresh(project)
    return {"project_id": project_id, "note": note, "note_count": len(memory["notes"])}


# =====================================================================
# 自动精读执行器
# =====================================================================
@router.post("/{project_id}/reading-executions", status_code=202)
async def start_reading_execution(
    project_id: str,
    body: ReadingExecutionStart,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    rows = (await db.execute(
        select(ProjectPaper).where(ProjectPaper.project_id == project_id)
    )).scalars().all()
    queued = [pp for pp in rows if (pp.reading_plan or {}).get("status") in {"pending", "reading", "failed"}]
    if not queued:
        raise HTTPException(status_code=400, detail="没有可执行的精读任务，请先生成阅读计划")
    task_id = str(uuid.uuid4())
    data = {
        "task_id": task_id,
        "project_id": project_id,
        "user_id": user_id,
        "status": "queued",
        "control": "run",
        "total": min(len(queued), body.max_items),
        "completed": 0,
        "current_paper_id": None,
        "results": [],
        "error": None,
        "max_items": body.max_items,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    await set_json(f"{READING_EXECUTION_PREFIX}{task_id}", data, READING_EXECUTION_TTL)
    await enqueue_job(
        "project_reading_execution",
        {"task_id": task_id, "project_id": project_id, "user_id": user_id},
    )
    return data


async def _owned_execution(task_id: str, project_id: str, user_id: str) -> dict[str, Any]:
    data = await get_json(f"{READING_EXECUTION_PREFIX}{task_id}")
    if not isinstance(data, dict) or data.get("project_id") != project_id or data.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="精读任务不存在或无访问权限")
    return data


@router.get("/{project_id}/reading-executions/{task_id}")
async def get_reading_execution(
    project_id: str,
    task_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    return await _owned_execution(task_id, project_id, user_id)


@router.post("/{project_id}/reading-executions/{task_id}/pause")
async def pause_reading_execution(
    project_id: str, task_id: str, authorization: str = Header(None), db: AsyncSession = Depends(get_db)
):
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    data = await _owned_execution(task_id, project_id, user_id)
    if data.get("status") not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="当前任务不可暂停")
    data.update({"control": "pause", "updated_at": time.time()})
    await set_json(f"{READING_EXECUTION_PREFIX}{task_id}", data, READING_EXECUTION_TTL)
    return data


@router.post("/{project_id}/reading-executions/{task_id}/resume", status_code=202)
async def resume_reading_execution(
    project_id: str, task_id: str, authorization: str = Header(None), db: AsyncSession = Depends(get_db)
):
    user_id = await get_current_user_id(authorization, db)
    await _get_owned_project(db, project_id, user_id)
    data = await _owned_execution(task_id, project_id, user_id)
    if data.get("status") not in {"paused", "failed"}:
        raise HTTPException(status_code=409, detail="当前任务不可继续或重试")
    data.update({"status": "queued", "control": "run", "error": None, "updated_at": time.time()})
    await set_json(f"{READING_EXECUTION_PREFIX}{task_id}", data, READING_EXECUTION_TTL)
    await enqueue_job(
        "project_reading_execution",
        {"task_id": task_id, "project_id": project_id, "user_id": user_id},
    )
    return data
