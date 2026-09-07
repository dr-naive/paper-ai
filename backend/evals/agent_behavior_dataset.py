"""Agent Behavior V1 数据集的共享常量、读取和确定性校验。"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import yaml


SCHEMA_VERSION = "agent_behavior_v1"
GOAL_TYPES = {"READ_PAPERS", "WRITE_SECTION", "DISCOVER_AND_IMPORT"}
TASK_TYPES = {
    "DISCOVER",
    "IMPORT_PAPER",
    "READ_PAPER",
    "BUILD_EVIDENCE",
    "WRITE_SECTION",
    "AUDIT_DRAFT",
}
EXECUTOR_TYPES = {"AGENT", "DETERMINISTIC", "WORKFLOW"}
STATUSES = {
    "pending",
    "queued",
    "running",
    "waiting_user",
    "retrying",
    "completed",
    "partial",
    "blocked",
    "failed",
    "cancelled",
    "paused",
}
INTERACTIONS = {"none", "confirmation", "clarification"}
ARTIFACT_TYPES = {
    "paper",
    "paper_card",
    "evidence",
    "writing_context",
    "section_draft",
    "audit",
    "discovery_results",
    "blueprint",
    "document",
    "memory",
}

TOP_LEVEL_KEYS = {
    "schema_version",
    "id",
    "goal_type",
    "input",
    "source_refs",
    "expected",
    "allowed",
    "forbidden",
    "completion",
    "budget",
}
INPUT_KEYS = {
    "project_id",
    "instruction",
    "paper_ids",
    "requested_paper_ids",
    "paper_titles",
    "evidence_ids",
    "document_id",
    "seed_case_ids",
    "project_state",
    "user_confirmation",
    "selected_candidate_ids",
    "selected_text",
}
SOURCE_REF_KEYS = {"paperqa_case_ids", "skill_cases"}
EXPECTED_KEYS = {
    "execution_status",
    "task_graph",
    "reused_assets",
    "output_types",
    "user_interaction",
    "preconditions",
    "policies",
}
TASK_GRAPH_KEYS = {"task_id", "task_type", "executor_type", "skill_id", "depends_on"}
ALLOWED_KEYS = {"task_types", "executors", "skills", "tools", "max_task_count"}
FORBIDDEN_KEYS = {"task_types", "executors", "skills", "tools", "actions"}
COMPLETION_KEYS = {
    "required_status",
    "required_outputs",
    "criteria",
    "on_incomplete",
    "max_repair_count",
}
BUDGET_KEYS = {
    "max_tool_calls",
    "max_model_calls",
    "max_external_searches",
    "max_papers_to_read",
    "max_seconds",
}

ALL_TOOLS = {
    "literature.search_external",
    "paper.get_metadata",
    "paper.get_outline",
    "paper.search_content",
    "project.list_papers",
    "project.search_content",
}
FORBIDDEN_ACTIONS = {
    "auto_expand_goal",
    "create_unrelated_task",
    "fabricate_paper",
    "fabricate_evidence",
    "fabricate_search_result",
    "treat_abstract_as_full_text",
    "read_foreign_project_resource",
    "write_without_user_confirmation",
    "overwrite_existing_document",
    "duplicate_import",
    "duplicate_artifact",
    "skip_paper_processing",
    "run_next_goal",
    "call_disallowed_tool",
    "exceed_budget",
    "present_unverified_citation",
    "ignore_completion_failure",
    "import_without_confirmation",
    "resume_without_user_input",
}
COMPLETION_CRITERIA = {
    "paper_scope_checked",
    "source_ids_present",
    "insufficiency_explicit",
    "processing_ready_before_dispatch",
    "paper_card_persisted",
    "existing_paper_card_reused",
    "no_unrelated_goal_tasks",
    "evidence_refs_scoped",
    "document_scoped",
    "structured_citations",
    "section_is_single_paragraph",
    "reviewer_passed_or_one_repair",
    "citation_verification_passed",
    "completion_gate_passed",
    "no_unsupported_citations",
    "user_confirmation_persisted",
    "selected_results_only",
    "no_import_before_confirmation",
    "waiting_context_persisted",
    "search_results_structured",
    "abstract_boundary_preserved",
    "no_fabricated_results",
    "duplicate_import_prevented",
    "duplicate_artifact_prevented",
    "existing_artifact_reused",
    "idempotent_output",
    "processing_failure_exposed",
    "no_foreign_resource",
    "hard_dependency_blocked",
    "no_external_discovery",
    "retryable_failure_recorded",
    "partial_outputs_preserved",
    "cancel_stops_follow_up",
}
DISALLOWED_EVAL_KEYS = {
    "score",
    "scores",
    "judge",
    "grading",
    "grade",
    "llm",
    "llm_judge",
    "reference_answer",
    "reference_claims",
    "evaluation_prompt",
    "auto_score",
    "model_score",
    "gold_answer",
    "expected_answer",
}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,127}$")

GOAL_TASK_TYPES = {
    "READ_PAPERS": {"READ_PAPER"},
    "WRITE_SECTION": {"BUILD_EVIDENCE", "WRITE_SECTION", "AUDIT_DRAFT"},
    "DISCOVER_AND_IMPORT": {"DISCOVER", "IMPORT_PAPER"},
}


def load_jsonl_objects(path: str | Path) -> list[dict[str, Any]]:
    """读取 JSONL 对象；结构校验由 ``validate_cases`` 负责。"""
    dataset_path = Path(path)
    rows: list[dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{dataset_path}:{line_number} JSON 无效: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{dataset_path}:{line_number} 每行必须是 JSON 对象")
            rows.append(value)
    return rows


def load_paperqa_case_ids(path: str | Path) -> set[str]:
    return {str(row.get("id", "")) for row in load_jsonl_objects(path) if row.get("id")}


def load_skill_cases(skills_root: str | Path) -> dict[str, set[str]]:
    root = Path(skills_root)
    result: dict[str, set[str]] = {}
    for path in sorted(root.glob("*/evals/cases.yaml")):
        skill_id = path.parent.parent.name
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cases = payload.get("cases", [])
        if not isinstance(cases, list):
            raise ValueError(f"{path}: cases 必须是列表")
        result[skill_id] = {
            str(case.get("id", ""))
            for case in cases
            if isinstance(case, dict) and case.get("id")
        }
    return result


def load_skill_definitions(skills_root: str | Path) -> dict[str, dict[str, Any]]:
    root = Path(skills_root)
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*/skill.yaml")):
        skill_id = path.parent.name
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: Skill 定义必须是对象")
        result[skill_id] = payload
    return result


def dataset_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "total": len(rows),
        "by_goal": dict(sorted(Counter(row.get("goal_type") for row in rows).items())),
        "by_status": dict(sorted(Counter(row.get("expected", {}).get("execution_status") for row in rows).items())),
        "source_paperqa_cases": len({
            case_id
            for row in rows
            for case_id in row.get("source_refs", {}).get("paperqa_case_ids", [])
        }),
        "source_skill_cases": len({
            case_ref
            for row in rows
            for case_ref in row.get("source_refs", {}).get("skill_cases", [])
        }),
    }


def validate_cases(
    rows: Iterable[dict[str, Any]],
    *,
    paperqa_case_ids: set[str] | None = None,
    skill_cases: dict[str, set[str]] | None = None,
    skill_definitions: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    rows = list(rows)
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, 1):
        case_id = str(row.get("id", ""))
        label = case_id or f"第 {index} 条"
        if case_id in seen_ids:
            errors.append(f"{label}: id 重复")
        seen_ids.add(case_id)
        errors.extend(f"{label}: {error}" for error in _validate_case(
            row,
            paperqa_case_ids=paperqa_case_ids,
            skill_cases=skill_cases,
            skill_definitions=skill_definitions,
        ))
    return errors


def _validate_case(
    row: dict[str, Any],
    *,
    paperqa_case_ids: set[str] | None,
    skill_cases: dict[str, set[str]] | None,
    skill_definitions: dict[str, dict[str, Any]] | None,
) -> list[str]:
    errors: list[str] = []
    errors.extend(_find_disallowed_keys(row))
    _require_exact_keys(row, TOP_LEVEL_KEYS, "顶层", errors)

    case_id = row.get("id")
    if row.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version 必须是 {SCHEMA_VERSION}")
    if not isinstance(case_id, str) or not ID_PATTERN.fullmatch(case_id):
        errors.append("id 必须是 3～128 个字符的稳定 snake_case 标识")

    goal_type = row.get("goal_type")
    if goal_type not in GOAL_TYPES:
        errors.append(f"goal_type 必须是 {sorted(GOAL_TYPES)} 之一")

    _validate_input(row.get("input"), errors)
    _validate_sources(row.get("source_refs"), paperqa_case_ids, skill_cases, errors)

    graph, graph_skills = _validate_expected(row.get("expected"), goal_type, errors)
    allowed = _validate_allowed(row.get("allowed"), graph, graph_skills, errors)
    forbidden = _validate_forbidden(row.get("forbidden"), errors)
    _check_disjoint_constraints(allowed, forbidden, errors)
    if skill_definitions is not None:
        known_skills = set(skill_definitions)
        for field, constraints in (("allowed", allowed), ("forbidden", forbidden)):
            unknown = set(constraints.get("skills", [])) - known_skills
            if unknown:
                errors.append(f"{field}.skills 包含未定义 Skill: {sorted(unknown)}")
    _validate_completion(row.get("completion"), row.get("expected"), errors)
    budget = _validate_budget(row.get("budget"), bool(graph), errors)
    _validate_skill_contracts(graph, allowed, budget, skill_definitions, errors)
    return errors


def _require_exact_keys(value: Any, expected: set[str], label: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是对象")
        return
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        errors.append(f"{label} 缺少字段: {sorted(missing)}")
    if unknown:
        errors.append(f"{label} 存在未知字段: {sorted(unknown)}")


def _validate_input(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("input 必须是对象")
        return
    actual = set(value)
    unknown = actual - INPUT_KEYS
    if unknown:
        errors.append(f"input 存在未知字段: {sorted(unknown)}")
    for field in ("project_id", "instruction"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            errors.append(f"input.{field} 必须是非空字符串")
    for field in ("paper_ids", "requested_paper_ids", "evidence_ids", "seed_case_ids", "selected_candidate_ids"):
        if field in value and not _string_list(value[field]):
            errors.append(f"input.{field} 必须是字符串列表")
    if "paper_titles" in value and not _string_list(value["paper_titles"]):
        errors.append("input.paper_titles 必须是字符串列表")
    if "document_id" in value and value["document_id"] is not None and not isinstance(value["document_id"], str):
        errors.append("input.document_id 必须是字符串或 null")
    if "user_confirmation" in value and value["user_confirmation"] not in {
        "not_required",
        "required",
        "provided",
        "declined",
    }:
        errors.append("input.user_confirmation 值不受支持")
    if "selected_text" in value and not isinstance(value["selected_text"], str):
        errors.append("input.selected_text 必须是字符串")
    state = value.get("project_state")
    if not isinstance(state, dict):
        errors.append("input.project_state 必须是对象")
    else:
        if not isinstance(state.get("papers"), list):
            errors.append("input.project_state.papers 必须是列表")
        else:
            for paper_index, paper in enumerate(state["papers"], 1):
                if not isinstance(paper, dict):
                    errors.append(f"input.project_state.papers[{paper_index}] 必须是对象")
                    continue
                required = {"paper_id", "indexed", "processing", "card_ready"}
                if not required.issubset(paper):
                    errors.append(f"input.project_state.papers[{paper_index}] 缺少 {sorted(required - set(paper))}")
                if not isinstance(paper.get("paper_id"), str):
                    errors.append(f"input.project_state.papers[{paper_index}].paper_id 必须是字符串")
                for field in ("indexed", "card_ready"):
                    if not isinstance(paper.get(field), bool):
                        errors.append(f"input.project_state.papers[{paper_index}].{field} 必须是布尔值")
                if not isinstance(paper.get("processing"), str):
                    errors.append(f"input.project_state.papers[{paper_index}].processing 必须是字符串")
        for field in ("evidence_ids", "confirmation"):
            if field in state and field == "evidence_ids" and not _string_list(state[field]):
                errors.append("input.project_state.evidence_ids 必须是字符串列表")
            if field == "confirmation" and field in state and not isinstance(state[field], str):
                errors.append("input.project_state.confirmation 必须是字符串")
        for field in ("has_document", "has_blueprint", "has_audit"):
            if field in state and not isinstance(state[field], bool):
                errors.append(f"input.project_state.{field} 必须是布尔值")


def _validate_sources(
    value: Any,
    paperqa_case_ids: set[str] | None,
    skill_cases: dict[str, set[str]] | None,
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append("source_refs 必须是对象")
        return
    _require_exact_keys(value, SOURCE_REF_KEYS, "source_refs", errors)
    paperqa = value.get("paperqa_case_ids")
    skills = value.get("skill_cases")
    if not _string_list(paperqa) or not paperqa:
        errors.append("source_refs.paperqa_case_ids 必须至少引用一条现有 PaperQA Case")
    if not _string_list(skills) or not skills:
        errors.append("source_refs.skill_cases 必须至少引用一条现有 Skill Case")
    if paperqa_case_ids is not None:
        for case_id in paperqa or []:
            if case_id not in paperqa_case_ids:
                errors.append(f"source_refs 引用了不存在的 PaperQA Case: {case_id}")
    if skill_cases is not None:
        for reference in skills or []:
            if ":" not in reference:
                errors.append(f"Skill Case 引用必须使用 skill_id:case_id: {reference}")
                continue
            skill_id, case_id = reference.split(":", 1)
            if skill_id not in skill_cases:
                errors.append(f"source_refs 引用了不存在的 Skill: {skill_id}")
            elif case_id not in skill_cases[skill_id]:
                errors.append(f"source_refs 引用了不存在的 Skill Case: {reference}")


def _validate_expected(value: Any, goal_type: Any, errors: list[str]) -> tuple[list[dict[str, Any]], set[str]]:
    if not isinstance(value, dict):
        errors.append("expected 必须是对象")
        return [], set()
    _require_exact_keys(value, EXPECTED_KEYS, "expected", errors)
    status = value.get("execution_status")
    if status not in STATUSES:
        errors.append(f"expected.execution_status 必须是 {sorted(STATUSES)} 之一")
    interaction = value.get("user_interaction")
    if interaction not in INTERACTIONS:
        errors.append(f"expected.user_interaction 必须是 {sorted(INTERACTIONS)} 之一")
    for field in ("reused_assets", "output_types", "preconditions", "policies"):
        if not _string_list(value.get(field)):
            errors.append(f"expected.{field} 必须是字符串列表")
    for field in ("reused_assets", "output_types"):
        for artifact_type in value.get(field, []) if isinstance(value.get(field), list) else []:
            if artifact_type not in ARTIFACT_TYPES:
                errors.append(f"expected.{field} 包含未知产物类型: {artifact_type}")

    graph = value.get("task_graph")
    if not isinstance(graph, list):
        errors.append("expected.task_graph 必须是列表")
        return [], set()
    task_ids: set[str] = set()
    graph_skills: set[str] = set()
    graph_task_types: list[str] = []
    for index, task in enumerate(graph, 1):
        if not isinstance(task, dict):
            errors.append(f"expected.task_graph[{index}] 必须是对象")
            continue
        _require_exact_keys(task, TASK_GRAPH_KEYS, f"expected.task_graph[{index}]", errors)
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not ID_PATTERN.fullmatch(task_id):
            errors.append(f"expected.task_graph[{index}].task_id 无效")
        elif task_id in task_ids:
            errors.append(f"expected.task_graph.task_id 重复: {task_id}")
        else:
            task_ids.add(task_id)
        task_type = task.get("task_type")
        if task_type not in TASK_TYPES:
            errors.append(f"expected.task_graph[{index}].task_type 无效: {task_type}")
        else:
            graph_task_types.append(task_type)
        executor = task.get("executor_type")
        if executor not in EXECUTOR_TYPES:
            errors.append(f"expected.task_graph[{index}].executor_type 无效: {executor}")
        if executor == "AGENT" and not isinstance(task.get("skill_id"), str):
            errors.append(f"expected.task_graph[{index}] 的 AGENT 必须指定 skill_id")
        if task.get("skill_id") is not None:
            if not isinstance(task["skill_id"], str) or not task["skill_id"].strip():
                errors.append(f"expected.task_graph[{index}].skill_id 必须是字符串或 null")
            else:
                graph_skills.add(task["skill_id"])
        if not _string_list(task.get("depends_on")):
            errors.append(f"expected.task_graph[{index}].depends_on 必须是字符串列表")

    if goal_type in GOAL_TASK_TYPES:
        disallowed = set(graph_task_types) - GOAL_TASK_TYPES[goal_type]
        if disallowed:
            errors.append(f"{goal_type} 的 task_graph 包含不属于该 Goal 的 Task: {sorted(disallowed)}")
    if not _is_acyclic(graph):
        errors.append("expected.task_graph 存在循环依赖或未知依赖")
    if status == "blocked" and graph:
        errors.append("blocked Case 不应继续调度 task_graph")
    if status == "waiting_user" and interaction == "none":
        errors.append("waiting_user Case 必须声明 confirmation 或 clarification")
    if status != "waiting_user" and interaction == "none":
        pass
    if status == "completed" and not graph and not value.get("reused_assets"):
        errors.append("completed Case 必须有 task_graph 或复用的 project asset")
    if goal_type == "WRITE_SECTION" and graph:
        _validate_write_graph(graph, errors)
    if goal_type == "DISCOVER_AND_IMPORT" and graph:
        _validate_discover_graph(graph, errors)
    return graph, graph_skills


def _validate_write_graph(graph: list[dict[str, Any]], errors: list[str]) -> None:
    by_type = {task.get("task_type"): task for task in graph}
    write = by_type.get("WRITE_SECTION")
    audit = by_type.get("AUDIT_DRAFT")
    if write is None or audit is None:
        errors.append("WRITE_SECTION 的活动 task_graph 必须包含 WRITE_SECTION 和 AUDIT_DRAFT")
        return
    if write.get("task_id") not in audit.get("depends_on", []):
        errors.append("AUDIT_DRAFT 必须依赖 WRITE_SECTION")
    build = by_type.get("BUILD_EVIDENCE")
    if build and build.get("task_id") not in write.get("depends_on", []):
        errors.append("存在 BUILD_EVIDENCE 时 WRITE_SECTION 必须依赖它")


def _validate_discover_graph(graph: list[dict[str, Any]], errors: list[str]) -> None:
    discover = next((task for task in graph if task.get("task_type") == "DISCOVER"), None)
    imports = [task for task in graph if task.get("task_type") == "IMPORT_PAPER"]
    if imports and discover is None:
        errors.append("IMPORT_PAPER 必须有 DISCOVER 前置 Task")
    if discover:
        for task in imports:
            if discover.get("task_id") not in task.get("depends_on", []):
                errors.append("IMPORT_PAPER 必须依赖 DISCOVER")


def _validate_allowed(
    value: Any,
    graph: list[dict[str, Any]],
    graph_skills: set[str],
    errors: list[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append("allowed 必须是对象")
        return {}
    _require_exact_keys(value, ALLOWED_KEYS, "allowed", errors)
    for field in ("task_types", "executors", "skills", "tools"):
        if not _string_list(value.get(field)):
            errors.append(f"allowed.{field} 必须是字符串列表")
    if isinstance(value.get("task_types"), list):
        unknown = set(value["task_types"]) - TASK_TYPES
        if unknown:
            errors.append(f"allowed.task_types 包含未知值: {sorted(unknown)}")
    if isinstance(value.get("executors"), list):
        unknown = set(value["executors"]) - EXECUTOR_TYPES
        if unknown:
            errors.append(f"allowed.executors 包含未知值: {sorted(unknown)}")
    if isinstance(value.get("tools"), list):
        unknown = set(value["tools"]) - ALL_TOOLS
        if unknown:
            errors.append(f"allowed.tools 包含未登记工具: {sorted(unknown)}")
    max_task_count = value.get("max_task_count")
    if not _nonnegative_int(max_task_count):
        errors.append("allowed.max_task_count 必须是非负整数")
    graph_types = {task.get("task_type") for task in graph}
    graph_executors = {task.get("executor_type") for task in graph}
    if isinstance(value.get("task_types"), list) and not graph_types.issubset(value["task_types"]):
        errors.append("allowed.task_types 必须覆盖 task_graph")
    if isinstance(value.get("executors"), list) and not graph_executors.issubset(value["executors"]):
        errors.append("allowed.executors 必须覆盖 task_graph")
    if isinstance(value.get("skills"), list) and not graph_skills.issubset(value["skills"]):
        errors.append("allowed.skills 必须覆盖 task_graph 使用的 Skill")
    if _nonnegative_int(max_task_count) and max_task_count < len(graph):
        errors.append("allowed.max_task_count 不能小于 task_graph 数量")
    return value


def _validate_forbidden(value: Any, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append("forbidden 必须是对象")
        return {}
    _require_exact_keys(value, FORBIDDEN_KEYS, "forbidden", errors)
    for field in ("task_types", "executors", "skills", "tools", "actions"):
        if not _string_list(value.get(field)):
            errors.append(f"forbidden.{field} 必须是字符串列表")
    if isinstance(value.get("task_types"), list):
        unknown = set(value["task_types"]) - TASK_TYPES
        if unknown:
            errors.append(f"forbidden.task_types 包含未知值: {sorted(unknown)}")
    if isinstance(value.get("executors"), list):
        unknown = set(value["executors"]) - EXECUTOR_TYPES
        if unknown:
            errors.append(f"forbidden.executors 包含未知值: {sorted(unknown)}")
    if isinstance(value.get("tools"), list):
        unknown = set(value["tools"]) - ALL_TOOLS
        if unknown:
            errors.append(f"forbidden.tools 包含未登记工具: {sorted(unknown)}")
    if isinstance(value.get("actions"), list):
        unknown = set(value["actions"]) - FORBIDDEN_ACTIONS
        if unknown:
            errors.append(f"forbidden.actions 包含未知约束: {sorted(unknown)}")
    return value


def _check_disjoint_constraints(allowed: dict[str, Any], forbidden: dict[str, Any], errors: list[str]) -> None:
    for field in ("task_types", "executors", "skills", "tools"):
        overlap = set(allowed.get(field, [])) & set(forbidden.get(field, []))
        if overlap:
            errors.append(f"allowed.{field} 与 forbidden.{field} 不能重叠: {sorted(overlap)}")


def _validate_completion(value: Any, expected: Any, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append("completion 必须是对象")
        return {}
    _require_exact_keys(value, COMPLETION_KEYS, "completion", errors)
    required_status = value.get("required_status")
    if required_status not in STATUSES:
        errors.append("completion.required_status 不是合法状态")
    if isinstance(expected, dict) and required_status != expected.get("execution_status"):
        errors.append("completion.required_status 必须与 expected.execution_status 一致")
    if not _string_list(value.get("required_outputs")):
        errors.append("completion.required_outputs 必须是字符串列表")
    else:
        unknown = set(value["required_outputs"]) - ARTIFACT_TYPES
        if unknown:
            errors.append(f"completion.required_outputs 包含未知产物类型: {sorted(unknown)}")
        if isinstance(expected, dict) and not set(value["required_outputs"]).issubset(set(expected.get("output_types", []))):
            errors.append("completion.required_outputs 必须是 expected.output_types 的子集")
    criteria = value.get("criteria")
    if not _string_list(criteria) or not criteria:
        errors.append("completion.criteria 必须至少包含一条约束")
    else:
        unknown = set(criteria) - COMPLETION_CRITERIA
        if unknown:
            errors.append(f"completion.criteria 包含未登记项: {sorted(unknown)}")
    if value.get("on_incomplete") not in {"waiting_user", "retrying", "partial", "blocked", "failed", "cancelled"}:
        errors.append("completion.on_incomplete 不是合法后续状态")
    if not _nonnegative_int(value.get("max_repair_count")):
        errors.append("completion.max_repair_count 必须是非负整数")
    return value


def _validate_budget(value: Any, has_tasks: bool, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append("budget 必须是对象")
        return {}
    _require_exact_keys(value, BUDGET_KEYS, "budget", errors)
    for field in BUDGET_KEYS:
        if not _nonnegative_int(value.get(field)):
            errors.append(f"budget.{field} 必须是非负整数")
    if has_tasks and isinstance(value.get("max_seconds"), int) and value["max_seconds"] <= 0:
        errors.append("有 task_graph 时 budget.max_seconds 必须大于 0")
    return value


def _validate_skill_contracts(
    graph: list[dict[str, Any]],
    allowed: dict[str, Any],
    budget: dict[str, Any],
    skill_definitions: dict[str, dict[str, Any]] | None,
    errors: list[str],
) -> None:
    if skill_definitions is None:
        return
    for index, task in enumerate(graph, 1):
        skill_id = task.get("skill_id")
        if not skill_id:
            continue
        skill = skill_definitions.get(skill_id)
        if skill is None:
            errors.append(f"task_graph[{index}] 使用不存在的 Skill: {skill_id}")
            continue
        supported = set(skill.get("supported_task_types", []))
        if task.get("task_type") not in supported:
            errors.append(f"Skill {skill_id} 不支持 Task 类型 {task.get('task_type')}")
        skill_tools = set(skill.get("allowed_tools", []))
        if not set(allowed.get("tools", [])).issubset(skill_tools):
            errors.append(f"allowed.tools 超出 Skill {skill_id} 的 allowed_tools")
        skill_budget = skill.get("budget", {})
        limits = {
            "max_tool_calls": skill_budget.get("max_tool_calls"),
            "max_external_searches": skill_budget.get("max_external_searches"),
            "max_papers_to_read": skill_budget.get("max_papers_to_read"),
            "max_seconds": skill_budget.get("max_seconds"),
            "max_model_calls": skill.get("max_model_calls"),
        }
        for field, limit in limits.items():
            if isinstance(limit, int) and isinstance(budget.get(field), int) and budget[field] > limit:
                errors.append(f"budget.{field} 超出 Skill {skill_id} 的上限 {limit}")


def _find_disallowed_keys(value: Any, path: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in DISALLOWED_EVAL_KEYS:
                errors.append(f"{path + '.' if path else ''}{key} 属于禁止的 LLM/答案评分字段")
            errors.extend(_find_disallowed_keys(child, f"{path + '.' if path else ''}{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_find_disallowed_keys(child, f"{path}[{index}]"))
    return errors


def _is_acyclic(graph: list[dict[str, Any]]) -> bool:
    ids = {task.get("task_id") for task in graph}
    if len(ids) != len(graph):
        return False
    dependencies = {task.get("task_id"): set(task.get("depends_on", [])) for task in graph}
    if any(dep not in ids for deps in dependencies.values() for dep in deps):
        return False
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> bool:
        if task_id in visiting:
            return False
        if task_id in visited:
            return True
        visiting.add(task_id)
        if any(not visit(dep) for dep in dependencies[task_id]):
            return False
        visiting.remove(task_id)
        visited.add(task_id)
        return True

    return all(visit(task_id) for task_id in ids)


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and bool(item.strip()) for item in value)


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
