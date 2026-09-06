"""Deterministic metrics for the existing Agent/ResearchTask runtime.

This module deliberately accepts ORM rows *or* small mapping fixtures.  It
does not inspect prompts, model reasoning, secrets or provider payloads.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable


FAILURE_REASON_MAP = {
    "TOOL_INPUT_INVALID": "ARGUMENT_ERROR",
    "TOOL_TIMEOUT": "TOOL_TIMEOUT",
    "TOOL_EXECUTION_FAILED": "TOOL_FAILURE",
    "TOOL_CONTEXT_FORBIDDEN": "SCOPE_VIOLATION",
    "SKILL_TOOL_FORBIDDEN": "SCOPE_VIOLATION",
    "SKILL_TOOL_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
    "SKILL_EXTERNAL_SEARCH_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
    "SKILL_PAPER_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
    "TASK_SKILL_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
    "TOOL_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
    "MODEL_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
    "TOKEN_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
    "TIME_BUDGET_EXCEEDED": "BUDGET_EXCEEDED",
}

TERMINAL_TASK_STATUSES = {"completed", "partial", "blocked", "failed", "cancelled"}
SUCCESS_TOOL_STATUSES = {"completed", "success", "succeeded", "ok"}
FAILURE_TOOL_STATUSES = {"failed", "failure", "error", "timeout"}
SUCCESS_MODEL_STATUSES = {"completed", "success", "succeeded", "ok"}


def _get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _as_list(rows: Iterable[Any] | None) -> list[Any]:
    return list(rows or [])


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _sort_datetime(value: Any) -> float:
    parsed = _datetime(value)
    if parsed is None:
        return float("-inf")
    if parsed.tzinfo is not None:
        return parsed.timestamp()
    return parsed.replace(tzinfo=timezone.utc).timestamp()


def _duration_ms(row: Any, *, now: datetime | None = None) -> float | None:
    stored = _get(row, "duration_ms")
    if stored is not None:
        return max(0.0, _number(stored))
    started = _datetime(_get(row, "started_at"))
    completed = _datetime(_get(row, "completed_at"))
    if started is None:
        return None
    end = completed or _datetime(_get(row, "updated_at")) or now or datetime.now(timezone.utc)
    if started.tzinfo is None and end.tzinfo is not None:
        end = end.replace(tzinfo=None)
    if started.tzinfo is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0.0, (end - started).total_seconds() * 1000)


def percentile(values: Iterable[float], quantile: float) -> float:
    values = sorted(float(value) for value in values)
    if not values:
        return 0.0
    quantile = min(1.0, max(0.0, quantile))
    position = (len(values) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(values[lower], 2)
    weight = position - lower
    return round(values[lower] * (1 - weight) + values[upper] * weight, 2)


def _rate(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 6) if denominator else 0.0


def _avg(values: Iterable[float]) -> float:
    values = list(values)
    return round(sum(values) / len(values), 2) if values else 0.0


def _json_key(value: Any) -> str:
    """Canonical argument representation used only by duplicate detection."""
    try:
        return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return repr(value)


def _tool_ok(row: Any) -> bool:
    status = str(_get(row, "status", "")).lower()
    return status in SUCCESS_TOOL_STATUSES and not _get(row, "error_code")


def _model_ok(row: Any) -> bool:
    return str(_get(row, "status", "")).lower() in SUCCESS_MODEL_STATUSES and not _get(row, "error_code")


def detect_duplicate_tool_calls(tool_calls: Iterable[Any]) -> dict[str, Any]:
    """Observe repeated successful actions within one ResearchTask.

    A failed/timeout call resets the consecutive-success window, so a normal
    retry after an error is not reported as a duplicate action.
    """
    rows = [row for row in _as_list(tool_calls) if _get(row, "task_id")]
    groups: dict[tuple[str, str, str, str], list[Any]] = defaultdict(list)
    for row in rows:
        key = (
            str(_get(row, "execution_id", "")),
            str(_get(row, "task_id", "")),
            str(_get(row, "tool_name", "")),
            _json_key(_get(row, "arguments", {})),
        )
        groups[key].append(row)

    duplicates: list[dict[str, Any]] = []
    duplicate_call_ids: set[str] = set()
    for (execution_id, task_id, tool_name, _), grouped in groups.items():
        grouped.sort(key=lambda item: (
            _sort_datetime(_get(item, "started_at")),
            str(_get(item, "id", "")),
        ))
        previous_success: Any | None = None
        for row in grouped:
            if not _tool_ok(row):
                previous_success = None
                continue
            if previous_success is not None:
                ids = [str(_get(previous_success, "id", "")), str(_get(row, "id", ""))]
                duplicate_call_ids.add(ids[-1])
                duplicates.append({
                    "execution_id": execution_id,
                    "task_id": task_id,
                    "tool_name": tool_name,
                    "tool_call_ids": ids,
                    "duplicate_call_ids": [ids[-1]],
                })
            previous_success = row

    return {
        "duplicate_count": len(duplicate_call_ids),
        "duplicate_group_count": len(duplicates),
        "duplicate_rate": _rate(len(duplicate_call_ids), len(rows)),
        "duplicates": duplicates,
    }


def _completion_passed(task: Any) -> bool:
    payload = _get(task, "completion_payload") or {}
    if not isinstance(payload, dict):
        return False
    completion = payload.get("completion") or {}
    return bool(completion) and all(value is True for value in completion.values())


def classify_failure(*, tool_call: Any | None = None, task: Any | None = None,
                     duplicate: bool = False) -> str:
    """Map persisted deterministic signals to the stable failure taxonomy."""
    if duplicate:
        return "DUPLICATE_ACTION"
    if tool_call is not None:
        code = str(_get(tool_call, "error_code") or "")
        if code in FAILURE_REASON_MAP:
            return FAILURE_REASON_MAP[code]
        status = str(_get(tool_call, "status", "")).lower()
        if status in FAILURE_TOOL_STATUSES:
            return "UNKNOWN"
    if task is not None and str(_get(task, "status", "")) == "failed" and not _completion_passed(task):
        code = str(_get(task, "error_code") or "")
        if code in FAILURE_REASON_MAP:
            return FAILURE_REASON_MAP[code]
        return "INCOMPLETE_TASK"
    return "UNKNOWN"


def _execution_metrics(executions: list[Any]) -> dict[str, Any]:
    count = len(executions)
    statuses = Counter(str(_get(row, "status", "")) for row in executions)
    durations = [value for row in executions if (value := _duration_ms(row)) is not None]
    return {
        "execution_count": count,
        "completed_rate": _rate(statuses["completed"], count),
        "partial_rate": _rate(statuses["partial"], count),
        "failed_rate": _rate(statuses["failed"], count),
        "blocked_rate": _rate(statuses["blocked"], count),
        "waiting_user_rate": _rate(statuses["waiting_user"], count),
        "avg_duration": _avg(durations),
        "p50_duration": percentile(durations, 0.50),
        "p95_duration": percentile(durations, 0.95),
        "avg_duration_ms": _avg(durations),
        "p50_duration_ms": percentile(durations, 0.50),
        "p95_duration_ms": percentile(durations, 0.95),
        "duration_unit": "ms",
    }


def _task_metrics(tasks: list[Any]) -> dict[str, Any]:
    count = len(tasks)
    statuses = Counter(str(_get(row, "status", "")) for row in tasks)
    attempts = [_integer(_get(row, "attempt_count"), 0) for row in tasks]
    retries = sum(
        attempt > 1 or str(_get(row, "status", "")) == "retrying"
        for attempt, row in zip(attempts, tasks)
    )
    return {
        "task_count": count,
        "task_success_rate": _rate(statuses["completed"], count),
        "task_partial_rate": _rate(statuses["partial"], count),
        "task_failure_rate": _rate(statuses["failed"], count),
        "retry_rate": _rate(retries, count),
        "avg_attempt_count": _avg(attempts),
    }


def _task_slice(tasks: list[Any], key: str) -> dict[str, Any]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for task in tasks:
        grouped[str(_get(task, key) or "未设置")].append(task)
    return {name: _task_metrics(rows) for name, rows in sorted(grouped.items())}


def _task_usage_slice(tasks: list[Any], key: str, tool_calls: list[Any], model_calls: list[Any]) -> dict[str, Any]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for task in tasks:
        grouped[str(_get(task, key) or "未设置")].append(task)
    result = {}
    for name, rows in sorted(grouped.items()):
        task_ids = {str(_get(row, "task_id")) for row in rows}
        result[name] = {
            **_task_metrics(rows),
            "tool_call_count": sum(str(_get(row, "task_id")) in task_ids for row in tool_calls),
            "model_call_count": sum(str(_get(row, "task_id")) in task_ids for row in model_calls),
        }
    return result


def _tool_metrics(tool_calls: list[Any], tasks: list[Any]) -> dict[str, Any]:
    count = len(tool_calls)
    successes = sum(_tool_ok(row) for row in tool_calls)
    failures = sum(not _tool_ok(row) for row in tool_calls)
    timeouts = sum(str(_get(row, "error_code") or "") == "TOOL_TIMEOUT" for row in tool_calls)
    invalid = sum(str(_get(row, "error_code") or "") == "TOOL_INPUT_INVALID" for row in tool_calls)
    latencies = [value for row in tool_calls if (value := _duration_ms(row)) is not None]
    task_ids = {str(_get(row, "task_id")) for row in tool_calls if _get(row, "task_id")}
    calls_per_task = _number(count / len(task_ids)) if task_ids else 0.0
    return {
        "tool_call_count": count,
        "success_rate": _rate(successes, count),
        "failure_rate": _rate(failures, count),
        "timeout_rate": _rate(timeouts, count),
        "input_invalid_rate": _rate(invalid, count),
        "avg_latency": _avg(latencies),
        "p50_latency": percentile(latencies, 0.50),
        "p95_latency": percentile(latencies, 0.95),
        "avg_latency_ms": _avg(latencies),
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "latency_unit": "ms",
        "calls_per_task": round(calls_per_task, 2),
    }


def _model_metrics(model_calls: list[Any], tasks: list[Any]) -> dict[str, Any]:
    count = len(model_calls)
    errors = sum(not _model_ok(row) for row in model_calls)
    latencies = [value for row in model_calls if (value := _duration_ms(row)) is not None]
    input_tokens = [_integer(_get(row, "input_tokens"), 0) for row in model_calls]
    output_tokens = [_integer(_get(row, "output_tokens"), 0) for row in model_calls]
    task_ids = {str(_get(row, "task_id")) for row in model_calls if _get(row, "task_id")}
    if not task_ids:
        task_ids = {str(_get(row, "execution_id")) for row in model_calls if _get(row, "execution_id")}
    denominator = len(task_ids)
    return {
        "model_call_count": count,
        "model_calls_per_task": round(count / denominator, 2) if denominator else 0.0,
        "avg_input_tokens_per_task": round(sum(input_tokens) / denominator, 2) if denominator else 0.0,
        "avg_output_tokens_per_task": round(sum(output_tokens) / denominator, 2) if denominator else 0.0,
        "model_error_rate": _rate(errors, count),
        "avg_latency": _avg(latencies),
        "p50_latency": percentile(latencies, 0.50),
        "p95_latency": percentile(latencies, 0.95),
        "avg_latency_ms": _avg(latencies),
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "latency_unit": "ms",
    }


def _budget_metrics(executions: list[Any], tasks: list[Any], tool_calls: list[Any], model_calls: list[Any]) -> dict[str, Any]:
    tools_by_execution = Counter(str(_get(row, "execution_id")) for row in tool_calls)
    models_by_execution = Counter(str(_get(row, "execution_id")) for row in model_calls)
    tokens_by_execution = Counter()
    for row in model_calls:
        execution_id = str(_get(row, "execution_id"))
        tokens_by_execution[execution_id] += _integer(_get(row, "input_tokens"), 0) + _integer(_get(row, "output_tokens"), 0)

    tool_utilization = []
    model_utilization = []
    token_utilization = []
    near_budget: list[dict[str, Any]] = []
    near_budget_tasks: list[dict[str, Any]] = []
    exceeded = 0
    for execution in executions:
        execution_id = str(_get(execution, "id", ""))
        # AgentExecution counters also cover compatible/instant paths whose
        # fine-grained rows predate this observability block.
        tools_by_execution[execution_id] = max(
            tools_by_execution[execution_id], _integer(_get(execution, "tool_call_count"), 0)
        )
        models_by_execution[execution_id] = max(
            models_by_execution[execution_id], _integer(_get(execution, "model_call_count"), 0)
        )
        tokens_by_execution[execution_id] = max(
            tokens_by_execution[execution_id],
            _integer(_get(execution, "input_tokens"), 0) + _integer(_get(execution, "output_tokens"), 0),
        )
        tool_limit = _integer(_get(execution, "max_tool_calls"), 0)
        model_limit = _integer(_get(execution, "max_model_calls"), 0)
        token_limit = _integer(_get(execution, "max_tokens"), 0)
        tool_ratio = tools_by_execution[execution_id] / tool_limit if tool_limit else 0.0
        model_ratio = models_by_execution[execution_id] / model_limit if model_limit else 0.0
        token_ratio = tokens_by_execution[execution_id] / token_limit if token_limit else 0.0
        tool_utilization.append(tool_ratio)
        model_utilization.append(model_ratio)
        token_utilization.append(token_ratio)
        budget_error = any(
            str(_get(row, "error_code") or "") in FAILURE_REASON_MAP
            and FAILURE_REASON_MAP[str(_get(row, "error_code"))] == "BUDGET_EXCEEDED"
            for row in tool_calls + model_calls
            if str(_get(row, "execution_id")) == execution_id
        ) or max(tool_ratio, model_ratio, token_ratio) >= 1.0
        exceeded += int(budget_error)
        if max(tool_ratio, model_ratio, token_ratio) >= 0.8:
            near_budget.append({
                "execution_id": execution_id,
                "tool_utilization": round(tool_ratio, 4),
                "model_utilization": round(model_ratio, 4),
                "token_utilization": round(token_ratio, 4),
            })
    execution_limits = {str(_get(row, "id", "")): row for row in executions}
    for task in tasks:
        execution = execution_limits.get(str(_get(task, "execution_id", "")))
        if execution is None:
            continue
        metrics = (_get(task, "completion_payload") or {}).get("metrics", {})
        task_tool_limit = _integer(_get(execution, "max_tool_calls"), 0)
        task_model_limit = _integer(_get(execution, "max_model_calls"), 0)
        task_tool_ratio = _number(metrics.get("tool_call")) / task_tool_limit if task_tool_limit else 0.0
        task_model_ratio = _number(metrics.get("model_call")) / task_model_limit if task_model_limit else 0.0
        if max(task_tool_ratio, task_model_ratio) >= 0.8:
            near_budget_tasks.append({
                "execution_id": str(_get(task, "execution_id", "")),
                "task_id": str(_get(task, "task_id", "")),
                "tool_utilization": round(task_tool_ratio, 4),
                "model_utilization": round(task_model_ratio, 4),
            })
    return {
        "avg_tool_utilization": _avg(tool_utilization),
        "avg_model_utilization": _avg(model_utilization),
        "avg_token_utilization": _avg(token_utilization),
        "budget_exceeded_rate": _rate(exceeded, len(executions)),
        "near_budget_executions": near_budget,
        "near_budget_tasks": near_budget_tasks,
        "utilization_unit": "ratio",
    }


def _safe_ref(row: Any, *, include_tool: bool = False) -> dict[str, Any]:
    result = {
        "id": str(_get(row, "id", "")),
        "execution_id": str(_get(row, "execution_id", "")),
        "task_id": _get(row, "task_id"),
        "status": _get(row, "status"),
        "error_code": _get(row, "error_code"),
        "duration_ms": _duration_ms(row),
    }
    if include_tool:
        result["tool_name"] = _get(row, "tool_name")
    return result


def build_runtime_report(*, executions: Iterable[Any] | None = None,
                         tasks: Iterable[Any] | None = None,
                         tool_calls: Iterable[Any] | None = None,
                         model_calls: Iterable[Any] | None = None,
                         filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a privacy-safe report from durable runtime rows."""
    executions = _as_list(executions)
    tasks = _as_list(tasks)
    tool_calls = _as_list(tool_calls)
    model_calls = _as_list(model_calls)
    filters = filters or {}

    task_types = set(filters.get("task_types") or filters.get("task_type") or [])
    skill_id = filters.get("skill_id")
    if task_types:
        tasks = [row for row in tasks if str(_get(row, "task_type")) in task_types]
        task_ids = {str(_get(row, "task_id")) for row in tasks}
        execution_ids = {str(_get(row, "execution_id")) for row in tasks}
        executions = [row for row in executions if str(_get(row, "id")) in execution_ids]
        tool_calls = [row for row in tool_calls if str(_get(row, "task_id")) in task_ids]
        model_calls = [row for row in model_calls if str(_get(row, "task_id")) in task_ids]
    if skill_id:
        tasks = [row for row in tasks if str(_get(row, "skill_id")) == str(skill_id)]
        execution_ids = {str(_get(row, "execution_id")) for row in tasks}
        executions = [row for row in executions if str(_get(row, "id")) in execution_ids]
        tool_calls = [row for row in tool_calls if str(_get(row, "skill_id")) == str(skill_id)]
        model_calls = [row for row in model_calls if str(_get(row, "skill_id")) == str(skill_id)]

    duplicate = detect_duplicate_tool_calls(tool_calls)
    duplicate_ids = {call_id for item in duplicate["duplicates"] for call_id in item["duplicate_call_ids"]}
    failures: list[dict[str, Any]] = []
    for row in tool_calls:
        if not _tool_ok(row):
            failures.append({
                "reason": classify_failure(tool_call=row),
                "execution_id": str(_get(row, "execution_id", "")),
                "task_id": _get(row, "task_id"),
                "trace_id": str(_get(row, "id", "")),
                "error_code": _get(row, "error_code"),
                "tool_name": _get(row, "tool_name"),
            })
    for row in model_calls:
        if not _model_ok(row):
            failures.append({
                "reason": "UNKNOWN",
                "execution_id": str(_get(row, "execution_id", "")),
                "task_id": _get(row, "task_id"),
                "trace_id": str(_get(row, "id", "")),
                "error_code": _get(row, "error_code"),
                "tool_name": None,
            })
    for call_id in duplicate_ids:
        row = next((item for item in tool_calls if str(_get(item, "id", "")) == call_id), None)
        if row is not None:
            failures.append({
                "reason": "DUPLICATE_ACTION",
                "execution_id": str(_get(row, "execution_id", "")),
                "task_id": _get(row, "task_id"),
                "trace_id": call_id,
                "error_code": None,
                "tool_name": _get(row, "tool_name"),
            })
    for row in tasks:
        if str(_get(row, "status", "")) == "failed":
            failures.append({
                "reason": classify_failure(task=row),
                "execution_id": str(_get(row, "execution_id", "")),
                "task_id": _get(row, "task_id"),
                "trace_id": _get(row, "task_id"),
                "error_code": _get(row, "error_code"),
                "tool_name": None,
            })
    failure_distribution = Counter(item["reason"] for item in failures)

    execution_metrics = _execution_metrics(executions)
    task_metrics = _task_metrics(tasks)
    tool_metrics = _tool_metrics(tool_calls, tasks)
    model_metrics = _model_metrics(model_calls, tasks)
    budget = _budget_metrics(executions, tasks, tool_calls, model_calls)
    task_type_slices = _task_slice(tasks, "task_type")
    skill_slices = _task_usage_slice(tasks, "skill_id", tool_calls, model_calls)
    failed_tools = Counter(str(_get(row, "tool_name")) for row in tool_calls if not _tool_ok(row))
    lowest_task_type = min(
        task_type_slices.items(),
        key=lambda item: (item[1]["task_success_rate"], item[0]),
        default=None,
    )
    most_consuming_skill = max(
        skill_slices.items(),
        key=lambda item: (item[1]["tool_call_count"], item[0]),
        default=None,
    )
    most_failed_tool = failed_tools.most_common(1)[0] if failed_tools else None
    summary = {
        **execution_metrics,
        **task_metrics,
        **tool_metrics,
        **model_metrics,
        "duplicate_count": duplicate["duplicate_count"],
        "duplicate_rate": duplicate["duplicate_rate"],
        "failure_count": len(failures),
        "failure_reason_distribution": dict(sorted(failure_distribution.items())),
        "budget": budget,
        "budget_utilization": {
            "tool": budget["avg_tool_utilization"],
            "model": budget["avg_model_utilization"],
            "token": budget["avg_token_utilization"],
        },
        "lowest_task_success": {
            "task_type": lowest_task_type[0],
            "rate": lowest_task_type[1]["task_success_rate"],
        } if lowest_task_type else None,
        "most_tool_consuming_skill": {
            "skill_id": most_consuming_skill[0],
            "tool_call_count": most_consuming_skill[1]["tool_call_count"],
        } if most_consuming_skill else None,
        "tool_with_most_failures": {
            "tool_name": most_failed_tool[0],
            "failure_count": most_failed_tool[1],
        } if most_failed_tool else None,
        "execution": execution_metrics,
        "task": task_metrics,
        "tool": tool_metrics,
        "model": model_metrics,
    }
    traces = [
        {**_safe_ref(row), "kind": "model", "model": _get(row, "model"), "purpose": _get(row, "purpose"),
         "call_index": _get(row, "call_index")}
        for row in model_calls
    ] + [
        {**_safe_ref(row, include_tool=True), "kind": "tool"}
        for row in tool_calls
    ]
    return {
        "report_type": "agent_runtime",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": {
            "executions": len(executions),
            "tasks": len(tasks),
            "tool_calls": len(tool_calls),
            "model_calls": len(model_calls),
            "failure_records": len(failures),
        },
        "filters": filters,
        "summary": summary,
        "task_types": task_type_slices,
        "skills": skill_slices,
        "executors": _task_slice(tasks, "executor_type"),
        "tools": {
            name: _tool_metrics([row for row in tool_calls if str(_get(row, "tool_name")) == name], tasks)
            for name in sorted({str(_get(row, "tool_name")) for row in tool_calls})
        },
        "models": {
            name: _model_metrics([row for row in model_calls if str(_get(row, "model")) == name], tasks)
            for name in sorted({str(_get(row, "model")) for row in model_calls})
        },
        "failures": {
            "failure_reason_distribution": dict(sorted(failure_distribution.items())),
            "details": failures,
            "unknown_count": failure_distribution.get("UNKNOWN", 0),
        },
        "cases": [
            {
                "execution_id": str(_get(row, "execution_id", "")),
                "task_id": str(_get(row, "task_id", "")),
                "task_type": _get(row, "task_type"),
                "skill_id": _get(row, "skill_id"),
                "executor_type": _get(row, "executor_type"),
                "status": _get(row, "status"),
                "attempt_count": _integer(_get(row, "attempt_count"), 0),
                "completion_passed": _completion_passed(row),
                "error_code": _get(row, "error_code"),
            }
            for row in tasks
        ],
        "traces": traces,
    }
