import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.projects import (
    ArtifactCreate,
    MemoryNoteCreate,
    ProjectPaperCardUpdate,
    ProjectPaperReadingPlan,
    ReadingExecutionStart,
    _artifact_integrity_locked,
    _validate_artifact_create_integrity,
    _build_workflow_status,
)
from app.models.project import WritingArtifact
from app.harness.tools.literature_research import (
    ProjectAppendMemoryInput,
    ProjectSavePaperCardInput,
    ProjectSaveResearchBriefInput,
    ProjectSaveLiteratureScreeningInput,
    ProjectSaveResearchMapInput,
    ProjectSaveReadingPlanInput,
    ProjectBuildEvidenceMatrixInput,
    ProjectSaveExperimentDesignInput,
    ProjectSaveExperimentResultsInput,
    ProjectSavePaperBlueprintInput,
    ProjectSaveSectionDraftInput,
    ProjectAssembleFullDraftInput,
    _as_dict,
    ProjectAuditFullDraftInput,
    ProjectFinalizeManuscriptInput,
    ProjectBuildReferenceListInput,
    ProjectImportArxivPaperInput,
)


def test_rest_paper_card_preserves_structured_evidence():
    card = ProjectPaperCardUpdate(
        summary="核心结论",
        findings=["方法在目标数据集上更稳定"],
        evidence=[
            {
                "source_id": "S3",
                "page": 7,
                "section": "4.2 Experiments",
                "text": "实验结果支持该结论。",
            }
        ],
    )

    assert card.model_dump()["evidence"] == [
        {
            "source_id": "S3",
            "page": 7,
            "section": "4.2 Experiments",
            "text": "实验结果支持该结论。",
        }
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"summary": "x", "evidence": [{"page": 0, "text": "bad page"}]},
        {"summary": "x", "evidence": [{"page": 1, "text": ""}]},
    ],
)
def test_rest_paper_card_rejects_unusable_evidence(payload):
    with pytest.raises(ValidationError):
        ProjectPaperCardUpdate(**payload)


def test_memory_provenance_contract_matches_agent_tool():
    rest_note = MemoryNoteCreate(
        text="论文结论",
        source_type="paper",
        paper_id="paper-1",
        paper_title="A Paper",
        page=8,
        source_id="S2",
    )
    tool_note = ProjectAppendMemoryInput(
        note="论文结论",
        source_type="paper",
        paper_id="paper-1",
        paper_title="A Paper",
        page=8,
        source_id="S2",
    )

    assert rest_note.paper_id == tool_note.paper_id == "paper-1"
    assert rest_note.page == tool_note.page == 8
    assert rest_note.source_id == tool_note.source_id == "S2"


def test_rest_memory_rejects_invalid_provenance_values():
    with pytest.raises(ValidationError):
        MemoryNoteCreate(text="x", source_type="web")
    with pytest.raises(ValidationError):
        MemoryNoteCreate(text="x", source_type="paper", page=0)


def test_agent_card_schema_accepts_provenance_fields():
    card = ProjectSavePaperCardInput(
        paper_id="paper-1",
        evidence=[{"source_id": "S1", "page": 3, "section": "Method", "text": "Evidence"}],
    )

    assert card.evidence[0]["source_id"] == "S1"


def test_research_map_requires_a_topic_summary_and_keeps_decision_fields():
    research_map = ProjectSaveResearchMapInput(
        topic_summary="该领域关注跨域鲁棒性。",
        keywords=["domain generalization", "跨域鲁棒性"],
        research_gaps=[{"gap": "真实场景评测不足", "source_ids": ["S1", "S4"]}],
        candidate_topics=[
            {
                "title": "轻量跨域适配",
                "feasibility": "已有公开数据和基线",
                "next_step": "复现两个基线",
            }
        ],
    )

    assert research_map.research_gaps[0]["source_ids"] == ["S1", "S4"]
    assert research_map.candidate_topics[0]["next_step"] == "复现两个基线"

    with pytest.raises(ValueError):
        ProjectSaveResearchMapInput(topic_summary="")


def test_research_brief_requires_an_executable_search_query():
    brief = ProjectSaveResearchBriefInput(
        topic="可追溯研究 Agent", objective="形成可验证的论文选题",
        known_context=["用户希望覆盖完整论文流程"], unknowns=["领域基线是什么"],
        search_queries=["research agent provenance manuscript"],
        inclusion_criteria=["有可复现实验"], evaluation_criteria=["创新性", "可行性"],
    )
    assert brief.search_queries == ["research agent provenance manuscript"]
    with pytest.raises(ValueError):
        ProjectSaveResearchBriefInput(topic="x", objective="y", search_queries=[])


def test_literature_screening_requires_decisions_and_scores():
    screening = ProjectSaveLiteratureScreeningInput(
        query_runs=[{"source": "arxiv", "query": "research agents", "result_count": 12}],
        candidates=[{"title": "A traceable research agent", "arxiv_id": "2601.12345",
                     "decision": "include", "reason": "matches the research question",
                     "relevance_score": 92, "coverage": ["provenance"]}],
    )
    assert screening.candidates[0].decision == "include"
    with pytest.raises(ValueError):
        ProjectSaveLiteratureScreeningInput(
            query_runs=[{"source": "arxiv", "query": "x", "result_count": 1}],
            candidates=[{"title": "x", "decision": "unknown", "reason": "x", "relevance_score": 101}],
        )


def test_experiment_results_require_provenance_and_numeric_metrics():
    results = ProjectSaveExperimentResultsInput(
        experiment_design_id="design-1", run_id="run-2026-08-16",
        sources=[{"source_id": "R1", "source_type": "uploaded_file", "locator": "results.csv", "checksum": "abc"}],
        metrics=[{"metric": "F1", "value": 0.91, "dataset": "test", "source_id": "R1"}],
        hypothesis_outcome="mixed",
    )
    assert results.metrics[0].value == pytest.approx(0.91)
    with pytest.raises(ValueError):
        ProjectSaveExperimentResultsInput(
            experiment_design_id="design-1", run_id="run",
            sources=[], hypothesis_outcome="supported",
        )


def test_reading_plan_contract_captures_execution_intent():
    plan = ProjectSaveReadingPlanInput(
        objective="验证候选选题的可行性",
        items=[
            {
                "paper_id": "paper-1",
                "order": 1,
                "priority": 5,
                "reason": "代表性基线",
                "focus": ["方法", "消融实验"],
                "questions": ["跨域性能如何？"],
            }
        ],
    )
    assert plan.items[0].priority == 5
    assert plan.items[0].questions == ["跨域性能如何？"]

    with pytest.raises(ValueError):
        ProjectSaveReadingPlanInput(objective="x", items=[])


def test_rest_reading_status_is_bounded():
    assert ProjectPaperReadingPlan(status="reading", order=2).status == "reading"
    with pytest.raises(ValidationError):
        ProjectPaperReadingPlan(status="unknown")


def test_reading_execution_batch_size_is_bounded():
    assert ReadingExecutionStart(max_items=5).max_items == 5
    with pytest.raises(ValidationError):
        ReadingExecutionStart(max_items=0)


def test_evidence_matrix_requires_a_research_question():
    matrix = ProjectBuildEvidenceMatrixInput(
        research_question="不同方法在跨域设置下表现如何？",
        conflicts=[{"paper_ids": ["p1", "p2"], "source_ids": ["S1", "S4"]}],
        evidence_gaps=[{"dimension": "外部验证", "next_action": "补充真实数据"}],
    )
    assert matrix.conflicts[0]["source_ids"] == ["S1", "S4"]
    with pytest.raises(ValueError):
        ProjectBuildEvidenceMatrixInput(research_question="")


def test_experiment_design_requires_success_and_falsification_criteria():
    design = ProjectSaveExperimentDesignInput(
        research_question="方法是否提升跨域鲁棒性？",
        hypothesis="加入约束后，跨域 F1 将稳定提升。",
        rationale="证据矩阵显示现有方法在域偏移下退化。",
        experiment_steps=["训练基线", "加入约束并复现实验"],
        success_criteria=["三个随机种子平均 F1 提升且置信区间不跨零"],
        falsification_criteria=["提升不稳定或仅在单一数据集出现"],
    )
    assert design.falsification_criteria
    with pytest.raises(ValueError):
        ProjectSaveExperimentDesignInput(
            research_question="x", hypothesis="x", rationale="x",
            experiment_steps=["x"], success_criteria=["x"], falsification_criteria=[],
        )


def test_paper_blueprint_requires_multiple_planned_sections():
    blueprint = ProjectSavePaperBlueprintInput(
        working_title="A testable paper",
        central_claim="The proposed constraint improves robustness.",
        sections=[
            {"section_id": "intro", "title": "Introduction", "order": 1, "purpose": "Motivate"},
            {"section_id": "method", "title": "Method", "order": 2, "purpose": "Define method"},
            {"section_id": "experiments", "title": "Experiments", "order": 3, "purpose": "Test hypothesis"},
        ],
    )
    assert blueprint.sections[2].section_id == "experiments"
    with pytest.raises(ValueError):
        ProjectSavePaperBlueprintInput(
            working_title="x", central_claim="x",
            sections=[{"section_id": "intro", "title": "Intro", "order": 1, "purpose": "x"}],
        )


def test_section_draft_and_full_draft_contracts_keep_provenance_controls():
    draft = ProjectSaveSectionDraftInput(
        blueprint_id="blueprint-1", section_id="method", title="Method",
        markdown_text="# Method", evidence_refs=[{"paper_id": "p1", "source_id": "S2"}],
        unresolved_items=["补充复杂度分析"],
    )
    assembled = ProjectAssembleFullDraftInput(blueprint_id="blueprint-1", title="Full draft")
    assert draft.evidence_refs[0]["source_id"] == "S2"
    assert assembled.allow_unresolved_placeholders is False


def test_audit_and_finalization_contracts_are_bound_to_specific_draft():
    audit = ProjectAuditFullDraftInput(
        full_draft_id="draft-1",
        issues=[{
            "severity": "blocker", "category": "citation", "section_id": "intro",
            "description": "关键主张缺少引用。", "recommendation": "补充一手文献。",
            "evidence_refs": [{"paper_id": "p1", "source_id": "S2"}],
        }],
    )
    finalization = ProjectFinalizeManuscriptInput(
        full_draft_id="draft-1", review_report_id="report-1", title="Final manuscript",
    )
    assert audit.issues[0].severity == "blocker"
    assert finalization.review_report_id == "report-1"
    assert ProjectBuildReferenceListInput(blueprint_id="blueprint-1").title == "参考文献列表"


def test_integrity_artifacts_cannot_be_forged_through_generic_rest_contract():
    with pytest.raises(HTTPException) as final_error:
        _validate_artifact_create_integrity(ArtifactCreate(
            artifact_type="final_manuscript", title="Forged final",
        ))
    assert final_error.value.status_code == 409
    with pytest.raises(HTTPException) as results_error:
        _validate_artifact_create_integrity(ArtifactCreate(
            artifact_type="experiment_results", title="Invented metrics",
        ))
    assert results_error.value.status_code == 409
    with pytest.raises(HTTPException) as audit_error:
        _validate_artifact_create_integrity(ArtifactCreate(
            artifact_type="review_report", title="Forged audit", meta={"audit_kind": "full_draft"},
        ))
    assert audit_error.value.status_code == 400


def test_agent_integrity_artifacts_are_content_locked():
    reference_list = WritingArtifact(
        artifact_type="reference_list", title="References",
        meta={"generated_by": "deterministic_reference_builder"},
    )
    audit = WritingArtifact(artifact_type="review_report", title="Audit", meta={"audit_kind": "full_draft"})
    final = WritingArtifact(artifact_type="final_manuscript", title="Final", meta={})
    results = WritingArtifact(artifact_type="experiment_results", title="Results", meta={})
    assert all(_artifact_integrity_locked(item) for item in (reference_list, audit, results, final))


def test_nested_tool_models_are_normalized_before_implementation_use():
    plan = ProjectSaveReadingPlanInput(
        objective="verify", items=[{"paper_id": "p1", "order": 1}],
    )
    normalized = _as_dict(plan.items[0])
    assert normalized["paper_id"] == "p1"
    assert normalized["priority"] == 3
    assert ProjectImportArxivPaperInput(arxiv_id="2401.12345").reading_priority == 3


def test_workflow_status_points_to_first_missing_safe_stage():
    paper = type("ProjectPaperStub", (), {"analysis_card": {}})()
    status = _build_workflow_status([paper], [])
    assert status["next_stage"] == "research_brief"
    assert status["stages"][0]["status"] == "current"
    assert "研究任务书" in status["next_prompt"]
    assert status["mode"] == "workbench"
    assert [area["key"] for area in status["areas"]] == ["topic", "reading", "writing"]
    assert status["areas"][0]["primary_action"] == "开始选题"
    assert status["areas"][1]["metrics"]["papers"] == 1


def test_workflow_status_does_not_treat_unresolved_sections_as_complete():
    blueprint = WritingArtifact(
        id="blueprint-1", artifact_type="paper_blueprint", title="Blueprint",
        content={"sections": [{"section_id": "intro"}]}, meta={},
    )
    draft = WritingArtifact(
        artifact_type="section_draft", title="Intro", parent_id="blueprint-1",
        content={}, meta={"section_id": "intro", "unresolved_items": ["citation"]},
    )
    status = _build_workflow_status([], [blueprint, draft])
    section_stage = next(item for item in status["stages"] if item["key"] == "section_drafts")
    assert section_stage["status"] != "completed"
    assert status["unresolved_items"] == 1


def test_workflow_requires_results_only_for_empirical_designs():
    empirical = WritingArtifact(
        id="design-1", artifact_type="experiment_design", title="Empirical",
        content={"requires_empirical_results": True}, meta={},
    )
    status = _build_workflow_status([], [empirical])
    results_stage = next(item for item in status["stages"] if item["key"] == "experiment_results")
    assert results_stage["status"] != "completed"
    results = WritingArtifact(
        artifact_type="experiment_results", title="Results",
        content={"experiment_design_id": "design-1"}, meta={},
    )
    status = _build_workflow_status([], [empirical, results])
    results_stage = next(item for item in status["stages"] if item["key"] == "experiment_results")
    assert results_stage["status"] == "completed"

    theoretical = WritingArtifact(
        id="design-2", artifact_type="experiment_design", title="Theory",
        content={"requires_empirical_results": False}, meta={},
    )
    status = _build_workflow_status([], [theoretical])
    results_stage = next(item for item in status["stages"] if item["key"] == "experiment_results")
    assert results_stage["status"] == "completed"
