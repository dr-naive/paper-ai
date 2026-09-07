from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from evals.agent_behavior_dataset import (
    dataset_summary,
    load_jsonl_objects,
    load_paperqa_case_ids,
    load_skill_cases,
    load_skill_definitions,
    validate_cases,
)
from evals.generate_agent_behavior_dataset import build_cases


ROOT = Path(__file__).resolve().parents[1]
PAPERQA_PATH = ROOT / "evals" / "datasets" / "paperqa_v1.jsonl"
SKILLS_ROOT = ROOT / "app" / "harness" / "skills"
DATASET_PATH = ROOT / "evals" / "datasets" / "agent_behavior_v1.jsonl"


def _load_behavior_cases() -> list[dict]:
    return load_jsonl_objects(DATASET_PATH)


def _source_validation_args() -> dict:
    return {
        "paperqa_case_ids": load_paperqa_case_ids(PAPERQA_PATH),
        "skill_cases": load_skill_cases(SKILLS_ROOT),
        "skill_definitions": load_skill_definitions(SKILLS_ROOT),
    }


def test_agent_behavior_v1_has_36_cases_balanced_across_three_goals():
    cases = _load_behavior_cases()
    summary = dataset_summary(cases)

    assert len(cases) == 36
    assert summary["by_goal"] == {
        "DISCOVER_AND_IMPORT": 12,
        "READ_PAPERS": 12,
        "WRITE_SECTION": 12,
    }
    assert not validate_cases(cases, **_source_validation_args())


def test_generator_is_deterministic_and_reuses_existing_sources():
    paperqa_rows = load_jsonl_objects(PAPERQA_PATH)
    first = build_cases(paperqa_rows)
    second = build_cases(paperqa_rows)

    assert first == second
    assert {case["id"] for case in first} == {case["id"] for case in _load_behavior_cases()}
    source_paperqa_ids = {
        case_id
        for case in first
        for case_id in case["source_refs"]["paperqa_case_ids"]
    }
    assert len(source_paperqa_ids) >= 27
    assert source_paperqa_ids.issubset(load_paperqa_case_ids(PAPERQA_PATH))


def test_all_existing_skill_cases_are_referenced_without_llm_scoring():
    cases = _load_behavior_cases()
    referenced = {
        reference
        for case in cases
        for reference in case["source_refs"]["skill_cases"]
    }
    expected = {
        f"{skill_id}:{case_id}"
        for skill_id, case_ids in load_skill_cases(SKILLS_ROOT).items()
        for case_id in case_ids
    }

    assert expected.issubset(referenced)
    assert all("reference_answer" not in case for case in cases)
    assert all("reference_claims" not in case for case in cases)
    assert all("score" not in case for case in cases)
    assert all("judge" not in case for case in cases)


def test_write_section_covers_reuse_build_and_blocked_paths():
    cases = {case["id"]: case for case in _load_behavior_cases()}

    reuse = cases["write_existing_evidence_p03_q002"]
    assert [task["task_type"] for task in reuse["expected"]["task_graph"]] == ["WRITE_SECTION", "AUDIT_DRAFT"]
    assert "evidence" in reuse["expected"]["reused_assets"]

    build = cases["write_indexed_only_p03_q004"]
    assert [task["task_type"] for task in build["expected"]["task_graph"]] == [
        "BUILD_EVIDENCE",
        "WRITE_SECTION",
        "AUDIT_DRAFT",
    ]
    assert build["expected"]["task_graph"][1]["depends_on"] == ["build_evidence"]

    blocked = cases["write_no_papers_blocked_p04_q001"]
    assert blocked["expected"]["execution_status"] == "blocked"
    assert blocked["expected"]["task_graph"] == []
    assert "DISCOVER" in blocked["forbidden"]["task_types"]
    assert "auto_expand_goal" in blocked["forbidden"]["actions"]


def test_discover_waiting_confirmation_and_import_order_are_explicit():
    cases = {case["id"]: case for case in _load_behavior_cases()}
    waiting = cases["discover_clear_query_confirmation_p05_q005"]
    graph = waiting["expected"]["task_graph"]

    assert waiting["expected"]["execution_status"] == "waiting_user"
    assert waiting["expected"]["user_interaction"] == "confirmation"
    assert [task["task_type"] for task in graph] == ["DISCOVER", "IMPORT_PAPER"]
    assert graph[1]["depends_on"] == ["discover"]
    assert "no_import_before_confirmation" in waiting["completion"]["criteria"]


def test_read_reuse_processing_and_cancel_constraints_are_present():
    cases = {case["id"]: case for case in _load_behavior_cases()}

    reuse = cases["read_existing_card_reuse_p02_q003"]
    assert reuse["expected"]["task_graph"] == []
    assert reuse["expected"]["reused_assets"] == ["paper", "paper_card"]
    assert reuse["budget"] == {key: 0 for key in reuse["budget"]}

    processing = cases["read_processing_pending_p03_q001"]
    assert processing["expected"]["execution_status"] == "queued"
    assert processing["expected"]["preconditions"] == ["paper_processing_ready_before_dispatch"]
    assert processing["expected"]["policies"] == ["complete_existing_processing_before_read"]
    assert "processing_ready_before_dispatch" in processing["completion"]["criteria"]

    cancelled = cases["read_cancel_preserves_partial_p05_q006"]
    assert cancelled["expected"]["execution_status"] == "cancelled"
    assert "partial_outputs_preserved" in cancelled["completion"]["criteria"]
    assert "cancel_stops_follow_up" in cancelled["completion"]["criteria"]


def test_validator_rejects_cycle_and_llm_scoring_fields():
    case = deepcopy(_load_behavior_cases()[0])
    case["expected"]["task_graph"][0]["depends_on"] = ["read_paper"]
    case["completion"]["score"] = 1

    errors = validate_cases([case], **_source_validation_args())

    assert any("循环依赖" in error for error in errors)
    assert any("禁止的 LLM/答案评分字段" in error for error in errors)


def test_validator_rejects_task_type_outside_goal_and_tool_outside_skill():
    case = deepcopy(_load_behavior_cases()[0])
    case["expected"]["task_graph"][0]["task_type"] = "WRITE_SECTION"
    case["allowed"]["task_types"] = ["READ_PAPER", "WRITE_SECTION"]
    case["allowed"]["tools"].append("project.search_content")

    errors = validate_cases([case], **_source_validation_args())

    assert any("不属于该 Goal" in error for error in errors)
    assert any("超出 Skill paper_internal" in error for error in errors)
