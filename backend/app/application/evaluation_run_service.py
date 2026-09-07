"""EvaluationRun 的状态转换和 API 投影。

状态只在该服务和评测 Worker 中改变，API 不直接修改已存在运行的内部状态。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.evaluation import (
    EVALUATION_STATUSES,
    EvaluationRun,
)


EVALUATION_STATUS_TRANSITIONS = {
    "queued": {"running", "failed", "cancelled"},
    "running": {"running", "retrying", "completed", "failed", "cancelled"},
    "retrying": {"running", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class EvaluationRunStateError(ValueError):
    """评测运行状态转换不合法。"""


def transition_evaluation_run(
    run: EvaluationRun,
    target_status: str,
    *,
    now: datetime | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    summary: dict[str, Any] | None = None,
    report_path: str | None = None,
    markdown_path: str | None = None,
) -> EvaluationRun:
    if target_status not in EVALUATION_STATUSES:
        raise EvaluationRunStateError(f"未知评测运行状态: {target_status}")
    current = str(run.status)
    if target_status != current and target_status not in EVALUATION_STATUS_TRANSITIONS.get(current, set()):
        raise EvaluationRunStateError(f"评测运行不能从 {current} 转为 {target_status}")

    timestamp = now or datetime.utcnow()
    run.status = target_status
    run.updated_at = timestamp
    if target_status == "running" and run.started_at is None:
        run.started_at = timestamp
    if target_status in {"completed", "failed", "cancelled"}:
        run.completed_at = timestamp
    if summary is not None:
        run.summary = summary
    if report_path is not None:
        run.report_path = report_path
    if markdown_path is not None:
        run.markdown_path = markdown_path
    if error_code is not None:
        run.error_code = error_code
    if error_message is not None:
        run.error_message = error_message
    return run


def evaluation_run_dict(run: EvaluationRun, reports_dir: Path | None = None) -> dict[str, Any]:
    report_available = bool(run.report_path)
    markdown_available = bool(run.markdown_path)
    if reports_dir is not None:
        report_available = report_available and (reports_dir / str(run.report_path)).is_file()
        markdown_available = markdown_available and (reports_dir / str(run.markdown_path)).is_file()

    def iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    return {
        "id": run.id,
        "evaluation_type": run.evaluation_type,
        "status": run.status,
        "config": run.config or {},
        "summary": run.summary,
        "attempt_count": int(run.attempt_count or 0),
        "max_attempts": int(run.max_attempts or 0),
        "created_at": iso(run.created_at),
        "started_at": iso(run.started_at),
        "updated_at": iso(run.updated_at),
        "completed_at": iso(run.completed_at),
        "report_available": report_available,
        "markdown_available": markdown_available,
        "error": (
            {"code": run.error_code, "message": run.error_message}
            if run.error_code or run.error_message
            else None
        ),
    }
