from datetime import datetime

from app.application.execution_service import event_envelope, execution_dict
from app.main import app
from app.models.execution import AgentEvent, AgentExecution, EXECUTION_STATUSES


def test_execution_contract_has_all_required_states_and_budget_fields():
    assert EXECUTION_STATUSES == {"queued", "running", "waiting_user", "paused", "completed", "failed", "cancelled"}
    columns = set(AgentExecution.__table__.columns.keys())
    assert {"max_tool_calls", "max_model_calls", "max_tokens", "max_seconds"} <= columns
    assert {"tool_call_count", "model_call_count", "input_tokens", "output_tokens"} <= columns


def test_public_event_envelope_excludes_private_reasoning():
    event = AgentEvent(id="event-1", execution_id="execution-1", seq=3, event_type="stage_changed",
                       stage="planning", message="正在制定计划", payload={"visible": True}, created_at=datetime(2026, 1, 1))
    payload = event_envelope(event)
    assert set(payload) == {"id", "seq", "execution_id", "type", "timestamp", "stage", "message", "data"}
    assert "reasoning" not in payload and "chain_of_thought" not in payload


def test_execution_serialization_is_json_safe():
    item = AgentExecution(id="execution-1", user_id="user-1", project_id="project-1",
                          agent_type="mock_agent", goal="test")
    payload = execution_dict(item)
    assert payload["id"] == "execution-1"
    assert payload["status"] is None  # SQL defaults are applied on insert.


def test_execution_api_routes_are_registered():
    routes = {(route.path, tuple(route.methods or ())) for route in app.routes}
    paths = {path for path, _ in routes}
    assert "/api/v1/projects/{project_id}/executions" in paths
    assert "/api/v1/executions/{execution_id}/events" in paths
    assert "/api/v1/executions/{execution_id}/stream" in paths
    for action in ("cancel", "pause", "resume", "approve"):
        assert f"/api/v1/executions/{{execution_id}}/{action}" in paths
