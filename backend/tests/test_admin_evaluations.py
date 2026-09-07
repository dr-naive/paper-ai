import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.application.admin_evaluation_runner import default_evaluation_config
from app.application.evaluation_run_service import (
    EvaluationRunStateError,
    transition_evaluation_run,
)
from app.models.evaluation import EvaluationRun


def test_evaluation_run_has_one_explicit_state_machine():
    run = EvaluationRun(status="queued", evaluation_type="runtime")
    transition_evaluation_run(run, "running", now=datetime(2026, 9, 7, 10, 0))
    assert run.status == "running"
    assert run.started_at == datetime(2026, 9, 7, 10, 0)

    transition_evaluation_run(run, "retrying", now=datetime(2026, 9, 7, 10, 1))
    transition_evaluation_run(run, "running", now=datetime(2026, 9, 7, 10, 2))
    transition_evaluation_run(run, "completed", summary={"case_count": 3}, now=datetime(2026, 9, 7, 10, 3))
    assert run.completed_at == datetime(2026, 9, 7, 10, 3)
    assert run.summary == {"case_count": 3}

    with pytest.raises(EvaluationRunStateError):
        transition_evaluation_run(run, "running")


def test_queue_failure_can_be_persisted_without_touching_agent_execution():
    run = EvaluationRun(status="queued", evaluation_type="runtime")
    transition_evaluation_run(
        run,
        "failed",
        error_code="EVALUATION_QUEUE_UNAVAILABLE",
        error_message="Redis 不可用",
    )
    assert run.status == "failed"
    assert run.error_code == "EVALUATION_QUEUE_UNAVAILABLE"


def test_default_configs_are_stable_and_do_not_accept_unknown_type():
    assert default_evaluation_config("runtime") == {"scope": "all_executions"}
    assert default_evaluation_config("retrieval")["dataset"] == "paperqa_v1.jsonl"
    assert default_evaluation_config("e2e")["split"] == "test"
    with pytest.raises(ValueError, match="不支持的评测类型"):
        default_evaluation_config("behavior")


def test_runner_reuses_a_completed_report(monkeypatch, tmp_path):
    import app.application.admin_evaluation_runner as runner

    report_dir = tmp_path / "reports"
    monkeypatch.setattr(runner, "REPORTS_DIR", report_dir)
    monkeypatch.setattr(runner, "ADMIN_REPORTS_DIR", report_dir / "admin_evaluations")
    report_path, markdown_path, _ = runner.report_paths("run-1")
    report_path.write_text(json.dumps({"report_type": "agent_runtime", "summary": {"case_count": 2}}), encoding="utf-8")
    markdown_path.write_text("# 已有报告", encoding="utf-8")

    called = False

    async def should_not_run(_args):
        nonlocal called
        called = True

    monkeypatch.setattr("evals.run_agent_runtime_report.async_main", should_not_run, raising=False)
    result = asyncio.run(runner.run_admin_evaluation("run-1", "runtime"))

    assert result[0]["summary"]["case_count"] == 2
    assert result[1] == "admin_evaluations/run-1.json"
    assert result[2] == "admin_evaluations/run-1.md"
    assert called is False


def test_worker_dispatch_registers_admin_evaluation(monkeypatch):
    from app import worker
    from app.job_queue import WorkerJob

    handled = []

    async def fake_handler(job):
        handled.append(job.type)

    monkeypatch.setattr(worker, "handle_admin_evaluation", fake_handler)
    asyncio.run(worker.dispatch_job(WorkerJob.create("admin_evaluation", {"evaluation_run_id": "run-1"})))
    assert handled == ["admin_evaluation"]


def test_worker_persists_completed_result_and_reuses_same_run(monkeypatch):
    from app import worker
    from app.job_queue import WorkerJob

    run = EvaluationRun(
        id="run-1",
        evaluation_type="runtime",
        status="queued",
        config={"scope": "all_executions"},
    )

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, model, identifier):
            return run if identifier == run.id else None

        async def commit(self):
            return None

    runner = AsyncMock(return_value=(
        {"summary": {"case_count": 2}},
        "admin_evaluations/run-1.json",
        "admin_evaluations/run-1.md",
    ))
    monkeypatch.setattr(worker, "AsyncSessionLocal", lambda: Session())
    monkeypatch.setattr("app.application.admin_evaluation_runner.run_admin_evaluation", runner)

    asyncio.run(worker.handle_admin_evaluation(WorkerJob.create(
        "admin_evaluation", {"evaluation_run_id": "run-1"}, job_id="evaluation:run-1"
    )))

    assert run.status == "completed"
    assert run.attempt_count == 1
    assert run.summary == {"case_count": 2}
    assert run.report_path == "admin_evaluations/run-1.json"
    runner.assert_awaited_once_with("run-1", "runtime", {"scope": "all_executions"})


def test_worker_marks_transient_evaluation_error_for_existing_queue_retry(monkeypatch):
    from app import worker
    from app.job_queue import WorkerJob

    run = EvaluationRun(id="run-2", evaluation_type="runtime", status="queued", config={})

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, model, identifier):
            return run if identifier == run.id else None

        async def commit(self):
            return None

    runner = AsyncMock(side_effect=RuntimeError("temporary provider error"))
    monkeypatch.setattr(worker, "AsyncSessionLocal", lambda: Session())
    monkeypatch.setattr("app.application.admin_evaluation_runner.run_admin_evaluation", runner)

    with pytest.raises(RuntimeError, match="temporary provider error"):
        asyncio.run(worker.handle_admin_evaluation(WorkerJob.create(
            "admin_evaluation", {"evaluation_run_id": "run-2"}
        )))
    assert run.status == "retrying"

    retry = WorkerJob.create("admin_evaluation", {"evaluation_run_id": "run-2"})
    retry.attempts = 3
    with pytest.raises(RuntimeError, match="temporary provider error"):
        asyncio.run(worker.handle_admin_evaluation(retry))
    assert run.status == "failed"


def test_admin_evaluation_api_routes_are_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/admin/evaluations" in paths
    assert "/api/admin/evaluations/{run_id}" in paths
