"""Deterministic routing policy for the lead agent.

Keep routing separate from the executor: the executor owns the ReAct loop, while
this module decides whether a question needs that loop and records why.  The
decision is deliberately cheap and deterministic so it can run before any LLM
call and be covered by unit tests.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ExecutionMode(str, Enum):
    FAST = "fast"
    REACT = "react"


class ProjectAction(str, Enum):
    NONE = "none"
    RESEARCH = "research"
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    SAVE_ARTIFACT = "save_artifact"
    MANAGE_LIBRARY = "manage_library"
    MAP_DOMAIN = "map_domain"
    PLAN_READING = "plan_reading"
    BUILD_EVIDENCE_MATRIX = "build_evidence_matrix"
    DESIGN_EXPERIMENT = "design_experiment"
    PLAN_WRITING = "plan_writing"
    DRAFT_SECTION = "draft_section"
    AUDIT_DRAFT = "audit_draft"
    FINALIZE_MANUSCRIPT = "finalize_manuscript"


@dataclass(frozen=True)
class RouteDecision:
    mode: ExecutionMode
    reason: str
    project_action: ProjectAction = ProjectAction.NONE


_CRITIQUE = re.compile(r"审稿|评审|批判|创新性评估|找不足|review|critique", re.IGNORECASE)
_READ_MEMORY = re.compile(
    r"回顾.*(?:进展|要点|记录)|之前.*(?:调研|记录|记忆)|记了.*什么|读取.*记忆|项目.*记忆",
    re.IGNORECASE,
)
_WRITE_MEMORY = re.compile(
    r"(?:写入|记录|记下|记到|记入|保存).{0,8}(?:记忆|要点|偏好|结论|待办)", re.IGNORECASE
)
_SAVE_ARTIFACT = re.compile(
    r"综述|大纲|章节草稿|参考文献列表|审稿报告|投稿建议|写作产物|保存到项目|项目工作区",
    re.IGNORECASE,
)
_MAP_DOMAIN = re.compile(
    r"选题|研究方向|领域地图|关键词树|研究问题|研究空白|研究缺口|候选题目|topic selection|research gap",
    re.IGNORECASE,
)
_PLAN_READING = re.compile(
    r"阅读计划|精读计划|阅读队列|先读哪|阅读顺序|安排.{0,6}阅读|怎么读这些论文",
    re.IGNORECASE,
)
_EVIDENCE_MATRIX = re.compile(
    r"证据矩阵|对比矩阵|方法.{0,4}数据集.{0,4}指标|冲突结论|证据缺口|跨论文对照",
    re.IGNORECASE,
)
_EXPERIMENT_DESIGN = re.compile(
    r"研究假设|实验设计|可证伪|变量定义|对照实验|消融实验|成功判据|失败判据|baseline|ablation",
    re.IGNORECASE,
)
_PLAN_WRITING = re.compile(r"论文蓝图|写作蓝图|写作计划|章节证据|论证结构", re.IGNORECASE)
_DRAFT_SECTION = re.compile(r"章节草稿|撰写.{0,8}(?:引言|方法|实验|结论|相关工作)|完整草稿|全文草稿", re.IGNORECASE)
_AUDIT_DRAFT = re.compile(r"全文审计|引用审计|事实核查|主张.{0,4}证据|检查.{0,6}(?:引用|全文|草稿)|审校", re.IGNORECASE)
_FINALIZE_MANUSCRIPT = re.compile(r"定稿|锁定终稿|生成终稿|最终稿|finalize", re.IGNORECASE)
_MANAGE_LIBRARY = re.compile(
    r"(?:加入|添加|纳入|移除|删除).{0,12}(?:项目文档库|项目库|论文)", re.IGNORECASE
)
_RESEARCH = re.compile(
    r"调研|文献研究|research|这些论文|多篇论文|跨论文|项目.{0,6}(?:论文|文献)|"
    r"领域.{0,6}(?:趋势|进展|方法|数据集)|共同.{0,6}(?:方法|结论|问题|数据集)",
    re.IGNORECASE,
)


def detect_project_action(question: str) -> ProjectAction:
    """Identify project-scoped work without asking an LLM.

    Mutating actions are checked before broad research terms.  This makes the
    result suitable for a future confirmation/permission policy as well as for
    routing today.
    """
    for pattern, action in (
        (_WRITE_MEMORY, ProjectAction.WRITE_MEMORY),
        (_MANAGE_LIBRARY, ProjectAction.MANAGE_LIBRARY),
        (_FINALIZE_MANUSCRIPT, ProjectAction.FINALIZE_MANUSCRIPT),
        (_AUDIT_DRAFT, ProjectAction.AUDIT_DRAFT),
        (_DRAFT_SECTION, ProjectAction.DRAFT_SECTION),
        (_PLAN_WRITING, ProjectAction.PLAN_WRITING),
        (_EXPERIMENT_DESIGN, ProjectAction.DESIGN_EXPERIMENT),
        (_EVIDENCE_MATRIX, ProjectAction.BUILD_EVIDENCE_MATRIX),
        (_PLAN_READING, ProjectAction.PLAN_READING),
        (_MAP_DOMAIN, ProjectAction.MAP_DOMAIN),
        (_SAVE_ARTIFACT, ProjectAction.SAVE_ARTIFACT),
        (_READ_MEMORY, ProjectAction.READ_MEMORY),
        (_RESEARCH, ProjectAction.RESEARCH),
    ):
        if pattern.search(question):
            return action
    return ProjectAction.NONE


def decide_agent_route(
    question: str,
    *,
    project_id: str = "",
    intent_type: str = "factual",
    complexity: str = "medium",
) -> RouteDecision:
    """Choose the cheap answer path or the full tool-calling loop."""
    if _CRITIQUE.search(question):
        return RouteDecision(ExecutionMode.REACT, "critique_requires_subagent")

    action = detect_project_action(question) if project_id else ProjectAction.NONE
    if action is not ProjectAction.NONE:
        return RouteDecision(ExecutionMode.REACT, f"project_action:{action.value}", action)

    if project_id and intent_type == "analytical":
        return RouteDecision(ExecutionMode.REACT, "project_analysis")

    if intent_type == "analytical" and complexity == "high":
        return RouteDecision(ExecutionMode.REACT, "deep_analysis")

    return RouteDecision(ExecutionMode.FAST, "single_retrieval_sufficient")
