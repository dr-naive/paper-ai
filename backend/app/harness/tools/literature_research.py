"""literature_research skill 的 project-scope tool 工厂。

为 agent 提供**项目级**能力:往项目加/移论文、读写长期记忆、保存写作产物。
与 paper_internal/external_literature 不同,这些 tool 不是 SkillRegistry.load_tools 创建的,
而是在 run_lead_agent 里当 project_id 非空时用 closure 追加到 tools 列表(因为 registry
只有 db 参数,无法同时注入 project_id/user_id)。

所有 tool 名统一用 `project_` 前缀,与其他 skill 的 tool 无冲突。
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from langchain_core.tools import StructuredTool
from pydantic.v1 import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.config import settings
from app.job_queue import enqueue_job
from app.services.remote_paper_import import normalize_arxiv_id
from app.utils.task_manager import create_task, update_task
from app.models.project import (
    ARTIFACT_STATUS_DRAFT,
    ARTIFACT_STATUS_READY,
    PAPER_ROLE_RELATED,
    PROJECT_PHASE_WRITING,
    PROJECT_PHASE_REFINEMENT,
    ProjectPaper,
    ResearchProject,
    WritingArtifact,
)
from app.models.research import MemoryItem
from app.research.context.manager import ProjectContextManager
from app.research.context.schemas import DISCOVERY_MEMORY_TYPES
from app.utils.manuscript_export import build_bibliography

logger = logging.getLogger(__name__)

_VALID_PAPER_ROLES = {"core", "related", "background"}
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


def _as_dict(value: Any) -> dict[str, Any]:
    """Normalize nested LangChain/Pydantic tool arguments to plain dictionaries."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, BaseModel):
        return value.dict()
    try:
        return dict(value)
    except (TypeError, ValueError):
        raise TypeError(f"expected mapping-like tool argument, got {type(value).__name__}")


# =====================================================================
# Pydantic v1 args_schema(与 LangChain Tool 兼容)
# =====================================================================
class ProjectAddPaperInput(BaseModel):
    """向当前研究项目的文档库加入一篇用户已有的论文。
    加入后,这篇论文会出现在项目的"文档库"中,供后续阅读、对比、引用。
    """
    paper_id: str = Field(..., description="要加入的论文 ID,UUID 格式。必须是当前用户已上传并成功解析的论文。")
    role: str = Field(
        PAPER_ROLE_RELATED,
        description="这篇论文在项目中的角色:core(核心文献,重点阅读) / related(相关工作,参考对比) / background(背景知识,辅助理解)。默认 related。",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="自定义标签数组,便于项目文档库筛选。例如:['对比实验','数据集','SOTA']。",
    )
    notes: str = Field("", description="用户对这篇论文的备注,例如:'与研究主题高度相关,重点看第4节'。默认空。")
    reading_priority: int = Field(
        3,
        ge=1, le=5,
        description="阅读优先级,1-5 档,越高越先读。默认 3。",
    )


class ProjectRemovePaperInput(BaseModel):
    """从当前研究项目的文档库中移除一篇论文。
    只移除关联,不删除用户的论文本体,后续还可以重新加入。
    """
    paper_id: str = Field(..., description="要移除的论文 ID。")


class ProjectImportArxivPaperInput(BaseModel):
    arxiv_id: str = Field(..., min_length=5, max_length=80, description="arXiv ID，例如 2401.12345 或 cs/9901001；不接受任意 URL。")
    role: str = Field(PAPER_ROLE_RELATED, description="core/related/background")
    tags: list[str] = Field(default_factory=list)
    notes: str = Field("", max_length=2000)
    reading_priority: int = Field(3, ge=1, le=5)


class ProjectAppendMemoryInput(BaseModel):
    """向项目的 typed Literature Memory 追加一条长期有效的信息。"""
    note: str = Field(
        ..., min_length=1, max_length=2000,
        description="要写入记忆的要点。建议用短句,可包含关键数据点。例如:'FakeShield 论文在 MMTD-Set 上 F1 达到 0.93,是 SOTA。'",
    )
    tag: str = Field(
        "",
        description="可选的细分标签,例如 keyword:retrieval 或 direction:multimodal。不要把原始推理写入记忆。",
    )
    memory_type: str = Field(
        "",
        description="必填的稳定类型: literature_intent / literature_preference / literature_exclusion / project_decision。",
    )
    source_type: str = Field(
        "agent",
        description="来源类型:user/agent/paper。来自论文事实时必须传 paper。",
    )
    paper_id: Optional[str] = Field(None, description="来源论文 ID；source_type=paper 时必填。")
    paper_title: Optional[str] = Field(None, description="来源论文标题。")
    page: Optional[int] = Field(None, ge=1, description="来源 PDF 页码。")
    source_id: Optional[str] = Field(None, description="本次检索中的来源编号，如 S3。")


class ProjectReadMemoryInput(BaseModel):
    """读取项目的完整长期记忆。
    在开始新的分析前,如果不确定之前做了哪些调研,调这个 tool 回顾。
    """
    # 无参数


class ProjectSearchContentInput(BaseModel):
    """在当前项目的多篇论文中检索可引用证据。"""
    query: str = Field(..., min_length=1, description="研究问题、比较维度或要查找的事实。")
    intent: str = Field(
        "general",
        description="检索意图:general/comparison/table/image。跨论文比较建议传 comparison。",
    )
    top_k: int = Field(10, ge=2, le=20, description="最终返回的跨论文证据数，默认 10。")
    max_papers: int = Field(5, ge=1, le=5, description="本次最多检索多少篇候选项目论文，默认 5。")


class ProjectSaveArtifactInput(BaseModel):
    """向项目的"写作产物"库保存一份结果。
    当你帮用户生成了文献综述、章节大纲、参考文献列表等结构化结果时,
    用这个 tool 保存下来,用户可以在"项目工作区 → 写作产物" Tab 中查看、下载、编辑。
    """
    artifact_type: str = Field(
        ...,
        description="产物类型。可选:outline(章节大纲)、literature_review(文献综述)、reference_list(参考文献列表)、section_draft(章节草稿)、full_draft(完整草稿)、review_report(审稿报告)、submission_suggestion(投稿建议)。",
    )
    title: str = Field(
        ..., min_length=1, max_length=400,
        description="产物标题。建议简洁明了,例如:'MLLM 伪造检测文献综述 v1' 或 '论文第一章 引言草稿'。",
    )
    markdown_text: str = Field(
        ..., min_length=1,
        description="产物的 Markdown 全文。这是用户实际会查看/下载的内容,必须完整可阅读。",
    )
    content: Optional[dict[str, Any]] = Field(
        default=None,
        description="(可选)产物的结构化数据,供 UI 分段渲染。例如大纲可传 {sections:[{level,title,desc},...]}。不传则仅保存 Markdown。",
    )


class ProjectSavePaperCardInput(BaseModel):
    """保存一篇项目论文的结构化阅读卡片。"""
    paper_id: str = Field(..., description="项目文档库中的论文 ID。")
    summary: str = Field("", max_length=2000, description="论文核心内容摘要。")
    research_questions: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    contributions: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(
        default_factory=list,
        description="证据数组，每项建议包含 source_id/page/section/text。",
    )


class ProjectSaveResearchBriefInput(BaseModel):
    """保存检索之前的研究任务书，区分用户约束、初始假设和待验证信息。"""
    title: str = Field("研究任务书", min_length=1, max_length=400)
    topic: str = Field(..., min_length=1, max_length=1000, description="经澄清后的研究题材。")
    objective: str = Field(..., min_length=1, max_length=2000, description="本轮调研要支持的决策或最终目标。")
    known_context: list[str] = Field(default_factory=list, description="用户已明确提供的背景；不得混入模型猜测。")
    constraints: list[str] = Field(default_factory=list, description="时间、数据、算力、语言、场景、学科或投稿约束。")
    unknowns: list[str] = Field(default_factory=list, description="仍需询问用户或通过检索验证的问题。")
    seed_keywords: list[str] = Field(default_factory=list, description="中英文关键词、同义词和缩写。")
    search_queries: list[str] = Field(..., min_items=1, description="可直接用于学术搜索的检索式。")
    inclusion_criteria: list[str] = Field(default_factory=list)
    exclusion_criteria: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list, description="评价候选选题的创新性、证据、可行性与风险维度。")
    next_actions: list[str] = Field(default_factory=list)


class LiteratureSearchRun(BaseModel):
    source: str = Field(..., min_length=1, max_length=80, description="arxiv/semantic_scholar/crossref/其他学术来源。")
    query: str = Field(..., min_length=1, max_length=1000)
    result_count: int = Field(..., ge=0)
    filters: dict[str, Any] = Field(default_factory=dict)


class LiteratureCandidate(BaseModel):
    title: str = Field(..., min_length=1, max_length=1000)
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = Field(None, ge=1800, le=2200)
    venue: str = Field("", max_length=300)
    arxiv_id: str = Field("", max_length=80)
    doi: str = Field("", max_length=300)
    url: str = Field("", max_length=2000)
    abstract: str = Field("", max_length=5000)
    decision: Literal["include", "exclude", "maybe"]
    reason: str = Field(..., min_length=1, max_length=2000)
    relevance_score: int = Field(..., ge=0, le=100)
    coverage: list[str] = Field(default_factory=list, description="该候选覆盖的研究问题、方法、数据或反例维度。")


class ProjectSaveLiteratureScreeningInput(BaseModel):
    """保存外部检索运行和候选论文筛选决策。"""
    title: str = Field("候选文献筛选台账", min_length=1, max_length=400)
    query_runs: list[LiteratureSearchRun] = Field(..., min_items=1)
    candidates: list[LiteratureCandidate] = Field(..., min_items=1)
    coverage_summary: list[dict[str, Any]] = Field(default_factory=list, description="维度覆盖摘要，字段建议为 dimension/count/gap/next_query。")
    stopping_reason: str = Field("", max_length=2000, description="为何继续检索或为何当前覆盖足够。")


class ProjectSaveResearchMapInput(BaseModel):
    """保存用于选题决策的结构化领域地图。"""
    title: str = Field("领域研究地图", min_length=1, max_length=400)
    topic_summary: str = Field(..., min_length=1, max_length=3000)
    keywords: list[str] = Field(default_factory=list, description="中英文关键词和检索词。")
    research_questions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="研究问题，建议字段:question/importance/evidence/source_ids。",
    )
    method_families: list[dict[str, Any]] = Field(
        default_factory=list,
        description="方法族，建议字段:name/strengths/weaknesses/papers。",
    )
    datasets: list[dict[str, Any]] = Field(
        default_factory=list,
        description="数据集，建议字段:name/task/scale/limitations/papers。",
    )
    research_gaps: list[dict[str, Any]] = Field(
        default_factory=list,
        description="研究空白，建议字段:gap/evidence/opportunity/risk/source_ids。",
    )
    candidate_topics: list[dict[str, Any]] = Field(
        default_factory=list,
        description="候选选题，建议字段:title/question/novelty/feasibility/next_step。",
    )
    evidence: list[dict[str, Any]] = Field(
        default_factory=list,
        description="支撑地图的来源，包含 paper_id/paper_title/source_id/page。",
    )


class ReadingPlanItem(BaseModel):
    paper_id: str
    order: int = Field(..., ge=1)
    priority: int = Field(3, ge=1, le=5)
    reason: str = Field("", max_length=1000)
    focus: list[str] = Field(default_factory=list, description="重点章节、方法或实验。")
    questions: list[str] = Field(default_factory=list, description="精读后需要回答的问题。")


class ProjectSaveReadingPlanInput(BaseModel):
    """把项目论文编排成可执行的精读队列。"""
    title: str = Field("项目精读计划", min_length=1, max_length=400)
    objective: str = Field(..., min_length=1, max_length=2000)
    items: list[ReadingPlanItem] = Field(..., min_items=1)


class ProjectBuildEvidenceMatrixInput(BaseModel):
    """从已保存论文卡片构建跨论文证据矩阵。"""
    title: str = Field("跨论文证据矩阵", min_length=1, max_length=400)
    research_question: str = Field(..., min_length=1, max_length=1000)
    conflicts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="冲突判断，字段:claim_a/claim_b/explanation/paper_ids/source_ids/confidence。",
    )
    evidence_gaps: list[dict[str, Any]] = Field(
        default_factory=list,
        description="证据缺口，字段:dimension/missing_evidence/affected_questions/next_action。",
    )


class ProjectSaveExperimentDesignInput(BaseModel):
    """保存由证据矩阵支持的可证伪研究与实验设计。"""
    title: str = Field("研究假设与实验设计", min_length=1, max_length=400)
    research_question: str = Field(..., min_length=1, max_length=1000)
    hypothesis: str = Field(..., min_length=1, max_length=2000)
    rationale: str = Field(..., min_length=1, max_length=3000)
    independent_variables: list[str] = Field(default_factory=list)
    dependent_variables: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    datasets: list[dict[str, Any]] = Field(default_factory=list)
    baselines: list[dict[str, Any]] = Field(default_factory=list)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    experiment_steps: list[str] = Field(..., min_items=1)
    ablations: list[dict[str, Any]] = Field(default_factory=list)
    success_criteria: list[str] = Field(..., min_items=1)
    falsification_criteria: list[str] = Field(..., min_items=1)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(
        default_factory=list,
        description="假设依据，字段:paper_id/source_id/claim。",
    )
    requires_empirical_results: bool = Field(True, description="实证/实验论文为 true；纯理论、观点或无需新结果的综述可为 false。")


class ExperimentResultSource(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=80)
    source_type: Literal["uploaded_file", "user_report", "experiment_tracker", "database_export", "repository"]
    locator: str = Field(..., min_length=1, max_length=2000, description="文件名、任务 ID、追踪运行 URL、数据库导出名或仓库提交。")
    checksum: str = Field("", max_length=128, description="若有原始文件，建议填写 SHA-256。")
    recorded_at: str = Field("", max_length=80)


class ExperimentMetricResult(BaseModel):
    metric: str = Field(..., min_length=1, max_length=200)
    value: float
    unit: str = Field("", max_length=80)
    dataset: str = Field("", max_length=300)
    split: str = Field("", max_length=100)
    method: str = Field("", max_length=300)
    baseline: str = Field("", max_length=300)
    sample_size: Optional[int] = Field(None, ge=1)
    uncertainty: str = Field("", max_length=300, description="标准差、置信区间或统计检验摘要。")
    source_id: str = Field(..., min_length=1, max_length=80, description="必须指向 sources 中的一项。")


class ProjectSaveExperimentResultsInput(BaseModel):
    """登记用户或系统提供的真实研究结果；不负责执行实验，也不允许生成预测数值。"""
    experiment_design_id: str
    title: str = Field("实验结果登记", min_length=1, max_length=400)
    run_id: str = Field(..., min_length=1, max_length=300)
    sources: list[ExperimentResultSource] = Field(..., min_items=1)
    metrics: list[ExperimentMetricResult] = Field(default_factory=list)
    hypothesis_outcome: Literal["supported", "not_supported", "mixed", "inconclusive"]
    qualitative_findings: list[str] = Field(default_factory=list)
    protocol_deviations: list[str] = Field(default_factory=list)
    analysis_notes: list[str] = Field(default_factory=list)


class BlueprintSection(BaseModel):
    section_id: str = Field(..., min_length=1, max_length=80)
    title: str = Field(..., min_length=1, max_length=300)
    order: int = Field(..., ge=1)
    purpose: str = Field(..., min_length=1, max_length=1500)
    key_claims: list[str] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    citation_needs: list[str] = Field(default_factory=list)
    word_target: int = Field(800, ge=100, le=10000)


class ProjectSavePaperBlueprintInput(BaseModel):
    title: str = Field("论文写作蓝图", min_length=1, max_length=400)
    working_title: str = Field(..., min_length=1, max_length=500)
    central_claim: str = Field(..., min_length=1, max_length=2000)
    target_audience: str = Field("", max_length=1000)
    target_venue: str = Field("", max_length=300)
    sections: list[BlueprintSection] = Field(..., min_items=3)


class ProjectSaveSectionDraftInput(BaseModel):
    blueprint_id: str
    section_id: str
    title: str = Field(..., min_length=1, max_length=400)
    markdown_text: str = Field(..., min_length=1)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    contains_empirical_results: bool = False
    experiment_results_id: str = Field("", max_length=80, description="包含实证数值时必须指向当前项目的 experiment_results 产物。")
    results_source: str = Field("", max_length=1000, description="兼容性说明字段；不能替代 experiment_results_id。")


class ProjectAssembleFullDraftInput(BaseModel):
    blueprint_id: str
    title: str = Field(..., min_length=1, max_length=400)
    allow_unresolved_placeholders: bool = False


class ProjectBuildReferenceListInput(BaseModel):
    blueprint_id: str
    title: str = Field("参考文献列表", min_length=1, max_length=400)


class DraftAuditIssue(BaseModel):
    severity: str = Field(..., description="blocker/major/minor")
    category: str = Field(..., description="citation/evidence/logic/structure/style/result_integrity")
    section_id: str = Field("", max_length=80)
    description: str = Field(..., min_length=1, max_length=1000)
    recommendation: str = Field(..., min_length=1, max_length=1000)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)


class ProjectAuditFullDraftInput(BaseModel):
    full_draft_id: str
    title: str = Field("全文事实与引用审计", min_length=1, max_length=400)
    issues: list[DraftAuditIssue] = Field(default_factory=list)


class ProjectFinalizeManuscriptInput(BaseModel):
    full_draft_id: str
    review_report_id: str
    title: str = Field(..., min_length=1, max_length=400)


# =====================================================================
# Tool 工厂
# =====================================================================
def make_project_tools(db: AsyncSession, project_id: str, user_id: str) -> list[StructuredTool]:
    """创建 project-scope 的 21 个 agent tool。

    Args:
        db: 异步 db session(由 API 层/harness 提供)
        project_id: 必须是已存在的项目(且 owner == user_id)。
            调用方(lead_agent.run_lead_agent)已做所有权校验。
        user_id: 当前用户 id,校验论文所有权时用。
    """
    _pid = project_id
    _uid = user_id
    _integrity_token = object()

    async def _assert_owned():
        # 每次 tool 调用都做一次权限校验,防止 agent 用错误 project_id 写入
        project = await db.get(ResearchProject, _pid)
        if project is None or project.user_id != _uid:
            raise RuntimeError(f"project {_pid} 不存在或不属于用户 {_uid}")
        return project

    async def add_paper_impl(**kwargs: Any) -> str:
        await _assert_owned()
        pid = kwargs["paper_id"]
        role = kwargs.get("role") or PAPER_ROLE_RELATED
        if role not in _VALID_PAPER_ROLES:
            return f"错误:非法 role={role},合法值为 core/related/background"
        # 校验论文存在且属于当前用户
        paper = await db.get(Paper, pid)
        if paper is None or paper.user_id != _uid:
            return f"错误:论文 {pid} 不存在或不属于当前用户"
        # 幂等:已存在则更新
        existing = (await db.execute(
            select(ProjectPaper).where(
                ProjectPaper.project_id == _pid, ProjectPaper.paper_id == pid
            )
        )).scalars().first()
        if existing:
            existing.role = role
            existing.tags = kwargs.get("tags") or []
            existing.notes = kwargs.get("notes") or ""
            existing.reading_priority = kwargs.get("reading_priority") or 3
            project_paper = existing
            msg = (f"已更新项目中论文 role={role} tags={existing.tags} "
                   f"priority={existing.reading_priority}。")
        else:
            pp = ProjectPaper(
                project_id=_pid,
                paper_id=pid,
                role=role,
                tags=kwargs.get("tags") or [],
                notes=kwargs.get("notes") or "",
                reading_priority=kwargs.get("reading_priority") or 3,
            )
            db.add(pp)
            project_paper = pp
            msg = f"已成功加入论文到项目。标题:{paper.title[:80]}{'...' if len(paper.title or '')>80 else ''}"
        # 顺便更新项目时间
        proj = await db.get(ResearchProject, _pid)
        if proj is not None:
            proj.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        if not (project_paper.analysis_card or {}).get("paper_profile"):
            from app.research.context.paper_profile import PaperProfileNotReadyError, PaperProfileService

            try:
                await PaperProfileService(db).request_generation(
                    project_id=_pid,
                    paper_id=pid,
                    user_id=_uid,
                )
            except PaperProfileNotReadyError:
                logger.info("Project Paper 尚未完成解析，暂不生成 Profile paper_id=%s", pid)
            except Exception:
                logger.exception("Project Paper Profile 调度失败 paper_id=%s", pid)
        return msg

    async def search_content_impl(**kwargs: Any) -> str:
        await _assert_owned()
        query = str(kwargs["query"]).strip()
        intent = str(kwargs.get("intent") or "general")
        top_k = int(kwargs.get("top_k") or 10)
        max_papers = int(kwargs.get("max_papers") or 5)
        context = await ProjectContextManager(db).build_writing_context(
            project_id=_pid,
            user_id=_uid,
            instruction=query,
            intent=intent,
            max_candidates=max_papers,
            top_k=top_k,
        )
        chunks = []
        for index, evidence in enumerate(context.evidence, start=1):
            item = evidence.model_dump(mode="json")
            item.update({
                "content": item["snippet"],
                "section": item["section_title"],
                "page": item["page_number"],
                "source_id": f"S{index}",
                "project_rerank_score": item["retrieval_score"],
            })
            chunks.append(item)
        return json.dumps({
            "chunks": chunks,
            "paper_count": len({item["paper_id"] for item in chunks}),
            "candidate_paper_count": len(context.candidate_papers),
            "query": query,
            "status": context.status,
        }, ensure_ascii=False)

    async def remove_paper_impl(**kwargs: Any) -> str:
        await _assert_owned()
        pid = kwargs["paper_id"]
        pp = (await db.execute(
            select(ProjectPaper).where(
                ProjectPaper.project_id == _pid, ProjectPaper.paper_id == pid
            )
        )).scalars().first()
        if pp is None:
            return f"提示:论文 {pid} 本来就不在项目文档库中。"
        await db.delete(pp)
        proj = await db.get(ResearchProject, _pid)
        if proj is not None:
            proj.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        return f"已从项目文档库移除论文 {pid}。"

    async def import_arxiv_paper_impl(**kwargs: Any) -> str:
        project = await _assert_owned()
        role = str(kwargs.get("role") or PAPER_ROLE_RELATED)
        if role not in _VALID_PAPER_ROLES:
            return "错误:role 必须是 core/related/background。"
        try:
            arxiv_id = normalize_arxiv_id(str(kwargs["arxiv_id"]))
        except ValueError as exc:
            return f"错误:{exc}"
        source_url = f"https://arxiv.org/abs/{arxiv_id}"
        existing = (await db.execute(select(Paper).where(
            Paper.user_id == _uid, Paper.source_url == source_url,
        ))).scalars().first()
        if existing:
            result = await add_paper_impl(
                paper_id=str(existing.id), role=role, tags=kwargs.get("tags") or [],
                notes=kwargs.get("notes") or "", reading_priority=kwargs.get("reading_priority") or 3,
            )
            return f"该 arXiv 论文已在用户论文库中。{result}"
        preferences = dict(project.preferences or {})
        imports = [dict(item) for item in preferences.get("paper_imports") or []]
        pending = next((item for item in imports if item.get("arxiv_id") == arxiv_id and item.get("status") in {"queued", "processing"}), None)
        if pending:
            return f"该论文正在导入，task_id={pending.get('task_id')}，请等待解析完成。"
        paper_id = str(uuid.uuid4())
        task = create_task(paper_id, _uid)
        import_item = {
            "arxiv_id": arxiv_id, "paper_id": paper_id, "task_id": task.task_id,
            "status": "queued", "role": role, "tags": list(kwargs.get("tags") or []),
            "notes": str(kwargs.get("notes") or ""), "reading_priority": int(kwargs.get("reading_priority") or 3),
            "source_url": source_url, "updated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        imports.append(import_item)
        preferences["paper_imports"] = imports[-30:]
        project.preferences = preferences
        await db.commit()
        try:
            await enqueue_job("arxiv_import", {
                "paper_id": paper_id, "user_id": _uid,
                "project_id": _pid, "arxiv_id": arxiv_id, "source_url": source_url,
                "role": role, "tags": import_item["tags"], "notes": import_item["notes"],
                "reading_priority": import_item["reading_priority"],
                "initial_counts": {"original_filename": f"arxiv-{arxiv_id}.pdf", "remote_source": "arxiv"},
            }, job_id=task.task_id)
        except Exception:
            update_task(task.task_id, status="failed", progress=0, message="导入任务入队失败")
            import_item["status"] = "failed"
            project.preferences = {**preferences, "paper_imports": imports[-30:]}
            await db.commit()
            return "错误:论文处理 Worker 暂时不可用。"
        return (
            f"arXiv:{arxiv_id} 导入任务已创建，正在后台安全下载。"
            f"task_id={task.task_id}，paper_id={paper_id}。"
            "解析完成后会自动加入当前项目文档库。"
        )

    async def append_memory_impl(**kwargs: Any) -> str:
        project = await _assert_owned()
        text = kwargs["note"].strip()[:2000]
        if not text:
            return "错误:note 内容不能为空。"
        tag = (kwargs.get("tag") or "").strip()[:50]
        memory_type = (kwargs.get("memory_type") or "").strip()
        if not memory_type and tag in DISCOVERY_MEMORY_TYPES:
            memory_type = tag
        if memory_type not in DISCOVERY_MEMORY_TYPES:
            return (
                "错误:必须提供稳定 memory_type: "
                "literature_intent/literature_preference/literature_exclusion/project_decision。"
                "普通聊天、原始搜索结果和 agent 推理不能写入 Literature Memory。"
            )
        source_type = (kwargs.get("source_type") or "agent").strip()[:20]
        paper_id = kwargs.get("paper_id") or None
        if source_type == "paper" and not paper_id:
            return "错误:来源类型为 paper 时必须提供 paper_id。"
        if paper_id:
            owned_paper = await db.get(Paper, paper_id)
            if owned_paper is None or owned_paper.user_id != _uid:
                return "错误:来源论文不存在或无访问权限。"
        tags = []
        if tag:
            tags.append(tag)
        if paper_id:
            tags.append(f"paper_id:{paper_id}")
        if kwargs.get("paper_title"):
            tags.append(f"paper_title:{str(kwargs['paper_title'])[:200]}")
        if kwargs.get("page"):
            tags.append(f"page:{int(kwargs['page'])}")
        item = MemoryItem(
            project_id=_pid,
            user_id=_uid,
            type=memory_type,
            title=tag or memory_type,
            content=text,
            source_type=source_type,
            source_id=(kwargs.get("source_id") or paper_id or None),
            confidence=1.0,
            tags=tags,
            created_by="agent",
        )
        db.add(item)
        project.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        return f"已写入 typed Literature Memory(type={memory_type})。\n写入内容: {text}"

    async def save_paper_card_impl(**kwargs: Any) -> str:
        await _assert_owned()
        paper_id = kwargs["paper_id"]
        pp = (await db.execute(select(ProjectPaper).where(
            ProjectPaper.project_id == _pid,
            ProjectPaper.paper_id == paper_id,
        ))).scalars().first()
        if pp is None:
            return f"错误:论文 {paper_id} 不在当前项目文档库中。"
        list_fields = (
            "research_questions", "methods", "datasets", "metrics",
            "contributions", "findings", "limitations",
        )
        card: dict[str, Any] = {
            "summary": str(kwargs.get("summary") or "")[:2000],
            "evidence": list(kwargs.get("evidence") or [])[:30],
            "updated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "generated_by": "agent",
        }
        existing_profile = (pp.analysis_card or {}).get("paper_profile")
        if isinstance(existing_profile, dict):
            card["paper_profile"] = existing_profile
        for field_name in list_fields:
            card[field_name] = [str(value)[:1000] for value in (kwargs.get(field_name) or [])[:30]]
        pp.analysis_card = card
        plan = dict(pp.reading_plan or {})
        if plan:
            plan["status"] = "completed"
            plan["completed_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            plan["updated_at"] = plan["completed_at"]
            pp.reading_plan = plan
        await db.commit()
        return (
            f"已保存论文卡片: paper_id={paper_id},"
            f"发现 {len(card['findings'])} 条,证据 {len(card['evidence'])} 条。"
        )

    async def read_memory_impl(**kwargs: Any) -> str:
        project = await _assert_owned()
        typed_rows = (await db.execute(
            select(MemoryItem).where(
                MemoryItem.project_id == _pid,
                MemoryItem.user_id == _uid,
                MemoryItem.superseded_by.is_(None),
                MemoryItem.type.in_(DISCOVERY_MEMORY_TYPES),
            ).order_by(MemoryItem.updated_at.desc()).limit(50)
        )).scalars().all()
        if typed_rows:
            lines = ["项目 Literature Memory(仅稳定类型):"]
            for item in reversed(typed_rows):
                lines.append(f"  - [{item.type}] {(item.content or '')[:500]}")
            return "\n".join(lines)
        memory = project.memory or {"summary": "", "notes": []}
        summary = memory.get("summary", "") or ""
        notes = memory.get("notes") or []
        lines = []
        if summary:
            lines.append(f"记忆摘要:\n{summary}")
        if notes:
            lines.append(f"\n记忆条目(最近 {len(notes)} 条):")
            # 取最近 50 条,避免 token 爆炸
            for n in notes[-50:]:
                t = n.get("time", "")[:16]
                tag = f"[{n.get('tag', '')}] " if n.get("tag") else ""
                txt = (n.get("text") or "")[:500]
                lines.append(f"  - {t} {tag}{txt}")
        if not lines:
            return "项目记忆目前为空,还没有写入任何调研要点。"
        return "\n".join(lines)

    async def save_artifact_impl(**kwargs: Any) -> str:
        project = await _assert_owned()
        atype = kwargs.get("artifact_type", "")
        if atype not in _VALID_ARTIFACT_TYPES:
            return f"错误:非法 artifact_type={atype},合法值为 {sorted(_VALID_ARTIFACT_TYPES)}"
        if atype in {"experiment_results", "final_manuscript"} and kwargs.pop("_integrity_token", None) is not _integrity_token:
            return f"错误:{atype} 只能通过对应的受约束工具生成，不能使用 project_save_artifact 绕过完整性检查。"
        title = (kwargs.get("title") or "").strip()[:400]
        if not title:
            return "错误:title 不能为空。"
        markdown = (kwargs.get("markdown_text") or "").strip()
        if not markdown:
            return "错误:markdown_text 内容不能为空,用户需要看到实际的内容。"
        content = kwargs.get("content") or {}

        # 是否更新已有的同类型+同标题(简单去重策略:同 project + 同 type + 同 title 的最近 1 条覆盖)
        existing = (await db.execute(
            select(WritingArtifact).where(
                WritingArtifact.project_id == _pid,
                WritingArtifact.artifact_type == atype,
                WritingArtifact.title == title,
            ).order_by(WritingArtifact.updated_at.desc()).limit(1)
        )).scalars().first()
        if existing:
            existing.content = content
            existing.markdown_text = markdown
            existing.version = (existing.version or 1) + 1
            existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()
            await db.refresh(existing)
            return (f"已更新写作产物(artifact_type={atype},title={title},version={existing.version})。\n"
                    f"产物 ID: {existing.id}\n"
                    f"Markdown 长度: {len(markdown)} 字符。已保存到用户的项目工作区。")
        artifact = WritingArtifact(
            project_id=_pid,
            author_id=_uid,
            artifact_type=atype,
            title=title,
            version=1,
            parent_id=None,
            content=content,
            markdown_text=markdown,
            html_text="",
            status=ARTIFACT_STATUS_DRAFT,
            meta={"generated_by": "agent", "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()},
        )
        db.add(artifact)
        project.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        # 保存了实质性写作产物时,自动把阶段推进到 writing(如果还在 research/reading)
        if project.phase in {"research", "reading"} and atype in {
            "literature_review", "outline", "reference_list", "paper_blueprint", "section_draft", "full_draft",
        }:
            project.phase = PROJECT_PHASE_WRITING
        await db.commit()
        await db.refresh(artifact)
        return (f"已保存写作产物(artifact_type={atype},title={title})。\n"
                f"产物 ID: {artifact.id}\n"
                f"Markdown 长度: {len(markdown)} 字符。已保存到用户的项目工作区。")

    async def save_research_brief_impl(**kwargs: Any) -> str:
        title = str(kwargs.get("title") or "研究任务书").strip()
        content = {
            "topic": str(kwargs.get("topic") or "").strip(),
            "objective": str(kwargs.get("objective") or "").strip(),
            **{
                key: [str(value).strip() for value in list(kwargs.get(key) or []) if str(value).strip()]
                for key in (
                    "known_context", "constraints", "unknowns", "seed_keywords", "search_queries",
                    "inclusion_criteria", "exclusion_criteria", "evaluation_criteria", "next_actions",
                )
            },
        }
        sections = [
            f"# {title}", "", "## 题材", "", content["topic"], "",
            "## 调研目标", "", content["objective"], "",
        ]
        for heading, key in (
            ("已知背景", "known_context"), ("约束", "constraints"), ("待确认与待验证", "unknowns"),
            ("种子关键词", "seed_keywords"), ("检索式", "search_queries"), ("纳入标准", "inclusion_criteria"),
            ("排除标准", "exclusion_criteria"), ("选题评价准则", "evaluation_criteria"), ("下一步", "next_actions"),
        ):
            if content[key]:
                sections.extend([f"## {heading}", "", *[f"- {value}" for value in content[key]], ""])
        return await save_artifact_impl(
            artifact_type="research_brief", title=title,
            markdown_text="\n".join(sections).strip(), content=content,
        )

    async def save_research_map_impl(**kwargs: Any) -> str:
        """Normalize a domain map and persist it through the artifact path."""
        title = (kwargs.get("title") or "领域研究地图").strip()
        content = {
            key: kwargs.get(key) or ([] if key != "topic_summary" else "")
            for key in (
                "topic_summary", "keywords", "research_questions", "method_families",
                "datasets", "research_gaps", "candidate_topics", "evidence",
            )
        }

        def item_text(item: Any, *keys: str) -> str:
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                return str(next((item.get(key) for key in keys if item.get(key)), ""))
            return str(item)

        sections = [f"# {title}", "", str(content["topic_summary"]), ""]
        if content["keywords"]:
            sections.extend(["## 关键词", "", "、".join(map(str, content["keywords"])), ""])
        for heading, key, names in (
            ("研究问题", "research_questions", ("question", "title")),
            ("方法版图", "method_families", ("name", "method")),
            ("数据集", "datasets", ("name", "dataset")),
            ("研究空白", "research_gaps", ("gap", "title")),
            ("候选选题", "candidate_topics", ("title", "question")),
        ):
            values = [item_text(item, *names) for item in content[key]]
            values = [value for value in values if value]
            if values:
                sections.extend([f"## {heading}", "", *[f"- {value}" for value in values], ""])
        return await save_artifact_impl(
            artifact_type="research_map",
            title=title,
            markdown_text="\n".join(sections).strip(),
            content=content,
        )

    async def save_literature_screening_impl(**kwargs: Any) -> str:
        brief = (await db.execute(
            select(WritingArtifact)
            .where(WritingArtifact.project_id == _pid, WritingArtifact.artifact_type == "research_brief")
            .order_by(WritingArtifact.updated_at.desc(), WritingArtifact.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if brief is None:
            return "错误:请先用 project_save_research_brief 保存研究任务书，再执行候选文献筛选。"

        query_runs = [_as_dict(item) for item in list(kwargs.get("query_runs") or [])]
        raw_candidates = [_as_dict(item) for item in list(kwargs.get("candidates") or [])]
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw_candidates:
            arxiv_id = str(item.get("arxiv_id") or "").strip().lower()
            doi = str(item.get("doi") or "").strip().lower().removeprefix("https://doi.org/")
            title = re.sub(r"\W+", "", str(item.get("title") or "").lower())
            identity = f"arxiv:{arxiv_id}" if arxiv_id else f"doi:{doi}" if doi else f"title:{title}"
            if identity in seen:
                continue
            seen.add(identity)
            normalized = dict(item)
            normalized["arxiv_id"] = arxiv_id
            normalized["doi"] = doi
            normalized["authors"] = [str(value)[:300] for value in list(item.get("authors") or [])[:50]]
            normalized["coverage"] = [str(value)[:300] for value in list(item.get("coverage") or [])[:30]]
            candidates.append(normalized)

        counts = {decision: sum(1 for item in candidates if item.get("decision") == decision)
                  for decision in ("include", "exclude", "maybe")}
        title = str(kwargs.get("title") or "候选文献筛选台账").strip()
        markdown = [
            f"# {title}", "", f"关联研究任务书：{brief.title} v{brief.version}", "",
            "## 检索记录", "",
            *[f"- {item.get('source')}：`{item.get('query')}`（{item.get('result_count', 0)} 条）" for item in query_runs],
            "", "## 筛选结果", "",
        ]
        labels = {"include": "纳入", "exclude": "排除", "maybe": "待定"}
        for item in candidates:
            identifier = item.get("arxiv_id") or item.get("doi") or item.get("url") or "仅标题"
            markdown.extend([
                f"### [{labels.get(str(item.get('decision')), '待定')}] {item.get('title')}",
                f"- 标识：{identifier}", f"- 相关度：{item.get('relevance_score', 0)}/100",
                f"- 理由：{item.get('reason')}",
                f"- 覆盖：{'；'.join(item.get('coverage') or []) or '未标注'}", "",
            ])
        content = {
            "research_brief_id": str(brief.id), "research_brief_version": brief.version,
            "query_runs": query_runs, "candidates": candidates,
            "coverage_summary": [_as_dict(item) for item in list(kwargs.get("coverage_summary") or [])],
            "stopping_reason": str(kwargs.get("stopping_reason") or "").strip(),
            "included_count": counts["include"], "excluded_count": counts["exclude"],
            "maybe_count": counts["maybe"], "deduplicated_count": len(raw_candidates) - len(candidates),
        }
        return await save_artifact_impl(
            artifact_type="literature_screening", title=title,
            markdown_text="\n".join(markdown).strip(), content=content,
        )

    async def save_reading_plan_impl(**kwargs: Any) -> str:
        """Validate project papers, then replace their project-scoped queue entries."""
        await _assert_owned()
        raw_items = [_as_dict(item) for item in list(kwargs.get("items") or [])]
        project_rows = (await db.execute(
            select(ProjectPaper, Paper)
            .join(Paper, Paper.id == ProjectPaper.paper_id)
            .where(ProjectPaper.project_id == _pid, Paper.user_id == _uid)
        )).all()
        by_paper_id = {str(pp.paper_id): (pp, paper) for pp, paper in project_rows}
        requested_ids = [str(item.get("paper_id")) for item in raw_items]
        missing = [paper_id for paper_id in requested_ids if paper_id not in by_paper_id]
        if missing:
            return f"错误:这些论文不在当前项目文档库中:{missing}"
        if len(set(requested_ids)) != len(requested_ids):
            return "错误:阅读计划中存在重复 paper_id。"

        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        normalized: list[dict[str, Any]] = []
        for raw in sorted(raw_items, key=lambda item: int(item.get("order") or 1)):
            paper_id = str(raw["paper_id"])
            pp, paper = by_paper_id[paper_id]
            entry = {
                "paper_id": paper_id,
                "paper_title": paper.title,
                "order": int(raw.get("order") or 1),
                "priority": int(raw.get("priority") or 3),
                "status": "completed" if (pp.analysis_card or {}).get("summary") else "pending",
                "reason": str(raw.get("reason") or "")[:1000],
                "focus": [str(value)[:300] for value in list(raw.get("focus") or [])[:20]],
                "questions": [str(value)[:500] for value in list(raw.get("questions") or [])[:20]],
                "updated_at": now,
            }
            pp.reading_priority = entry["priority"]
            pp.reading_plan = {key: value for key, value in entry.items() if key not in {"paper_id", "paper_title"}}
            normalized.append(entry)
        await db.commit()

        title = (kwargs.get("title") or "项目精读计划").strip()
        objective = str(kwargs.get("objective") or "").strip()
        markdown = [f"# {title}", "", objective, ""]
        for entry in normalized:
            markdown.extend([
                f"## {entry['order']}. {entry['paper_title']}",
                f"- 阅读理由:{entry['reason'] or '未说明'}",
                f"- 阅读重点:{'；'.join(entry['focus']) or '全文概览'}",
                f"- 待回答问题:{'；'.join(entry['questions']) or '提炼核心贡献与局限'}",
                "",
            ])
        return await save_artifact_impl(
            artifact_type="reading_plan",
            title=title,
            markdown_text="\n".join(markdown).strip(),
            content={"objective": objective, "items": normalized},
        )

    async def build_evidence_matrix_impl(**kwargs: Any) -> str:
        """Aggregate persisted cards deterministically; only conflicts/gaps come from the agent."""
        await _assert_owned()
        rows = (await db.execute(
            select(ProjectPaper, Paper)
            .join(Paper, Paper.id == ProjectPaper.paper_id)
            .where(ProjectPaper.project_id == _pid, Paper.user_id == _uid)
            .order_by(ProjectPaper.reading_priority.desc())
        )).all()
        matrix_rows: list[dict[str, Any]] = []
        for pp, paper in rows:
            card = dict(pp.analysis_card or {})
            if not card.get("summary"):
                continue
            matrix_rows.append({
                "paper_id": str(paper.id), "paper_title": paper.title, "role": pp.role,
                "methods": list(card.get("methods") or []),
                "datasets": list(card.get("datasets") or []),
                "metrics": list(card.get("metrics") or []),
                "findings": list(card.get("findings") or []),
                "limitations": list(card.get("limitations") or []),
                "evidence": list(card.get("evidence") or []),
            })
        if not matrix_rows:
            return "错误:项目中还没有已完成的论文卡片，请先执行精读计划。"

        project_paper_ids = {row["paper_id"] for row in matrix_rows}
        conflicts = []
        for raw_conflict in list(kwargs.get("conflicts") or [])[:30]:
            conflict = _as_dict(raw_conflict)
            paper_ids = [str(value) for value in conflict.get("paper_ids", [])]
            if paper_ids and not set(paper_ids).issubset(project_paper_ids):
                return "错误:冲突项引用了不在已完成论文卡片中的 paper_id。"
            conflicts.append(dict(conflict))
        gaps = [_as_dict(item) for item in list(kwargs.get("evidence_gaps") or [])[:30]]
        question = str(kwargs.get("research_question") or "").strip()
        content = {
            "research_question": question,
            "columns": ["methods", "datasets", "metrics", "findings", "limitations"],
            "rows": matrix_rows,
            "conflicts": conflicts,
            "evidence_gaps": gaps,
            "generated_from_cards": len(matrix_rows),
        }
        title = (kwargs.get("title") or "跨论文证据矩阵").strip()
        markdown = [f"# {title}", "", f"研究问题：{question}", "", "| 论文 | 方法 | 数据集 | 指标 | 主要发现 | 局限 |", "|---|---|---|---|---|---|"]
        for row in matrix_rows:
            cells = [row["paper_title"]] + ["；".join(map(str, row[key])) for key in content["columns"]]
            markdown.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
        if conflicts:
            markdown.extend(["", "## 冲突结论", *[f"- {item.get('explanation') or item.get('claim_a', '')}" for item in conflicts]])
        if gaps:
            markdown.extend(["", "## 证据缺口", *[f"- {item.get('dimension')}: {item.get('missing_evidence', '')}" for item in gaps]])
        return await save_artifact_impl(
            artifact_type="evidence_matrix",
            title=title,
            markdown_text="\n".join(markdown),
            content=content,
        )

    async def save_experiment_design_impl(**kwargs: Any) -> str:
        await _assert_owned()
        matrix = (await db.execute(
            select(WritingArtifact)
            .where(WritingArtifact.project_id == _pid, WritingArtifact.artifact_type == "evidence_matrix")
            .order_by(WritingArtifact.updated_at.desc())
            .limit(1)
        )).scalars().first()
        if matrix is None:
            return "错误:尚未生成证据矩阵，请先完成论文精读并构建跨论文证据矩阵。"
        fields = (
            "research_question", "hypothesis", "rationale", "independent_variables",
            "dependent_variables", "controls", "datasets", "baselines", "metrics",
            "experiment_steps", "ablations", "success_criteria", "falsification_criteria",
            "risks", "evidence_refs", "requires_empirical_results",
        )
        content = {
            field: (
                bool(kwargs.get(field, True)) if field == "requires_empirical_results"
                else kwargs.get(field) or ([] if field not in {"research_question", "hypothesis", "rationale"} else "")
            )
            for field in fields
        }
        content["evidence_matrix_id"] = str(matrix.id)
        title = (kwargs.get("title") or "研究假设与实验设计").strip()
        markdown = [
            f"# {title}", "", "## 研究问题", str(content["research_question"]), "",
            "## 可证伪假设", str(content["hypothesis"]), "", "## 依据", str(content["rationale"]), "",
            "## 实验步骤", *[f"{i}. {step}" for i, step in enumerate(content["experiment_steps"], 1)], "",
            "## 成功判据", *[f"- {item}" for item in content["success_criteria"]], "",
            "## 证伪判据", *[f"- {item}" for item in content["falsification_criteria"]],
        ]
        return await save_artifact_impl(
            artifact_type="experiment_design",
            title=title,
            markdown_text="\n".join(markdown),
            content=content,
        )

    async def save_experiment_results_impl(**kwargs: Any) -> str:
        await _assert_owned()
        design = await db.get(WritingArtifact, str(kwargs.get("experiment_design_id") or ""))
        if design is None or design.project_id != _pid or design.artifact_type != "experiment_design":
            return "错误:experiment_design_id 无效或不属于当前项目。"
        sources = [_as_dict(item) for item in list(kwargs.get("sources") or [])]
        source_ids = [str(item.get("source_id") or "") for item in sources]
        if len(set(source_ids)) != len(source_ids):
            return "错误:sources 中 source_id 必须唯一。"
        metrics = [_as_dict(item) for item in list(kwargs.get("metrics") or [])]
        unknown_sources = sorted({str(item.get("source_id") or "") for item in metrics} - set(source_ids))
        if unknown_sources:
            return f"错误:指标引用了不存在的结果来源:{unknown_sources}"
        if not metrics and not list(kwargs.get("qualitative_findings") or []):
            return "错误:至少需要一项真实指标或一条定性发现。"

        content = {
            "experiment_design_id": str(design.id), "experiment_design_version": design.version,
            "run_id": str(kwargs.get("run_id") or "").strip(), "sources": sources, "metrics": metrics,
            "hypothesis_outcome": kwargs.get("hypothesis_outcome"),
            "qualitative_findings": [str(value)[:2000] for value in list(kwargs.get("qualitative_findings") or [])],
            "protocol_deviations": [str(value)[:2000] for value in list(kwargs.get("protocol_deviations") or [])],
            "analysis_notes": [str(value)[:2000] for value in list(kwargs.get("analysis_notes") or [])],
        }
        title = str(kwargs.get("title") or "实验结果登记").strip()
        outcome_labels = {"supported": "支持", "not_supported": "不支持", "mixed": "部分支持", "inconclusive": "证据不足"}
        markdown = [
            f"# {title}", "", f"- 运行标识：{content['run_id']}",
            f"- 假设结论：{outcome_labels.get(str(content['hypothesis_outcome']), content['hypothesis_outcome'])}",
            f"- 绑定实验设计：{design.title} v{design.version}", "", "## 结果来源", "",
            *[f"- [{item['source_id']}] {item['source_type']}：{item['locator']}"
              + (f"（checksum: {item['checksum']}）" if item.get("checksum") else "") for item in sources], "",
        ]
        if metrics:
            markdown.extend(["## 指标", "", "| 方法 | 数据集/划分 | 指标 | 数值 | 不确定性 | 来源 |", "|---|---|---|---:|---|---|"])
            for item in metrics:
                dataset = "/".join(value for value in (str(item.get("dataset") or ""), str(item.get("split") or "")) if value)
                value = f"{item.get('value')} {item.get('unit') or ''}".strip()
                markdown.append(f"| {item.get('method') or item.get('baseline') or '—'} | {dataset or '—'} | {item.get('metric')} | {value} | {item.get('uncertainty') or '—'} | {item.get('source_id')} |")
            markdown.append("")
        if content["qualitative_findings"]:
            markdown.extend(["## 定性发现", "", *[f"- {item}" for item in content["qualitative_findings"]], ""])
        if content["protocol_deviations"]:
            markdown.extend(["## 相对设计的偏差", "", *[f"- {item}" for item in content["protocol_deviations"]], ""])
        return await save_artifact_impl(
            artifact_type="experiment_results", title=title,
            markdown_text="\n".join(markdown).strip(), content=content,
            _integrity_token=_integrity_token,
        )

    async def save_paper_blueprint_impl(**kwargs: Any) -> str:
        await _assert_owned()
        design = (await db.execute(
            select(WritingArtifact)
            .where(WritingArtifact.project_id == _pid, WritingArtifact.artifact_type == "experiment_design")
            .order_by(WritingArtifact.updated_at.desc()).limit(1)
        )).scalars().first()
        sections = [_as_dict(item) for item in list(kwargs.get("sections") or [])]
        section_ids = [str(item.get("section_id")) for item in sections]
        orders = [int(item.get("order") or 0) for item in sections]
        if len(set(section_ids)) != len(section_ids) or len(set(orders)) != len(orders):
            return "错误:sections 中 section_id 和 order 必须唯一。"
        project_paper_ids = set((await db.execute(
            select(ProjectPaper.paper_id).where(ProjectPaper.project_id == _pid)
        )).scalars().all())
        for section in sections:
            for ref in section.get("evidence_refs") or []:
                if ref.get("paper_id") and str(ref["paper_id"]) not in project_paper_ids:
                    return f"错误:章节 {section.get('section_id')} 引用了项目外论文。"
            section["status"] = "planned"
        sections.sort(key=lambda item: int(item["order"]))
        content = {
            "working_title": kwargs["working_title"],
            "central_claim": kwargs["central_claim"],
            "target_audience": kwargs.get("target_audience") or "",
            "target_venue": kwargs.get("target_venue") or "",
            "experiment_design_id": str(design.id) if design else "",
            "started_without_research_design": design is None,
            "sections": sections,
        }
        title = (kwargs.get("title") or "论文写作蓝图").strip()
        markdown = [f"# {content['working_title']}", "", f"中心论点：{content['central_claim']}", ""]
        for section in sections:
            markdown.extend([
                f"## {section['order']}. {section['title']}", section["purpose"],
                f"- 目标字数：{section.get('word_target', 800)}",
                f"- 核心主张：{'；'.join(section.get('key_claims') or []) or '待补充'}",
                f"- 引用需求：{'；'.join(section.get('citation_needs') or []) or '无'}", "",
            ])
        return await save_artifact_impl(
            artifact_type="paper_blueprint", title=title,
            markdown_text="\n".join(markdown), content=content,
        )

    async def save_section_draft_impl(**kwargs: Any) -> str:
        await _assert_owned()
        blueprint = await db.get(WritingArtifact, str(kwargs["blueprint_id"]))
        if blueprint is None or blueprint.project_id != _pid or blueprint.artifact_type != "paper_blueprint":
            return "错误:blueprint_id 无效或不属于当前项目。"
        section_id = str(kwargs["section_id"])
        planned = next((item for item in (blueprint.content or {}).get("sections", []) if str(item.get("section_id")) == section_id), None)
        if planned is None:
            return f"错误:蓝图中不存在 section_id={section_id}。"
        results_artifact = None
        if kwargs.get("contains_empirical_results"):
            results_id = str(kwargs.get("experiment_results_id") or "").strip()
            if not results_id:
                return "错误:包含实验结果时必须提供 experiment_results_id；自由文本 results_source 不能证明数值来源。"
            results_artifact = await db.get(WritingArtifact, results_id)
            if results_artifact is None or results_artifact.project_id != _pid or results_artifact.artifact_type != "experiment_results":
                return "错误:experiment_results_id 无效或不属于当前项目。"
            design_id = str((blueprint.content or {}).get("experiment_design_id") or "")
            if str((results_artifact.content or {}).get("experiment_design_id") or "") != design_id:
                return "错误:实验结果与当前论文蓝图所绑定的实验设计不一致。"
        project_paper_ids = set((await db.execute(
            select(ProjectPaper.paper_id).where(ProjectPaper.project_id == _pid)
        )).scalars().all())
        refs = [_as_dict(item) for item in list(kwargs.get("evidence_refs") or [])]
        if any(ref.get("paper_id") and str(ref["paper_id"]) not in project_paper_ids for ref in refs):
            return "错误:草稿引用了当前项目以外的论文。"
        unresolved = [str(item)[:500] for item in list(kwargs.get("unresolved_items") or [])[:50]]
        existing_rows = (await db.execute(
            select(WritingArtifact).where(
                WritingArtifact.project_id == _pid,
                WritingArtifact.artifact_type == "section_draft",
                WritingArtifact.parent_id == blueprint.id,
            )
        )).scalars().all()
        existing = next((item for item in existing_rows if (item.meta or {}).get("section_id") == section_id), None)
        meta = {
            "generated_by": "agent", "section_id": section_id,
            "evidence_refs": refs, "unresolved_items": unresolved,
            "contains_empirical_results": bool(kwargs.get("contains_empirical_results")),
            "experiment_results_id": str(results_artifact.id) if results_artifact else "",
            "results_source": str(kwargs.get("results_source") or "")[:1000],
        }
        if existing:
            existing.title = kwargs["title"]
            existing.markdown_text = kwargs["markdown_text"]
            existing.meta = meta
            existing.version = (existing.version or 1) + 1
            existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            artifact = existing
        else:
            artifact = WritingArtifact(
                project_id=_pid, author_id=_uid, artifact_type="section_draft",
                title=kwargs["title"], version=1, parent_id=blueprint.id,
                content={"section_id": section_id}, markdown_text=kwargs["markdown_text"],
                html_text="", status=ARTIFACT_STATUS_DRAFT, meta=meta,
            )
            db.add(artifact)
        blueprint_content = dict(blueprint.content or {})
        blueprint_sections = [dict(item) for item in blueprint_content.get("sections", [])]
        for item in blueprint_sections:
            if str(item.get("section_id")) == section_id:
                item["status"] = "drafted" if not unresolved else "needs_revision"
        blueprint_content["sections"] = blueprint_sections
        blueprint.content = blueprint_content
        await db.commit()
        await db.refresh(artifact)
        return f"已保存章节草稿 {artifact.title} (v{artifact.version})，未解决项 {len(unresolved)} 个。"

    async def assemble_full_draft_impl(**kwargs: Any) -> str:
        await _assert_owned()
        blueprint = await db.get(WritingArtifact, str(kwargs["blueprint_id"]))
        if blueprint is None or blueprint.project_id != _pid or blueprint.artifact_type != "paper_blueprint":
            return "错误:blueprint_id 无效或不属于当前项目。"
        drafts = (await db.execute(select(WritingArtifact).where(
            WritingArtifact.project_id == _pid,
            WritingArtifact.artifact_type == "section_draft",
            WritingArtifact.parent_id == blueprint.id,
        ))).scalars().all()
        by_section = {(item.meta or {}).get("section_id"): item for item in drafts}
        sections = sorted((blueprint.content or {}).get("sections", []), key=lambda item: int(item.get("order") or 0))
        missing = [item.get("section_id") for item in sections if item.get("section_id") not in by_section]
        unresolved = [value for draft in drafts for value in ((draft.meta or {}).get("unresolved_items") or [])]
        if missing:
            return f"错误:这些章节还没有草稿:{missing}"
        if unresolved and not kwargs.get("allow_unresolved_placeholders"):
            return f"错误:仍有 {len(unresolved)} 个未解决项，请先修订或明确允许保留占位符。"
        reference_list = (await db.execute(select(WritingArtifact).where(
            WritingArtifact.project_id == _pid,
            WritingArtifact.artifact_type == "reference_list",
            WritingArtifact.parent_id == blueprint.id,
        ).order_by(WritingArtifact.updated_at.desc()).limit(1))).scalars().first()
        if reference_list is None:
            return "错误:请先从章节 evidence_refs 生成参考文献列表，再组装带引用键的全文。"
        key_by_paper = {
            str(item.get("paper_id")): str(item.get("citation_key"))
            for item in (reference_list.content or {}).get("entries") or []
        }
        markdown_sections: list[str] = []
        cited_ids: set[str] = set()
        result_artifact_ids: set[str] = set()
        blueprint_design_id = str((blueprint.content or {}).get("experiment_design_id") or "")
        blueprint_design = await db.get(WritingArtifact, blueprint_design_id) if blueprint_design_id else None
        for item in sections:
            draft = by_section[item["section_id"]]
            draft_meta = draft.meta or {}
            if draft_meta.get("contains_empirical_results"):
                result_id = str(draft_meta.get("experiment_results_id") or "")
                result_artifact = await db.get(WritingArtifact, result_id) if result_id else None
                if (
                    result_artifact is None
                    or result_artifact.project_id != _pid
                    or result_artifact.artifact_type != "experiment_results"
                    or str((result_artifact.content or {}).get("experiment_design_id") or "") != blueprint_design_id
                ):
                    return f"错误:章节 {item['section_id']} 的实证结果没有绑定当前实验设计的可信结果产物。"
                result_artifact_ids.add(str(result_artifact.id))
            section_ids = sorted({str(ref.get("paper_id")) for ref in ((draft.meta or {}).get("evidence_refs") or []) if ref.get("paper_id")})
            cited_ids.update(section_ids)
            missing_keys = [paper_id for paper_id in section_ids if paper_id not in key_by_paper]
            if missing_keys:
                return f"错误:参考文献列表缺少章节引用:{missing_keys}，请重新生成。"
            citation_line = " ".join(f"[@{key_by_paper[paper_id]}]" for paper_id in section_ids)
            markdown_sections.append(draft.markdown_text + (f"\n\n本节引用：{citation_line}" if citation_line else ""))
        if (
            blueprint_design
            and (blueprint_design.content or {}).get("requires_empirical_results", True)
            and not result_artifact_ids
        ):
            return "错误:当前实验设计要求实证结果，但没有任何章节绑定 experiment_results_id。请先完成结果章节。"
        markdown = "\n\n".join(markdown_sections)
        return await save_artifact_impl(
            artifact_type="full_draft", title=kwargs["title"], markdown_text=markdown,
            content={"blueprint_id": str(blueprint.id), "section_ids": [item["section_id"] for item in sections],
                     "unresolved_items": unresolved, "reference_list_id": str(reference_list.id),
                     "reference_list_version": int(reference_list.version or 1), "cited_paper_ids": sorted(cited_ids),
                     "experiment_results_ids": sorted(result_artifact_ids)},
        )

    async def _blueprint_reference_ids(blueprint: WritingArtifact) -> tuple[set[str], int]:
        drafts = (await db.execute(select(WritingArtifact).where(
            WritingArtifact.project_id == _pid,
            WritingArtifact.artifact_type == "section_draft",
            WritingArtifact.parent_id == blueprint.id,
        ))).scalars().all()
        paper_ids: set[str] = set()
        missing_locations = 0
        for draft in drafts:
            for ref in (draft.meta or {}).get("evidence_refs") or []:
                if ref.get("paper_id"):
                    paper_ids.add(str(ref["paper_id"]))
                    if not ref.get("source_id") and not ref.get("page"):
                        missing_locations += 1
        return paper_ids, missing_locations

    async def build_reference_list_impl(**kwargs: Any) -> str:
        await _assert_owned()
        blueprint = await db.get(WritingArtifact, str(kwargs["blueprint_id"]))
        if blueprint is None or blueprint.project_id != _pid or blueprint.artifact_type != "paper_blueprint":
            return "错误:blueprint_id 无效或不属于当前项目。"
        paper_ids, missing_locations = await _blueprint_reference_ids(blueprint)
        if not paper_ids:
            return "错误:章节草稿没有记录任何 paper_id，无法生成可信参考文献表。"
        papers = (await db.execute(select(Paper).where(Paper.id.in_(paper_ids), Paper.user_id == _uid))).scalars().all()
        found_ids = {str(paper.id) for paper in papers}
        if found_ids != paper_ids:
            return f"错误:引用论文缺失或无权限:{sorted(paper_ids - found_ids)}"
        entries, bibtex, markdown = build_bibliography(papers)
        missing_doi = [item["paper_id"] for item in entries if not item["doi"]]
        existing = (await db.execute(select(WritingArtifact).where(
            WritingArtifact.project_id == _pid,
            WritingArtifact.artifact_type == "reference_list",
            WritingArtifact.parent_id == blueprint.id,
        ).order_by(WritingArtifact.updated_at.desc()).limit(1))).scalars().first()
        content = {"blueprint_id": str(blueprint.id), "paper_ids": sorted(paper_ids),
                   "entries": entries, "bibtex": bibtex, "missing_doi": missing_doi,
                   "missing_source_locations": missing_locations}
        if existing:
            existing.title = kwargs.get("title") or "参考文献列表"
            existing.content = content
            existing.markdown_text = markdown
            existing.version = (existing.version or 1) + 1
            existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            artifact = existing
        else:
            artifact = WritingArtifact(project_id=_pid, author_id=_uid, artifact_type="reference_list",
                title=kwargs.get("title") or "参考文献列表", version=1, parent_id=blueprint.id,
                content=content, markdown_text=markdown, html_text="", status=ARTIFACT_STATUS_READY,
                meta={"generated_by": "deterministic_reference_builder"})
            db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        return (f"已从章节实际引用生成 {len(entries)} 条参考文献，产物 ID: {artifact.id}。"
                f"缺 DOI {len(missing_doi)} 条，缺页码/source_id 定位 {missing_locations} 处。")

    async def audit_full_draft_impl(**kwargs: Any) -> str:
        project = await _assert_owned()
        full_draft = await db.get(WritingArtifact, str(kwargs["full_draft_id"]))
        if full_draft is None or full_draft.project_id != _pid or full_draft.artifact_type != "full_draft":
            return "错误:full_draft_id 无效或不属于当前项目。"
        blueprint_id = str((full_draft.content or {}).get("blueprint_id") or "")
        blueprint = await db.get(WritingArtifact, blueprint_id) if blueprint_id else None
        if blueprint is None or blueprint.project_id != _pid or blueprint.artifact_type != "paper_blueprint":
            return "错误:全文缺少有效论文蓝图来源，无法做章节级审计。"
        sections = list((blueprint.content or {}).get("sections") or [])
        section_ids = {str(item.get("section_id")) for item in sections}
        drafts = (await db.execute(select(WritingArtifact).where(
            WritingArtifact.project_id == _pid,
            WritingArtifact.artifact_type == "section_draft",
            WritingArtifact.parent_id == blueprint.id,
        ))).scalars().all()
        by_section = {str((item.meta or {}).get("section_id")): item for item in drafts}
        project_paper_ids = {str(value) for value in (await db.execute(
            select(ProjectPaper.paper_id).where(ProjectPaper.project_id == _pid)
        )).scalars().all()}
        issues: list[dict[str, Any]] = []
        for raw in list(kwargs.get("issues") or [])[:100]:
            issue = _as_dict(raw)
            if issue.get("severity") not in {"blocker", "major", "minor"}:
                return "错误:审计问题 severity 必须是 blocker/major/minor。"
            if issue.get("section_id") and str(issue["section_id"]) not in section_ids:
                return f"错误:审计问题引用了蓝图外章节 {issue['section_id']}。"
            for ref in issue.get("evidence_refs") or []:
                if ref.get("paper_id") and str(ref["paper_id"]) not in project_paper_ids:
                    return "错误:审计问题引用了当前项目以外的论文。"
            issues.append(issue)
        for section in sections:
            section_id = str(section.get("section_id"))
            draft = by_section.get(section_id)
            if draft is None:
                issues.append({"severity": "blocker", "category": "structure", "section_id": section_id,
                    "description": "蓝图章节缺少草稿。", "recommendation": "先完成该章节再重新组装全文。", "evidence_refs": []})
                continue
            meta = draft.meta or {}
            unresolved = list(meta.get("unresolved_items") or [])
            if unresolved:
                issues.append({"severity": "blocker", "category": "evidence", "section_id": section_id,
                    "description": f"章节仍有 {len(unresolved)} 个未解决项。", "recommendation": "逐项补证或明确删除无依据主张。", "evidence_refs": []})
            if meta.get("contains_empirical_results"):
                result_id = str(meta.get("experiment_results_id") or "")
                result_artifact = await db.get(WritingArtifact, result_id) if result_id else None
                expected_design_id = str((blueprint.content or {}).get("experiment_design_id") or "")
                if (
                    result_artifact is None
                    or result_artifact.project_id != _pid
                    or result_artifact.artifact_type != "experiment_results"
                    or str((result_artifact.content or {}).get("experiment_design_id") or "") != expected_design_id
                ):
                    issues.append({"severity": "blocker", "category": "result_integrity", "section_id": section_id,
                        "description": "章节含实证结果但未绑定与当前设计一致的可信结果产物。",
                        "recommendation": "先登记真实实验来源与指标，再用 experiment_results_id 重写该章节。", "evidence_refs": []})
            refs = list(meta.get("evidence_refs") or [])
            if section.get("key_claims") and not refs:
                issues.append({"severity": "major", "category": "citation", "section_id": section_id,
                    "description": "章节包含核心主张但没有记录证据引用。", "recommendation": "为核心主张补充论文与来源位置。", "evidence_refs": []})
            target = int(section.get("word_target") or 0)
            actual = len(re.sub(r"\s+", "", draft.markdown_text or ""))
            if target and actual < target * 0.5:
                issues.append({"severity": "major", "category": "structure", "section_id": section_id,
                    "description": f"章节内容约 {actual} 字，低于目标字数 {target} 的一半。", "recommendation": "补全蓝图要求的论证，不要用重复内容凑字数。", "evidence_refs": []})
        counts = {severity: sum(1 for item in issues if item["severity"] == severity) for severity in ("blocker", "major", "minor")}
        content = {"full_draft_id": str(full_draft.id), "full_draft_version": int(full_draft.version or 1), "blueprint_id": blueprint_id,
                   "issues": issues, "counts": counts, "passed": counts["blocker"] == 0}
        lines = [f"# {kwargs.get('title') or '全文事实与引用审计'}", "",
                 f"结论：{'通过阻断项检查' if content['passed'] else '存在阻断项，不可定稿'}", "",
                 f"- 阻断：{counts['blocker']}", f"- 重要：{counts['major']}", f"- 次要：{counts['minor']}", ""]
        for index, issue in enumerate(issues, 1):
            lines.extend([f"## {index}. [{issue['severity']}] {issue['category']}",
                          issue["description"], f"修订建议：{issue['recommendation']}", ""])
        report = WritingArtifact(project_id=_pid, author_id=_uid, artifact_type="review_report",
            title=kwargs.get("title") or "全文事实与引用审计", version=1, parent_id=full_draft.id,
            content=content, markdown_text="\n".join(lines), html_text="", status=ARTIFACT_STATUS_READY,
            meta={"generated_by": "agent", "audit_kind": "full_draft"})
        db.add(report)
        project.phase = PROJECT_PHASE_REFINEMENT
        await db.commit()
        await db.refresh(report)
        return f"已保存全文审计报告 {report.id}：blocker={counts['blocker']}，major={counts['major']}，minor={counts['minor']}。"

    async def finalize_manuscript_impl(**kwargs: Any) -> str:
        project = await _assert_owned()
        full_draft = await db.get(WritingArtifact, str(kwargs["full_draft_id"]))
        report = await db.get(WritingArtifact, str(kwargs["review_report_id"]))
        if full_draft is None or full_draft.project_id != _pid or full_draft.artifact_type != "full_draft":
            return "错误:full_draft_id 无效。"
        if report is None or report.project_id != _pid or report.artifact_type != "review_report" or report.parent_id != full_draft.id:
            return "错误:review_report_id 不是该全文的有效审计报告。"
        latest_reports = (await db.execute(select(WritingArtifact).where(
            WritingArtifact.project_id == _pid,
            WritingArtifact.artifact_type == "review_report",
            WritingArtifact.parent_id == full_draft.id,
        ).order_by(WritingArtifact.updated_at.desc()))).scalars().all()
        latest_report = next((item for item in latest_reports if (item.meta or {}).get("audit_kind") == "full_draft"), None)
        if latest_report is None or latest_report.id != report.id:
            return "错误:必须使用该全文最新的审计报告定稿。"
        if int((report.content or {}).get("full_draft_version") or 0) != int(full_draft.version or 1):
            return "错误:全文在审计后发生过修改，请重新审计后再定稿。"
        counts = (report.content or {}).get("counts") or {}
        if int(counts.get("blocker") or 0) > 0:
            return f"错误:审计仍有 {counts.get('blocker')} 个阻断项，必须修订并重新审计。"
        if list((full_draft.content or {}).get("unresolved_items") or []):
            return "错误:全文仍含未解决占位符，不能定稿。"
        blueprint_id = str((full_draft.content or {}).get("blueprint_id") or "")
        blueprint = await db.get(WritingArtifact, blueprint_id) if blueprint_id else None
        if blueprint is None:
            return "错误:全文缺少有效论文蓝图。"
        cited_ids, missing_locations = await _blueprint_reference_ids(blueprint)
        reference_list = (await db.execute(select(WritingArtifact).where(
            WritingArtifact.project_id == _pid,
            WritingArtifact.artifact_type == "reference_list",
            WritingArtifact.parent_id == blueprint.id,
        ).order_by(WritingArtifact.updated_at.desc()).limit(1))).scalars().first()
        if reference_list is None:
            return "错误:尚未基于章节实际引用生成参考文献列表。"
        if (reference_list.meta or {}).get("generated_by") != "deterministic_reference_builder":
            return "错误:参考文献列表不是由受信任的确定性工具生成。"
        listed_ids = set((reference_list.content or {}).get("paper_ids") or [])
        if listed_ids != cited_ids:
            return "错误:章节引用与参考文献列表不一致，请重新生成参考文献列表。"
        if str((full_draft.content or {}).get("reference_list_id") or "") != str(reference_list.id) or int((full_draft.content or {}).get("reference_list_version") or 0) != int(reference_list.version or 1):
            return "错误:全文没有使用最新参考文献版本，请重新组装全文。"
        if missing_locations:
            return f"错误:仍有 {missing_locations} 处论文引用缺少 page 或 source_id 定位。"
        manuscript = WritingArtifact(project_id=_pid, author_id=_uid, artifact_type="final_manuscript",
            title=kwargs["title"], version=1, parent_id=full_draft.id,
            content={"full_draft_id": str(full_draft.id), "review_report_id": str(report.id),
                     "audit_counts": counts, "reference_list_id": str(reference_list.id)}, markdown_text=full_draft.markdown_text,
            html_text=full_draft.html_text or "", status=ARTIFACT_STATUS_READY,
            meta={"generated_by": "agent", "finalized_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()})
        db.add(manuscript)
        project.phase = PROJECT_PHASE_REFINEMENT
        await db.commit()
        await db.refresh(manuscript)
        return f"终稿已锁定并保存：{manuscript.id}。可从项目工作台下载 Markdown。"

    return [
        StructuredTool.from_function(
            coroutine=search_content_impl,
            name="project_search_content",
            description=(
                "在【当前研究项目】的全部文档中做跨论文混合检索和统一重排。"
                "用于领域总结、多论文比较、共同趋势、差异、数据集/方法归纳和文献综述取证。"
                "返回的每条证据都包含 paper_id、paper_title、页码、章节和全局 source_id。"
                "项目级问题应优先使用本工具，不要只检索当前默认论文。"
            ),
            args_schema=ProjectSearchContentInput,
        ),
        StructuredTool.from_function(
            coroutine=add_paper_impl,
            name="project_add_paper",
            description=(
                "向【当前研究项目】的文档库加入一篇用户已有的论文。"
                "只能加该用户自己已经上传并解析成功的论文。"
                "加入后用户可以在项目文档库中看到它。"
                "适合场景:1) arXiv 检索后用户已经同步上传到了自己的论文库需要纳入项目管理;"
                "2) 已读论文确认相关性后,加入项目库作为核心/相关/背景文献。"
                "参数 role=core 表示核心文献(必须精读),related 表示相关工作(要在 Related Work 里提),background 表示背景知识。"
            ),
            args_schema=ProjectAddPaperInput,
        ),
        StructuredTool.from_function(
            coroutine=remove_paper_impl,
            name="project_remove_paper",
            description=(
                "从【当前研究项目】的文档库中移除一篇论文(仅移除关联,不删除论文本体)。"
                "适合场景:错误加入了不相关的论文需要清理;或论文已读完归档后移出项目库。"
            ),
            args_schema=ProjectRemovePaperInput,
        ),
        StructuredTool.from_function(
            coroutine=import_arxiv_paper_impl,
            name="project_import_arxiv_paper",
            description="按严格校验的 arXiv ID 下载 PDF，进入现有论文解析 Worker，完成后自动加入当前项目；不接受任意 URL。",
            args_schema=ProjectImportArxivPaperInput,
        ),
        StructuredTool.from_function(
            coroutine=append_memory_impl,
            name="project_append_memory",
            description=(
                "向【当前研究项目】写入一条经过确认的 typed Literature Memory。"
                "仅用于最终确认的搜索意图、重要检索偏好、明确排除方向或项目决策；"
                "必须传 memory_type=literature_intent/literature_preference/literature_exclusion/project_decision。"
                "不要写每轮搜索结果、provider 原始响应、临时 ranking、raw reasoning 或普通聊天。"
            ),
            args_schema=ProjectAppendMemoryInput,
        ),
        StructuredTool.from_function(
            coroutine=save_paper_card_impl,
            name="project_save_paper_card",
            description=(
                "把一篇已读项目论文沉淀成结构化阅读卡片。"
                "卡片包含研究问题、方法、数据集、指标、贡献、主要发现、局限和证据位置。"
                "完成一篇论文的精读后调用；事实必须在 evidence 中保留 source_id/page/section。"
            ),
            args_schema=ProjectSavePaperCardInput,
        ),
        StructuredTool.from_function(
            coroutine=save_research_brief_impl,
            name="project_save_research_brief",
            description=(
                "在检索和选题前保存结构化研究任务书：区分用户已知背景、约束、未知项与待验证假设，"
                "给出中英文关键词、可执行检索式、纳入排除标准和选题评价准则。空项目应先调用它。"
            ),
            args_schema=ProjectSaveResearchBriefInput,
        ),
        StructuredTool.from_function(
            coroutine=save_literature_screening_impl,
            name="project_save_literature_screening",
            description=(
                "把外部学术检索运行和候选论文筛选决策保存为可审计台账。"
                "每篇必须标记 include/exclude/maybe、相关度、覆盖维度和理由；先完成研究任务书，"
                "去重后再从 include 候选导入项目，不能把摘要元数据当作全文证据。"
            ),
            args_schema=ProjectSaveLiteratureScreeningInput,
        ),
        StructuredTool.from_function(
            coroutine=save_research_map_impl,
            name="project_save_research_map",
            description=(
                "把跨论文调研结果保存为结构化领域地图，用于选题决策。"
                "地图包含关键词、研究问题、方法族、数据集、研究空白、候选选题和可追溯证据。"
                "保存前必须先用 project_search_content 做跨论文取证；不确定的信息要明确标为待验证。"
            ),
            args_schema=ProjectSaveResearchMapInput,
        ),
        StructuredTool.from_function(
            coroutine=save_reading_plan_impl,
            name="project_save_reading_plan",
            description=(
                "把当前项目论文编排为可执行的精读队列。"
                "为每篇论文设置顺序、优先级、阅读理由、阅读重点和读后问题，并保存阅读计划产物。"
                "制定计划前应参考领域地图、论文元数据和项目长期记忆。"
            ),
            args_schema=ProjectSaveReadingPlanInput,
        ),
        StructuredTool.from_function(
            coroutine=build_evidence_matrix_impl,
            name="project_build_evidence_matrix",
            description=(
                "从项目中已经完成的结构化论文卡片生成跨论文证据矩阵。"
                "方法、数据集、指标、发现和局限直接取自卡片；可附带有论文 ID 和来源编号支撑的冲突结论与证据缺口。"
            ),
            args_schema=ProjectBuildEvidenceMatrixInput,
        ),
        StructuredTool.from_function(
            coroutine=save_experiment_design_impl,
            name="project_save_experiment_design",
            description=(
                "基于当前项目最新证据矩阵保存可证伪的研究假设与实验设计。"
                "必须明确变量、控制项、数据集、基线、指标、实验步骤、消融、成功判据、证伪判据、风险和证据引用。"
            ),
            args_schema=ProjectSaveExperimentDesignInput,
        ),
        StructuredTool.from_function(
            coroutine=save_experiment_results_impl,
            name="project_save_experiment_results",
            description=(
                "登记用户或系统实际提供的实验结果，绑定实验设计、运行标识、来源定位、指标和假设结论。"
                "本工具不执行实验；不得预测或编造数值。每个指标必须引用 sources 中的 source_id。"
            ),
            args_schema=ProjectSaveExperimentResultsInput,
        ),
        StructuredTool.from_function(
            coroutine=save_paper_blueprint_impl,
            name="project_save_paper_blueprint",
            description="基于已确认实验设计保存论文蓝图，逐节定义论证目的、核心主张、证据引用需求和字数预算。",
            args_schema=ProjectSavePaperBlueprintInput,
        ),
        StructuredTool.from_function(
            coroutine=save_section_draft_impl,
            name="project_save_section_draft",
            description=(
                "按论文蓝图保存或更新单个章节草稿，记录证据引用和未解决占位符。"
                "章节含实证数值时必须设置 contains_empirical_results=true，并绑定与蓝图设计一致的 experiment_results_id。"
            ),
            args_schema=ProjectSaveSectionDraftInput,
        ),
        StructuredTool.from_function(
            coroutine=assemble_full_draft_impl,
            name="project_assemble_full_draft",
            description="按论文蓝图顺序确定性拼装所有章节草稿；默认拒绝缺失章节或仍有未解决项的草稿。",
            args_schema=ProjectAssembleFullDraftInput,
        ),
        StructuredTool.from_function(
            coroutine=build_reference_list_impl,
            name="project_build_reference_list",
            description="从所有章节草稿实际使用的 evidence_refs 确定性生成去重参考文献表和 BibTeX，并报告缺 DOI 或来源定位。",
            args_schema=ProjectBuildReferenceListInput,
        ),
        StructuredTool.from_function(
            coroutine=audit_full_draft_impl,
            name="project_audit_full_draft",
            description="审计完整草稿的章节完整性、未解决项、主张证据覆盖和结构问题，并保存结构化审计报告。",
            args_schema=ProjectAuditFullDraftInput,
        ),
        StructuredTool.from_function(
            coroutine=finalize_manuscript_impl,
            name="project_finalize_manuscript",
            description="仅在对应全文的最新审计没有阻断项且无占位符时锁定终稿，生成可下载的 final_manuscript。",
            args_schema=ProjectFinalizeManuscriptInput,
        ),
        StructuredTool.from_function(
            coroutine=read_memory_impl,
            name="project_read_memory",
            description=(
                "读取【当前研究项目】的完整长期记忆,回顾之前写过的所有调研要点、判断、待办。"
                "适合场景:1) 不确定自己之前做过什么判断的时候;"
                "2) 生成文献综述或大纲前需要回顾所有积累的调研要点时。"
                "调用时不需要参数。"
            ),
            args_schema=ProjectReadMemoryInput,
        ),
        StructuredTool.from_function(
            coroutine=save_artifact_impl,
            name="project_save_artifact",
            description=(
                "把生成的结构化结果保存为【当前研究项目】的'写作产物',用户会在'项目工作区 → 写作产物'中看到它。"
                "完成以下工作时请立刻调用保存,不要让结果只出现在回答里:"
                "  - 写完一份文献综述(artifact_type=literature_review)"
                "  - 给出论文大纲(outline)"
                "  - 整理参考文献列表(reference_list)"
                "  - 写完某一章草稿(section_draft)"
                "  - 写完完整全文(full_draft)"
                "  - 给出审稿报告(review_report)"
                "  - 给出投稿建议(submission_suggestion)"
                "markdown_text 必须是完整可阅读的内容,是用户实际下载和查看的正文。"
            ),
            args_schema=ProjectSaveArtifactInput,
        ),
    ]
