import asyncio
from datetime import datetime
from types import SimpleNamespace

from app.harness.runtime.tool_runtime import ToolContext
from app.harness.runtime.task_context import current_model_call_observer
from app.llm.client import invoke_with_retry
from app.models.execution import ModelCall, ToolCall
from evals.agent_runtime_metrics import (
    build_runtime_report,
    classify_failure,
    detect_duplicate_tool_calls,
)


def _execution(status="completed"):
    return {
        "id": "execution-1",
        "status": status,
        "started_at": datetime(2026, 1, 1, 0, 0, 0),
        "completed_at": datetime(2026, 1, 1, 0, 0, 2),
        "max_tool_calls": 10,
        "max_model_calls": 10,
        "max_tokens": 1000,
    }


def _task(task_id="task-1", status="completed", attempts=1, task_type="READ_PAPER", skill_id="paper_internal"):
    return {
        "task_id": task_id,
        "execution_id": "execution-1",
        "task_type": task_type,
        "status": status,
        "attempt_count": attempts,
        "skill_id": skill_id,
        "executor_type": "AGENT",
        "completion_payload": {"completion": {"passed": status == "completed"}},
        "error_code": None if status == "completed" else "TASK_FAILED",
    }


def _tool(call_id, *, status="completed", error_code=None, started=0, arguments=None):
    return {
        "id": call_id,
        "execution_id": "execution-1",
        "task_id": "task-1",
        "skill_id": "paper_internal",
        "tool_name": "paper.search_content",
        "arguments": arguments or {"query": "methods", "top_k": 5},
        "status": status,
        "error_code": error_code,
        "started_at": datetime(2026, 1, 1, 0, 0, started),
        "completed_at": datetime(2026, 1, 1, 0, 0, started + 1),
    }


def test_toolcall_and_modelcall_add_task_skill_correlation_fields():
    assert {"task_id", "skill_id"} <= set(ToolCall.__table__.columns.keys())
    assert {"task_id", "skill_id", "call_index", "model", "provider", "purpose", "input_tokens", "output_tokens",
            "status", "started_at", "completed_at", "duration_ms", "error_code"} <= set(ModelCall.__table__.columns.keys())
    context = ToolContext(db=None, user_id="u", execution_id="e")
    assert context.task_id is None and context.skill_id is None


def test_research_task_model_call_observer_emits_start_and_finish_without_prompt():
    class FakeRunnable:
        model_name = "test-model"

        async def ainvoke(self, _messages):
            return SimpleNamespace(response_metadata={"token_usage": {
                "prompt_tokens": 11, "completion_tokens": 7,
            }})

    async def run():
        events = []

        async def observer(stage, data):
            events.append((stage, data))

        token = current_model_call_observer.set(observer)
        try:
            await invoke_with_retry(FakeRunnable(), ["不应落盘的提示词"], max_retries=0)
        finally:
            current_model_call_observer.reset(token)
        return events

    events = asyncio.run(run())
    assert [stage for stage, _ in events] == ["started", "finished"]
    assert events[0][1]["model"] == "test-model"
    assert events[1][1]["input_tokens"] == 11
    assert events[1][1]["output_tokens"] == 7
    assert all("提示词" not in str(data) for _, data in events)


def test_runtime_report_aggregates_slices_and_model_budget_metrics():
    report = build_runtime_report(
        executions=[_execution()],
        tasks=[_task()],
        tool_calls=[_tool("tool-1"), _tool("tool-2", started=2)],
        model_calls=[{
            "id": "model-1", "execution_id": "execution-1", "task_id": "task-1",
            "skill_id": "paper_internal", "model": "test-model", "status": "completed",
            "input_tokens": 100, "output_tokens": 50, "started_at": datetime(2026, 1, 1),
            "completed_at": datetime(2026, 1, 1, 0, 0, 1),
        }],
    )
    assert report["sample_size"] == {"executions": 1, "tasks": 1, "tool_calls": 2, "model_calls": 1, "failure_records": 1}
    assert report["summary"]["task_success_rate"] == 1
    assert report["summary"]["calls_per_task"] == 2
    assert report["summary"]["model_calls_per_task"] == 1
    assert report["task_types"]["READ_PAPER"]["task_success_rate"] == 1
    assert report["skills"]["paper_internal"]["task_count"] == 1
    assert report["tools"]["paper.search_content"]["tool_call_count"] == 2
    assert report["models"]["test-model"]["avg_input_tokens_per_task"] == 100
    assert report["summary"]["budget"]["avg_token_utilization"] == 0.15


def test_duplicate_detector_does_not_classify_retry_after_error():
    first = _tool("tool-failed", status="failed", error_code="TOOL_TIMEOUT")
    retry = _tool("tool-retry", started=2)
    assert detect_duplicate_tool_calls([first, retry])["duplicate_count"] == 0
    assert classify_failure(tool_call=first) == "TOOL_TIMEOUT"


def test_duplicate_detector_is_order_independent_for_normalized_arguments():
    result = detect_duplicate_tool_calls([
        _tool("tool-1", arguments={"top_k": 5, "query": "methods"}),
        _tool("tool-2", started=2, arguments={"query": "methods", "top_k": 5}),
    ])
    assert result["duplicate_count"] == 1
    assert result["duplicate_rate"] == 0.5
    assert result["duplicates"][0]["execution_id"] == "execution-1"


def test_failure_taxonomy_is_deterministic_and_incomplete_task_is_not_success():
    expected = {
        "TOOL_INPUT_INVALID": "ARGUMENT_ERROR",
        "TOOL_TIMEOUT": "TOOL_TIMEOUT",
        "TOOL_EXECUTION_FAILED": "TOOL_FAILURE",
        "TOOL_CONTEXT_FORBIDDEN": "SCOPE_VIOLATION",
        "SKILL_TOOL_FORBIDDEN": "SCOPE_VIOLATION",
        "SKILL_TOOL_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
        "SKILL_EXTERNAL_SEARCH_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
        "SKILL_PAPER_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
    }
    for code, reason in expected.items():
        assert classify_failure(tool_call={"status": "failed", "error_code": code}) == reason
    assert classify_failure(task=_task(status="failed")) == "INCOMPLETE_TASK"
    assert classify_failure(tool_call={"status": "failed", "error_code": "UNMAPPED"}) == "UNKNOWN"


def test_empty_runtime_report_is_explicit_and_safe():
    report = build_runtime_report()
    assert report["sample_size"] == {"executions": 0, "tasks": 0, "tool_calls": 0, "model_calls": 0, "failure_records": 0}
    assert report["summary"]["execution_count"] == 0
    assert report["summary"]["task_success_rate"] == 0
    assert report["failures"]["unknown_count"] == 0
