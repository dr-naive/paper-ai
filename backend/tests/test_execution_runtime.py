from datetime import datetime, timedelta

import pytest

from app.application.citation_verification_service import CitationVerificationResult
from app.application.execution_service import (
    CompletionGateError,
    evaluate_execution_trace,
    event_envelope,
    execution_dict,
    execution_trace_report,
    validate_writing_completion,
)
from app.application.writing_service import WritingGenerationProposal
from app.main import app
from app.models.execution import AgentEvent, AgentExecution, EXECUTION_STATUSES


def test_execution_contract_has_all_required_states_and_budget_fields():
    assert {"pending", "queued", "running", "waiting_user", "paused", "retrying", "completed", "partial", "blocked", "failed", "cancelled"} == EXECUTION_STATUSES
    columns = set(AgentExecution.__table__.columns.keys())
    assert {"max_tool_calls", "max_model_calls", "max_tokens", "max_seconds"} <= columns
    assert {"tool_call_count", "model_call_count", "input_tokens", "output_tokens"} <= columns
    assert {"input_payload", "result_payload"} <= columns


def test_public_event_envelope_excludes_private_reasoning():
    event = AgentEvent(id="event-1", execution_id="execution-1", seq=3, event_type="stage_changed",
                       stage="planning", message="正在制定计划", payload={"visible": True}, created_at=datetime(2026, 1, 1))
    payload = event_envelope(event)
    assert set(payload) == {"id", "seq", "execution_id", "type", "timestamp", "stage", "message", "data"}
    assert "reasoning" not in payload and "chain_of_thought" not in payload


def test_execution_serialization_is_json_safe():
    item = AgentExecution(id="execution-1", user_id="user-1", project_id="project-1",
                          agent_type="mock_agent", goal="test", plan={"tasks": [{"task_type": "READ_PAPER"}]})
    payload = execution_dict(item)
    assert payload["id"] == "execution-1"
    assert payload["status"] is None  # SQL defaults are applied on insert.
    assert "plan" not in payload  # Internal DAG stays server-side; progress is the public projection.


def _writing_proposal(status: str = "ready", citation_status: str = "verified") -> WritingGenerationProposal:
    return WritingGenerationProposal(
        proposal_id="proposal-1",
        project_id="project-1",
        document_id="document-1",
        base_revision_id="revision-1",
        status=status,
        content="Evidence-backed paragraph [[CITATION:cite-1]].",
        citations=[CitationVerificationResult(
            citation_key="cite-1", paper_id="paper-1", evidence_id="evidence-1",
            status=citation_status, code="semantic_result", reason="Supported",
            claim_text="Evidence-backed paragraph.", original_claim="Evidence-backed paragraph.",
        )],
        citation_style="apa",
        review={"status": "passed", "issue_codes": [], "repair_count": 0},
    )


def test_writing_completion_gate_accepts_verified_structured_proposal():
    execution = AgentExecution(
        id="execution-1", user_id="user-1", project_id="project-1",
        agent_type="writing_generate", goal="draft", active_skill="writing_evidence_generation",
        input_payload={"document_id": "document-1"},
    )

    result = validate_writing_completion(execution, _writing_proposal(), {"passed": True})

    assert result["passed"] is True
    assert result["verified_count"] == 1


def test_writing_completion_gate_rejects_unsupported_citation():
    execution = AgentExecution(
        id="execution-1", user_id="user-1", project_id="project-1",
        agent_type="writing_generate", goal="draft", active_skill="writing_evidence_generation",
        input_payload={"document_id": "document-1"},
    )

    with pytest.raises(CompletionGateError, match="unsupported_citation"):
        validate_writing_completion(
            execution,
            _writing_proposal(status="verification_failed", citation_status="unsupported"),
            {"passed": True},
        )


def test_writing_completion_gate_requires_active_skill_completion():
    execution = AgentExecution(
        id="execution-1", user_id="user-1", project_id="project-1",
        agent_type="writing_generate", goal="draft", active_skill="writing_evidence_generation",
        input_payload={"document_id": "document-1"},
    )

    with pytest.raises(CompletionGateError, match="skill_completion_failed"):
        validate_writing_completion(execution, _writing_proposal(), {"passed": False})


def test_durable_worker_activates_and_evaluates_writing_skill_without_review_reasoning():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "app" / "worker.py").read_text(encoding="utf-8")

    assert 'WRITING_SKILL_ID = "writing_evidence_generation"' in source
    assert "skill_runtime.activate" in source
    assert "skill_runtime.evaluate_completion" in source
    assert '"skill_completion_evaluated"' in source
    assert "chain_of_thought" not in source


def test_execution_api_routes_are_registered():
    routes = {(route.path, tuple(route.methods or ())) for route in app.routes}
    paths = {path for path, _ in routes}
    assert "/api/v1/projects/{project_id}/executions" in paths
    assert "/api/v1/executions" in paths
    assert "/api/v1/executions/{execution_id}/events" in paths
    assert "/api/v1/executions/{execution_id}/trace" in paths
    assert "/api/v1/executions/{execution_id}/evaluation" in paths
    assert "/api/v1/executions/{execution_id}/stream" in paths
    for action in ("cancel", "pause", "resume", "approve"):
        assert f"/api/v1/executions/{{execution_id}}/{action}" in paths
    assert "/api/v1/executions/{execution_id}/respond" in paths


def test_execution_trace_is_ordered_quality_aware_and_privacy_safe():
    started = datetime(2026, 8, 30, 8, 0, 0)
    execution = AgentExecution(
        id="execution-1", user_id="user-1", project_id="project-1",
        agent_type="writing_generate", runtime_version="v2", status="completed",
        current_stage="completed", goal="private user instruction",
        input_payload={
            "document_id": "document-1", "instruction": "private user instruction",
            "nearby_text": "private document content", "section_path": ["Intro", "Prior work"],
            "citation_style": "apa",
        },
        result_payload={
            "proposal": {"status": "ready", "content": "private model output", "citations": [{"status": "verified"}]},
            "completion": {"passed": True, "proposal_status": "ready", "citation_count": 1,
                           "verified_count": 1, "weak_count": 0, "checks": ["structured_citation_mapping"]},
        },
        started_at=started, completed_at=started + timedelta(seconds=3), updated_at=started + timedelta(seconds=3),
        max_tool_calls=30, max_model_calls=20, max_tokens=100000, max_seconds=1800,
        tool_call_count=2, model_call_count=1, input_tokens=120, output_tokens=80,
    )
    events = [
        AgentEvent(id="e2", execution_id=execution.id, seq=2, event_type="citation_verified",
                   stage="citation_verified", message="done", payload={"provider_payload": "private"},
                   created_at=started + timedelta(seconds=2)),
        AgentEvent(id="e1", execution_id=execution.id, seq=1, event_type="execution_started",
                   stage="starting", message="start", payload={}, created_at=started),
    ]

    report = execution_trace_report(execution, events)

    assert report["total_ms"] == 3000
    assert [span["seq"] for span in report["spans"]] == [1, 2]
    assert report["spans"][0]["duration_ms"] == 2000
    assert report["quality"]["completion_gate_passed"] is True
    assert report["budget"]["model_calls"] == {"used": 1, "limit": 20}
    assert report["input_summary"] == {
        "document_id": "document-1", "section_depth": 2,
        "has_nearby_context": True, "citation_style": "apa",
    }
    serialized = str(report)
    assert "private user instruction" not in serialized
    assert "private document content" not in serialized
    assert "private model output" not in serialized
    assert "provider_payload" not in serialized


def test_execution_trace_records_control_transitions_and_failed_span():
    started = datetime(2026, 8, 30, 8, 0, 0)
    execution = AgentExecution(
        id="execution-2", user_id="user-1", project_id="project-1", agent_type="writing_generate",
        runtime_version="v2", status="failed", current_stage="completion_gate", goal="draft",
        input_payload={"document_id": "document-1"}, result_payload={}, started_at=started,
        completed_at=started + timedelta(seconds=1), updated_at=started + timedelta(seconds=1),
        max_tool_calls=30, max_model_calls=20, max_tokens=100000, max_seconds=1800,
        tool_call_count=0, model_call_count=0, input_tokens=0, output_tokens=0,
        error_code="COMPLETION_GATE_FAILED", error_message="unsupported_citation",
    )
    events = [
        AgentEvent(id="e1", execution_id=execution.id, seq=1, event_type="execution_paused",
                   stage="generation_started", message="paused", payload={}, created_at=started),
        AgentEvent(id="e2", execution_id=execution.id, seq=2, event_type="execution_resumed",
                   stage="generation_started", message="resumed", payload={}, created_at=started + timedelta(milliseconds=200)),
        AgentEvent(id="e3", execution_id=execution.id, seq=3, event_type="completion_gate_failed",
                   stage="completion_gate", message="failed", payload={}, created_at=started + timedelta(milliseconds=800)),
    ]

    report = execution_trace_report(execution, events)

    assert [item["type"] for item in report["control_transitions"]] == ["execution_paused", "execution_resumed"]
    assert report["spans"][-1]["outcome"] == "error"
    assert report["error"]["code"] == "COMPLETION_GATE_FAILED"


def _evaluation_trace(*, status="completed", gate=True, weak=0, unsupported=0, citations=1, stages=None):
    stage_names = stages or [
        "context_started", "context_ready", "generation_started", "citation_verified", "completion_gate",
    ]
    return {
        "trace_id": "execution-1", "status": status, "total_ms": 2500,
        "quality": {
            "completion_gate_passed": gate, "citation_count": citations,
            "verified_count": max(0, citations - weak - unsupported),
            "weak_count": weak, "unsupported_count": unsupported,
        },
        "budget": {
            "tool_calls": {"used": 2, "limit": 30},
            "model_calls": {"used": 1, "limit": 20},
            "tokens": {"input": 100, "output": 50, "limit": 100000},
        },
        "spans": [{"stage": stage, "duration_ms": 100} for stage in stage_names],
    }


@pytest.mark.parametrize(
    ("trace", "verdict", "score"),
    [
        (_evaluation_trace(), "pass", 100),
        (_evaluation_trace(weak=1), "pass", 93),
        (_evaluation_trace(status="failed", gate=False, unsupported=1), "fail", 25),
        (_evaluation_trace(status="failed", gate=False, citations=0), "fail", 25),
        (_evaluation_trace(status="paused", gate=False, citations=0, stages=["context_started"]), "incomplete", 15),
    ],
)
def test_execution_evaluation_scenarios_are_deterministic(trace, verdict, score):
    first = evaluate_execution_trace(trace)
    second = evaluate_execution_trace(trace)

    assert first == second
    assert first["verdict"] == verdict
    assert first["score"] == score
    assert sum(item["maximum"] for item in first["checks"]) == 100


def test_execution_evaluation_rejects_budget_overrun_even_with_valid_output():
    trace = _evaluation_trace()
    trace["budget"]["model_calls"] = {"used": 21, "limit": 20}

    result = evaluate_execution_trace(trace)

    assert result["verdict"] == "fail"
    assert result["score"] == 90
    assert next(item for item in result["checks"] if item["name"] == "budget_compliance")["passed"] is False
