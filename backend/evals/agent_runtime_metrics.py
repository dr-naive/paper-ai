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
KNOWN_EXECUTION_STATUSES = (
    "pending",
    "queued",
    "running",
    "waiting_user",
    "paused",
    "retrying",
    "completed",
    "partial",
    "blocked",
    "failed",
    "cancelled",
)
TERMINAL_EXECUTION_STATUSES = {"completed", "partial", "failed", "cancelled"}
MIN_TASKS_FOR_TREND = 20
MIN_TASKS_FOR_COMPARISON = 50
MOCK_DATA_MARKERS = ("mock", "test", "fixture", "fake", "dummy", "sample")
RECOMMENDED_REAL_CHAINS = [
    "READ_PAPERS：使用已索引的真实项目论文完成一次项目级阅读。",
    "WRITE_SECTION：使用真实 Evidence 生成一个章节，并完成 AUDIT_DRAFT。",
    "DISCOVER_AND_IMPORT：执行真实论文发现，经过用户确认后导入论文。",
]

# These descriptions are deliberately stored with the report.  A JSON report
# is also consumed by the dashboard and by future offline tooling, so the
# meaning of a metric must not live only in a separate document.
REPORT_DEFINITIONS = {
    "sample_size.executions": "纳入本次统计的 Execution 数量。",
    "sample_size.tasks": "这些 Execution 关联的 ResearchTask 数量。",
    "sample_size.tool_calls": "这些 Execution 关联的 ToolCall 原子工具调用数量。",
    "sample_size.model_calls": "这些 Execution 关联的 ModelCall 模型调用数量。",
    "sample_size.events": "这些 Execution 关联的 AgentEvent 生命周期事件数量。",
    "sample_size.failure_records": "报告根据失败状态、错误码和重复动作整理出的失败记录数量。",
    "collection.total_execution_count": "满足时间和其他 Execution 筛选条件的总数量。",
    "collection.selected_execution_count": "实际纳入本次统计的 Execution 数量。",
    "collection.truncated": "由于显式 limit 小于筛选范围总量而发生截断时为 true。",
    "event_metrics.event_count": "纳入统计的 AgentEvent 总数量。",
    "event_metrics.event_type_counts": "按 event_type 汇总的 AgentEvent 数量。",
    "event_metrics.event_execution_coverage": "至少有一条 AgentEvent 的 Execution 占全部 Execution 的比例。",
    "event_metrics.events_per_execution": "每个 Execution 的 AgentEvent 平均数量。",
    "summary.status_counts": "每种 Execution 状态的绝对数量；状态占比以全部 Execution 为分母。",
    "summary.completed_rate": "状态为 completed 的 Execution 占全部 Execution 的比例。",
    "summary.partial_rate": "状态为 partial 的 Execution 占全部 Execution 的比例。",
    "summary.failed_rate": "状态为 failed 的 Execution 占全部 Execution 的比例。",
    "summary.blocked_rate": "状态为 blocked 的 Execution 占全部 Execution 的比例。",
    "summary.waiting_user_rate": "等待用户输入的 Execution 占全部 Execution 的比例。",
    "summary.cancelled_rate": "状态为 cancelled 的 Execution 占全部 Execution 的比例。",
    "summary.avg_duration_ms": "Execution 从开始到结束（或最后更新时间）的平均耗时，单位为毫秒。",
    "summary.p50_duration_ms": "Execution 耗时的中位数，50% 的样本不超过该值，单位为毫秒。",
    "summary.p95_duration_ms": "Execution 耗时的 95 分位值，95% 的样本不超过该值，单位为毫秒。",
    "summary.task_success_rate": "状态为 completed 的 ResearchTask 占全部 ResearchTask 的比例。",
    "summary.retry_rate": "发生过重试的 ResearchTask 占全部 ResearchTask 的比例。",
    "summary.success_rate": "成功 ToolCall 占全部 ToolCall 的比例。",
    "summary.failure_rate": "失败、超时或未完成 ToolCall 占全部 ToolCall 的比例。",
    "summary.calls_per_task": "有工具调用记录的 Task 中，平均每个 Task 的 ToolCall 数量。",
    "summary.model_calls_per_task": "有模型调用记录的 Task（旧路径会回退到 Execution）中，平均模型调用数量。",
    "summary.model_error_rate": "失败 ModelCall 占全部 ModelCall 的比例。",
    "summary.event_count": "纳入统计的 AgentEvent 总数量。",
    "summary.duplicate_rate": "同一 Task 内连续重复成功 ToolCall 占全部 ToolCall 的比例。",
    "summary.budget": "按照 Execution/Task 已持久化计数，与配置上限计算出的预算使用情况。",
    "events.event_type_counts": "按事件类型统计的 AgentEvent 数量；不包含事件原始 payload。",
    "observability.executions_with_tasks": "至少关联一个 ResearchTask 的 Execution 数量。",
    "observability.executions_with_tool_calls": "至少关联一条 ToolCall 记录的 Execution 数量。",
    "observability.executions_with_model_calls": "至少关联一条 ModelCall 记录的 Execution 数量。",
    "observability.tool_calls_without_task_id": "没有 ResearchTask 关联的历史或即时路径 ToolCall 数量。",
    "observability.model_calls_without_task_id": "没有 ResearchTask 关联的历史或即时路径 ModelCall 数量。",
    "observability.counter_only_tool_execution_count": "Execution 累计 ToolCall 计数大于 0，但没有对应明细 ToolCall 记录的数量。",
    "observability.counter_only_model_execution_count": "Execution 累计 ModelCall 计数大于 0，但没有对应明细 ModelCall 记录的数量。",
    "diagnostic.analysis_mode": "报告展示模式；insufficient 表示样本不足，diagnostic 表示可做初步诊断。",
    "diagnostic.sample_quality": "按 Execution 类型和 ResearchTask/ToolCall/ModelCall 数量判断的样本有效性及缺失项。",
    "diagnostic.task_type_comparison": "按 task_type 聚合的诊断摘要，包含样本量、成功/失败率、平均耗时、调用量、Token 和重复率。",
    "diagnostic.failure_categories": "按现有 Failure Taxonomy 汇总的失败类别，不改变既有分类规则。",
    "diagnostic.top_failed_tools": "按失败率和超时率排序的失败/超时 ToolCall 工具。",
    "diagnostic.duplicate_tasks": "同一 ResearchTask 内重复成功 ToolCall 最集中的任务。",
    "diagnostic.resource_anomalies": "按已有 ToolCall、ModelCall 和 Token 事实识别出的资源偏高 Task/Skill。",
    "diagnostic.drilldown_targets": "按失败、阻塞、重试、重复动作和资源异常确定的最多 10 个 Execution/Task 下钻对象。",
}


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
    metrics = {
        "execution_count": count,
        "status_counts": dict(sorted(statuses.items())),
        "completed_rate": _rate(statuses["completed"], count),
        "partial_rate": _rate(statuses["partial"], count),
        "failed_rate": _rate(statuses["failed"], count),
        "blocked_rate": _rate(statuses["blocked"], count),
        "waiting_user_rate": _rate(statuses["waiting_user"], count),
        "cancelled_rate": _rate(statuses["cancelled"], count),
        "pending_rate": _rate(statuses["pending"], count),
        "queued_rate": _rate(statuses["queued"], count),
        "running_rate": _rate(statuses["running"], count),
        "retrying_rate": _rate(statuses["retrying"], count),
        "paused_rate": _rate(statuses["paused"], count),
        "active_count": sum(statuses[status] for status in KNOWN_EXECUTION_STATUSES
                             if status not in TERMINAL_EXECUTION_STATUSES),
        "terminal_count": sum(statuses[status] for status in TERMINAL_EXECUTION_STATUSES),
        "unknown_status_count": sum(count for status, count in statuses.items()
                                     if status not in KNOWN_EXECUTION_STATUSES),
        "avg_duration": _avg(durations),
        "p50_duration": percentile(durations, 0.50),
        "p95_duration": percentile(durations, 0.95),
        "avg_duration_ms": _avg(durations),
        "p50_duration_ms": percentile(durations, 0.50),
        "p95_duration_ms": percentile(durations, 0.95),
        "duration_unit": "ms",
    }
    metrics["terminal_rate"] = _rate(metrics["terminal_count"], count)
    return metrics


def _event_metrics(events: list[Any], executions: list[Any]) -> dict[str, Any]:
    execution_ids = {str(_get(row, "id", "")) for row in executions}
    event_execution_ids = {
        str(_get(row, "execution_id", "")) for row in events
        if str(_get(row, "execution_id", "")) in execution_ids
    }
    event_types = Counter(str(_get(row, "event_type", "未设置")) for row in events)
    return {
        "event_count": len(events),
        "event_type_counts": dict(sorted(event_types.items())),
        "executions_with_events": len(event_execution_ids),
        "event_execution_coverage": _rate(len(event_execution_ids), len(executions)),
        "events_per_execution": round(len(events) / len(execution_ids), 2) if execution_ids else 0.0,
    }


def _execution_slice(executions: list[Any], key: str) -> dict[str, Any]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for execution in executions:
        grouped[str(_get(execution, key) or "未设置")].append(execution)
    return {name: _execution_metrics(rows) for name, rows in sorted(grouped.items())}


def _observability_coverage(executions: list[Any], tasks: list[Any],
                            tool_calls: list[Any], model_calls: list[Any],
                            events: list[Any]) -> dict[str, Any]:
    execution_ids = {str(_get(row, "id", "")) for row in executions}

    def execution_ids_from(rows: list[Any]) -> set[str]:
        return {
            str(_get(row, "execution_id", "")) for row in rows
            if str(_get(row, "execution_id", "")) in execution_ids
        }

    task_execution_ids = execution_ids_from(tasks)
    tool_execution_ids = execution_ids_from(tool_calls)
    model_execution_ids = execution_ids_from(model_calls)
    event_execution_ids = execution_ids_from(events)
    observed_tools_by_execution = Counter(str(_get(row, "execution_id", "")) for row in tool_calls)
    observed_models_by_execution = Counter(str(_get(row, "execution_id", "")) for row in model_calls)

    tool_counter_total = sum(_integer(_get(row, "tool_call_count"), 0) for row in executions)
    model_counter_total = sum(_integer(_get(row, "model_call_count"), 0) for row in executions)
    input_token_counter_total = sum(_integer(_get(row, "input_tokens"), 0) for row in executions)
    output_token_counter_total = sum(_integer(_get(row, "output_tokens"), 0) for row in executions)
    observed_input_tokens = sum(_integer(_get(row, "input_tokens"), 0) for row in model_calls)
    observed_output_tokens = sum(_integer(_get(row, "output_tokens"), 0) for row in model_calls)

    counter_only_tools = sum(
        _integer(_get(row, "tool_call_count"), 0) > 0
        and observed_tools_by_execution[str(_get(row, "id", ""))] == 0
        for row in executions
    )
    counter_only_models = sum(
        _integer(_get(row, "model_call_count"), 0) > 0
        and observed_models_by_execution[str(_get(row, "id", ""))] == 0
        for row in executions
    )
    return {
        "execution_count": len(executions),
        "executions_with_events": len(event_execution_ids),
        "executions_with_tasks": len(task_execution_ids),
        "executions_with_tool_calls": len(tool_execution_ids),
        "executions_with_model_calls": len(model_execution_ids),
        "event_execution_coverage": _rate(len(event_execution_ids), len(executions)),
        "task_execution_coverage": _rate(len(task_execution_ids), len(executions)),
        "tool_execution_coverage": _rate(len(tool_execution_ids), len(executions)),
        "model_execution_coverage": _rate(len(model_execution_ids), len(executions)),
        "tool_calls_with_task_id": sum(bool(_get(row, "task_id")) for row in tool_calls),
        "tool_calls_without_task_id": sum(not bool(_get(row, "task_id")) for row in tool_calls),
        "model_calls_with_task_id": sum(bool(_get(row, "task_id")) for row in model_calls),
        "model_calls_without_task_id": sum(not bool(_get(row, "task_id")) for row in model_calls),
        "execution_counter_tool_calls": tool_counter_total,
        "observed_tool_calls": len(tool_calls),
        "execution_counter_model_calls": model_counter_total,
        "observed_model_calls": len(model_calls),
        "execution_counter_input_tokens": input_token_counter_total,
        "observed_input_tokens": observed_input_tokens,
        "execution_counter_output_tokens": output_token_counter_total,
        "observed_output_tokens": observed_output_tokens,
        "counter_only_tool_execution_count": counter_only_tools,
        "counter_only_model_execution_count": counter_only_models,
        "coverage_unit": "ratio",
    }


def _execution_cases(executions: list[Any], tasks: list[Any],
                     tool_calls: list[Any], model_calls: list[Any],
                     events: list[Any]) -> list[dict[str, Any]]:
    task_counts = Counter(str(_get(row, "execution_id", "")) for row in tasks)
    tool_counts = Counter(str(_get(row, "execution_id", "")) for row in tool_calls)
    model_counts = Counter(str(_get(row, "execution_id", "")) for row in model_calls)
    event_counts = Counter(str(_get(row, "execution_id", "")) for row in events)
    rows = sorted(executions, key=lambda row: _sort_datetime(_get(row, "created_at")), reverse=True)
    return [
        {
            "execution_id": str(_get(row, "id", "")),
            "status": _get(row, "status"),
            "agent_type": _get(row, "agent_type"),
            "runtime_version": _get(row, "runtime_version"),
            "project_id": _get(row, "project_id"),
            "created_at": _get(row, "created_at"),
            "started_at": _get(row, "started_at"),
            "completed_at": _get(row, "completed_at"),
            "duration_ms": _duration_ms(row),
            "task_count": task_counts[str(_get(row, "id", ""))],
            "tool_call_count": tool_counts[str(_get(row, "id", ""))],
            "model_call_count": model_counts[str(_get(row, "id", ""))],
            "event_count": event_counts[str(_get(row, "id", ""))],
            "counter_tool_call_count": _integer(_get(row, "tool_call_count"), 0),
            "counter_model_call_count": _integer(_get(row, "model_call_count"), 0),
            "input_tokens": _integer(_get(row, "input_tokens"), 0),
            "output_tokens": _integer(_get(row, "output_tokens"), 0),
            "error_code": _get(row, "error_code"),
        }
        for row in rows
    ]


def _is_mock_value(value: Any) -> bool:
    normalized = str(value or "").lower()
    return any(marker in normalized for marker in MOCK_DATA_MARKERS)


def _sample_quality(executions: list[Any], tasks: list[Any],
                    tool_calls: list[Any], model_calls: list[Any]) -> dict[str, Any]:
    execution_count = len(executions)
    execution_by_id = {str(_get(row, "id", "")): row for row in executions}
    mock_execution_ids = {
        execution_id for execution_id, row in execution_by_id.items()
        if _is_mock_value(_get(row, "agent_type"))
    }
    real_execution_ids = set(execution_by_id) - mock_execution_ids

    def count_for_execution(rows: list[Any], execution_ids: set[str]) -> int:
        return sum(str(_get(row, "execution_id", "")) in execution_ids for row in rows)

    type_counts = Counter(str(_get(row, "agent_type") or "未设置") for row in executions)
    samples_by_agent_type = [
        {
            "agent_type": name,
            "sample_size": count,
            "classification": "疑似 Mock/测试" if _is_mock_value(name) else "非 Mock（需结合业务确认）",
        }
        for name, count in sorted(type_counts.items())
    ]
    mock_task_count = count_for_execution(tasks, mock_execution_ids)
    real_task_count = count_for_execution(tasks, real_execution_ids)
    mock_tool_count = count_for_execution(tool_calls, mock_execution_ids)
    real_tool_count = count_for_execution(tool_calls, real_execution_ids)
    mock_model_count = count_for_execution(model_calls, mock_execution_ids)
    real_model_count = count_for_execution(model_calls, real_execution_ids)

    reasons: list[str] = []
    all_mock = bool(execution_by_id) and mock_execution_ids == set(execution_by_id)
    if execution_count == 0:
        level = "no_data"
        label = "没有可分析样本"
        analysis_mode = "insufficient"
        reasons.append("NO_EXECUTIONS")
    else:
        if all_mock:
            reasons.append("MOCK_ONLY")
        if not tasks:
            reasons.append("NO_RESEARCH_TASKS")
        if not tool_calls:
            reasons.append("NO_TOOL_CALLS")
        if not model_calls:
            reasons.append("NO_MODEL_CALLS")
        if tasks and len(tasks) < MIN_TASKS_FOR_TREND:
            reasons.append("TASK_SAMPLE_BELOW_TREND_THRESHOLD")

        if all_mock:
            level = "debug_only"
            label = "仅有 Mock/测试样本，仅供调试"
            analysis_mode = "insufficient"
        elif reasons:
            level = "debug_only"
            label = "样本不足，仅供调试"
            analysis_mode = "insufficient"
        elif len(tasks) <= MIN_TASKS_FOR_COMPARISON:
            level = "early_trend"
            label = "可观察初步趋势"
            analysis_mode = "diagnostic"
        else:
            level = "comparison_ready"
            label = "可开始做 task_type / tool / failure 对比"
            analysis_mode = "diagnostic"

    if execution_count and not mock_execution_ids:
        real_sample_label = "当前样本未命中 Mock/测试标记；仍需确认是否为真实业务流量"
    elif real_execution_ids:
        real_sample_label = "同时存在非 Mock 样本"
    else:
        real_sample_label = "当前没有可识别的非 Mock 样本"
    return {
        "analysis_mode": analysis_mode,
        "level": level,
        "label": label,
        "reason_codes": reasons,
        "execution_count": execution_count,
        "task_count": len(tasks),
        "tool_call_count": len(tool_calls),
        "model_call_count": len(model_calls),
        "mock_execution_count": len(mock_execution_ids),
        "real_execution_count": len(real_execution_ids),
        "mock_task_count": mock_task_count,
        "real_task_count": real_task_count,
        "mock_tool_call_count": mock_tool_count,
        "real_tool_call_count": real_tool_count,
        "mock_model_call_count": mock_model_count,
        "real_model_call_count": real_model_count,
        "real_sample_label": real_sample_label,
        "samples_by_agent_type": samples_by_agent_type,
        "thresholds": {
            "min_tasks_for_trend": MIN_TASKS_FOR_TREND,
            "min_tasks_for_comparison": MIN_TASKS_FOR_COMPARISON,
        },
        "recommended_real_chains": RECOMMENDED_REAL_CHAINS,
    }


def _task_observation_rows(tasks: list[Any], tool_calls: list[Any],
                           model_calls: list[Any], duplicate: dict[str, Any]) -> list[dict[str, Any]]:
    tool_counts = Counter(str(_get(row, "task_id", "")) for row in tool_calls)
    model_counts = Counter(str(_get(row, "task_id", "")) for row in model_calls)
    input_tokens = Counter()
    output_tokens = Counter()
    for row in model_calls:
        task_id = str(_get(row, "task_id", ""))
        input_tokens[task_id] += _integer(_get(row, "input_tokens"), 0)
        output_tokens[task_id] += _integer(_get(row, "output_tokens"), 0)
    duplicate_counts = Counter()
    duplicate_tools: dict[str, Counter[str]] = defaultdict(Counter)
    for item in duplicate.get("duplicates", []):
        task_id = str(item.get("task_id") or "")
        count = len(item.get("duplicate_call_ids") or [])
        duplicate_counts[task_id] += count
        duplicate_tools[task_id][str(item.get("tool_name") or "未设置")] += count

    rows = []
    for task in tasks:
        task_id = str(_get(task, "task_id", ""))
        tool_count = tool_counts[task_id]
        model_count = model_counts[task_id]
        token_count = input_tokens[task_id] + output_tokens[task_id]
        rows.append({
            "task_id": task_id,
            "execution_id": str(_get(task, "execution_id", "")),
            "task_type": _get(task, "task_type") or "未设置",
            "skill_id": _get(task, "skill_id") or "未设置",
            "executor_type": _get(task, "executor_type") or "未设置",
            "status": _get(task, "status") or "未设置",
            "attempt_count": _integer(_get(task, "attempt_count"), 0),
            "duration_ms": _duration_ms(task),
            "tool_calls": tool_count,
            "model_calls": model_count,
            "tokens": token_count if model_count else None,
            "duplicate_count": duplicate_counts[task_id],
            "duplicate_rate": _rate(duplicate_counts[task_id], tool_count) if tool_count else None,
            "repeated_tools": dict(sorted(duplicate_tools[task_id].items())),
            "error_code": _get(task, "error_code"),
        })
    return rows


def _task_type_comparison(task_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        grouped[str(row["task_type"])].append(row)

    result = []
    for task_type, rows in sorted(grouped.items()):
        sample_size = len(rows)
        tool_count = sum(row["tool_calls"] for row in rows)
        model_count = sum(row["model_calls"] for row in rows)
        duplicate_count = sum(row["duplicate_count"] for row in rows)
        token_values = [row["tokens"] for row in rows if row["tokens"] is not None]
        duration_values = [row["duration_ms"] for row in rows if row["duration_ms"] is not None]
        result.append({
            "task_type": task_type,
            "sample_size": sample_size,
            "success_rate": _rate(sum(row["status"] == "completed" for row in rows), sample_size),
            "failure_rate": _rate(sum(row["status"] == "failed" for row in rows), sample_size),
            "avg_duration": _avg(duration_values) if duration_values else None,
            "avg_tool_calls": round(tool_count / sample_size, 2) if sample_size else None,
            "avg_model_calls": round(model_count / sample_size, 2) if sample_size else None,
            "avg_tokens": _avg(token_values) if token_values else None,
            "duplicate_rate": _rate(duplicate_count, tool_count) if tool_count else None,
        })
    return result


def _resource_groups(task_rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        grouped[str(row.get(key) or "未设置")].append(row)
    result = []
    for name, rows in sorted(grouped.items()):
        token_values = [row["tokens"] for row in rows if row["tokens"] is not None]
        result.append({
            "name": name,
            "sample_size": len(rows),
            "avg_tool_calls": _avg(row["tool_calls"] for row in rows),
            "avg_model_calls": _avg(row["model_calls"] for row in rows),
            "avg_tokens": _avg(token_values) if token_values else None,
            "total_tool_calls": sum(row["tool_calls"] for row in rows),
            "total_model_calls": sum(row["model_calls"] for row in rows),
            "total_tokens": sum(token_values),
        })
    return result


def _top_resource_groups(groups: list[dict[str, Any]], key: str, limit: int = 5) -> list[dict[str, Any]]:
    return sorted(
        groups,
        key=lambda row: (
            row.get(key) is not None,
            float(row.get(key)) if row.get(key) is not None else -1.0,
            row["name"],
        ),
        reverse=True,
    )[:limit]


def _tool_diagnostic_rows(tool_calls: list[Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in tool_calls:
        grouped[str(_get(row, "tool_name") or "未设置")].append(row)
    result = []
    for name, rows in sorted(grouped.items()):
        count = len(rows)
        failures = sum(not _tool_ok(row) for row in rows)
        timeouts = sum(str(_get(row, "error_code") or "") == "TOOL_TIMEOUT" for row in rows)
        latencies = [value for row in rows if (value := _duration_ms(row)) is not None]
        result.append({
            "tool_name": name,
            "sample_size": count,
            "failure_count": failures,
            "failure_rate": _rate(failures, count),
            "timeout_count": timeouts,
            "timeout_rate": _rate(timeouts, count),
            "avg_latency_ms": _avg(latencies) if latencies else None,
        })
    return result


def _resource_anomalies(task_rows: list[dict[str, Any]]) -> dict[str, Any]:
    task_type_groups = _resource_groups(task_rows, "task_type")
    skill_groups = _resource_groups(task_rows, "skill_id")
    average_tool_calls = _avg(row["tool_calls"] for row in task_rows)
    average_model_calls = _avg(row["model_calls"] for row in task_rows)
    token_values = [row["tokens"] for row in task_rows if row["tokens"] is not None]
    average_tokens = _avg(token_values) if token_values else None
    heavy_tasks = []
    for row in task_rows:
        signals = []
        if average_tool_calls and row["tool_calls"] >= max(2, average_tool_calls * 1.5):
            signals.append("Tool 调用偏高")
        if average_model_calls and row["model_calls"] >= max(2, average_model_calls * 1.5):
            signals.append("Model 调用偏高")
        if average_tokens and row["tokens"] is not None and row["tokens"] >= max(average_tokens * 1.5, average_tokens + 1):
            signals.append("Token 偏高")
        if row["duplicate_count"]:
            signals.append("存在重复 ToolCall")
        score = (
            (row["tool_calls"] / average_tool_calls if average_tool_calls else 0)
            + (row["model_calls"] / average_model_calls if average_model_calls else 0)
            + (row["tokens"] / average_tokens if average_tokens and row["tokens"] is not None else 0)
            + row["duplicate_count"] * 2
        )
        if signals:
            heavy_tasks.append({
                "task_id": row["task_id"],
                "execution_id": row["execution_id"],
                "task_type": row["task_type"],
                "skill_id": row["skill_id"],
                "tool_calls": row["tool_calls"],
                "model_calls": row["model_calls"],
                "tokens": row["tokens"],
                "duplicate_count": row["duplicate_count"],
                "signals": signals,
                "priority_score": round(score, 4),
            })
    return {
        "task_types": {
            "highest_avg_tool_calls": _top_resource_groups(task_type_groups, "avg_tool_calls"),
            "highest_avg_model_calls": _top_resource_groups(task_type_groups, "avg_model_calls"),
            "highest_avg_tokens": _top_resource_groups(task_type_groups, "avg_tokens"),
        },
        "skills": {
            "highest_avg_tool_calls": _top_resource_groups(skill_groups, "avg_tool_calls"),
            "highest_avg_model_calls": _top_resource_groups(skill_groups, "avg_model_calls"),
            "highest_avg_tokens": _top_resource_groups(skill_groups, "avg_tokens"),
        },
        "resource_heavy_tasks": sorted(
            heavy_tasks,
            key=lambda row: (row["priority_score"], row["task_id"]),
            reverse=True,
        )[:10],
        "baseline": {
            "avg_tool_calls": average_tool_calls if task_rows else None,
            "avg_model_calls": average_model_calls if task_rows else None,
            "avg_tokens": average_tokens,
        },
    }


def _top_drilldown_targets(execution_cases: list[dict[str, Any]], task_rows: list[dict[str, Any]],
                           failures: list[dict[str, Any]]) -> dict[str, Any]:
    failures_by_execution = Counter(str(row.get("execution_id") or "") for row in failures)
    duplicate_execution_ids = {str(row["execution_id"]) for row in task_rows if row["duplicate_count"]}
    execution_targets = []
    status_weight = {
        "failed": 100,
        "blocked": 90,
        "waiting_user": 80,
        "partial": 70,
        "cancelled": 50,
        "retrying": 40,
    }
    for row in execution_cases:
        execution_id = str(row["execution_id"])
        reasons = []
        score = status_weight.get(str(row.get("status")), 0)
        if row.get("status") in status_weight:
            reasons.append(f"Execution 状态为 {row.get('status')}")
        if failures_by_execution[execution_id]:
            score += 40
            reasons.append(f"有 {failures_by_execution[execution_id]} 条失败记录")
        if execution_id in duplicate_execution_ids:
            score += 30
            reasons.append("包含重复 ToolCall 的任务")
        if row.get("counter_tool_call_count", 0) > row.get("tool_call_count", 0):
            score += 20
            reasons.append("累计工具计数高于明细记录")
        if row.get("counter_model_call_count", 0) > row.get("model_call_count", 0):
            score += 20
            reasons.append("累计模型计数高于明细记录")
        execution_targets.append({
            "execution_id": execution_id,
            "status": row.get("status"),
            "agent_type": row.get("agent_type"),
            "task_count": row.get("task_count", 0),
            "event_count": row.get("event_count", 0),
            "duration_ms": row.get("duration_ms"),
            "reasons": reasons or ["常规抽查"],
            "priority_score": score,
        })

    task_targets = []
    for row in task_rows:
        reasons = []
        score = 0
        if row["status"] in {"failed", "blocked", "waiting_user", "partial", "retrying"}:
            score += 100
            reasons.append(f"Task 状态为 {row['status']}")
        if row["attempt_count"] > 1:
            score += 30
            reasons.append(f"已尝试 {row['attempt_count']} 次")
        if row["duplicate_count"]:
            score += 40
            reasons.append(f"有 {row['duplicate_count']} 次重复 ToolCall")
        if row["tool_calls"] >= 2:
            score += row["tool_calls"]
        if row["model_calls"] >= 2:
            score += row["model_calls"]
        task_targets.append({
            "task_id": row["task_id"],
            "execution_id": row["execution_id"],
            "task_type": row["task_type"],
            "skill_id": row["skill_id"],
            "status": row["status"],
            "attempt_count": row["attempt_count"],
            "tool_calls": row["tool_calls"],
            "model_calls": row["model_calls"],
            "tokens": row["tokens"],
            "duplicate_count": row["duplicate_count"],
            "reasons": reasons or ["常规抽查"],
            "priority_score": score,
        })
    return {
        "executions": sorted(
            execution_targets,
            key=lambda row: (row["priority_score"], row["execution_id"]),
            reverse=True,
        )[:10],
        "tasks": sorted(
            task_targets,
            key=lambda row: (row["priority_score"], row["task_id"]),
            reverse=True,
        )[:10],
    }


def _diagnostic_issue_list(sample_quality: dict[str, Any], task_comparison: list[dict[str, Any]],
                            failure_categories: list[dict[str, Any]], tool_rows: list[dict[str, Any]],
                            duplicate_tasks: list[dict[str, Any]], resource: dict[str, Any]) -> list[dict[str, Any]]:
    if sample_quality["analysis_mode"] != "diagnostic":
        return []
    candidates: list[dict[str, Any]] = []
    if task_comparison:
        worst = min(task_comparison, key=lambda row: (row["success_rate"], -row["failure_rate"], row["task_type"]))
        candidates.append({
            "category": "task_type",
            "title": f"{worst['task_type']} 表现最差",
            "evidence": f"样本 {worst['sample_size']}，成功率 {worst['success_rate']:.2%}，失败率 {worst['failure_rate']:.2%}。",
            "target": worst["task_type"],
        })
    if failure_categories:
        failure = failure_categories[0]
        candidates.append({
            "category": "failure_category",
            "title": f"失败主要集中在 {failure['category']}",
            "evidence": f"共 {failure['count']} 条，占失败记录 {failure['rate']:.2%}。",
            "target": failure["category"],
        })
    failed_tools = [row for row in tool_rows if row["failure_count"] or row["timeout_count"]]
    if failed_tools:
        tool = sorted(failed_tools, key=lambda row: (row["failure_rate"], row["timeout_rate"], row["sample_size"]), reverse=True)[0]
        candidates.append({
            "category": "tool",
            "title": f"工具 {tool['tool_name']} 失败/超时最多",
            "evidence": f"调用 {tool['sample_size']} 次，失败 {tool['failure_count']} 次，超时 {tool['timeout_count']} 次。",
            "target": tool["tool_name"],
        })
    elif duplicate_tasks:
        duplicate = duplicate_tasks[0]
        candidates.append({
            "category": "duplicate",
            "title": f"Task {duplicate['task_id']} 重复 ToolCall 最严重",
            "evidence": f"重复 {duplicate['duplicate_count']} 次，占该 Task 工具调用 {duplicate['duplicate_rate']:.2%}。",
            "target": duplicate["task_id"],
        })
    elif resource.get("resource_heavy_tasks"):
        heavy = resource["resource_heavy_tasks"][0]
        candidates.append({
            "category": "resource",
            "title": f"Task {heavy['task_id']} 资源使用偏高",
            "evidence": "、".join(heavy["signals"]),
            "target": heavy["task_id"],
        })
    return candidates[:3]


def _build_diagnostics(executions: list[Any], tasks: list[Any], tool_calls: list[Any],
                       model_calls: list[Any], events: list[Any], duplicate: dict[str, Any],
                       failures: list[dict[str, Any]], execution_cases: list[dict[str, Any]]) -> dict[str, Any]:
    sample_quality = _sample_quality(executions, tasks, tool_calls, model_calls)
    task_rows = _task_observation_rows(tasks, tool_calls, model_calls, duplicate)
    task_comparison = _task_type_comparison(task_rows)
    failure_counter = Counter(row["reason"] for row in failures)
    failure_categories = [
        {"category": name, "count": count, "rate": _rate(count, len(failures))}
        for name, count in failure_counter.most_common()
    ]
    tool_rows = _tool_diagnostic_rows(tool_calls)
    top_failed_tools = sorted(
        [row for row in tool_rows if row["failure_count"] or row["timeout_count"]],
        key=lambda row: (row["failure_rate"], row["timeout_rate"], row["sample_size"], row["tool_name"]),
        reverse=True,
    )[:5]
    duplicate_by_task = Counter()
    duplicate_tools_by_task: dict[str, Counter[str]] = defaultdict(Counter)
    for item in duplicate.get("duplicates", []):
        task_id = str(item.get("task_id") or "")
        count = len(item.get("duplicate_call_ids") or [])
        duplicate_by_task[task_id] += count
        duplicate_tools_by_task[task_id][str(item.get("tool_name") or "未设置")] += count
    tool_counts_by_task = Counter(str(_get(row, "task_id", "")) for row in tool_calls)
    task_lookup = {row["task_id"]: row for row in task_rows}
    duplicate_tasks = []
    for task_id, count in duplicate_by_task.items():
        task = task_lookup.get(task_id, {})
        total_tools = tool_counts_by_task[task_id]
        duplicate_tasks.append({
            "task_id": task_id,
            "execution_id": task.get("execution_id"),
            "task_type": task.get("task_type"),
            "skill_id": task.get("skill_id"),
            "duplicate_count": count,
            "sample_size": total_tools,
            "duplicate_rate": _rate(count, total_tools) if total_tools else None,
            "repeated_tools": dict(sorted(duplicate_tools_by_task[task_id].items())),
        })
    duplicate_tasks.sort(key=lambda row: (row["duplicate_rate"] is not None, row["duplicate_rate"] or -1, row["duplicate_count"], row["task_id"]), reverse=True)
    resource = _resource_anomalies(task_rows)
    execution_cases = execution_cases or _execution_cases(executions, tasks, tool_calls, model_calls, events)
    drilldown = _top_drilldown_targets(execution_cases, task_rows, failures)
    return {
        "analysis_mode": sample_quality["analysis_mode"],
        "sample_quality": sample_quality,
        "top_issues": _diagnostic_issue_list(sample_quality, task_comparison, failure_categories, top_failed_tools, duplicate_tasks, resource),
        "task_type_comparison": task_comparison,
        "failure_categories": failure_categories[:5],
        "top_failed_tools": top_failed_tools,
        "duplicate_tasks": duplicate_tasks[:10],
        "resource_anomalies": resource,
        "drilldown_targets": drilldown,
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
                         events: Iterable[Any] | None = None,
                         filters: dict[str, Any] | None = None,
                         collection: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a privacy-safe report from durable runtime rows."""
    executions = _as_list(executions)
    tasks = _as_list(tasks)
    tool_calls = _as_list(tool_calls)
    model_calls = _as_list(model_calls)
    events = _as_list(events)
    filters = filters or {}
    collection = dict(collection or {})
    collection.setdefault("total_execution_count", len(executions))
    collection.setdefault("selected_execution_count", len(executions))
    collection.setdefault("truncated", False)

    task_types = set(filters.get("task_types") or filters.get("task_type") or [])
    skill_id = filters.get("skill_id")
    if task_types:
        tasks = [row for row in tasks if str(_get(row, "task_type")) in task_types]
        task_ids = {str(_get(row, "task_id")) for row in tasks}
        execution_ids = {str(_get(row, "execution_id")) for row in tasks}
        executions = [row for row in executions if str(_get(row, "id")) in execution_ids]
        tool_calls = [row for row in tool_calls if str(_get(row, "task_id")) in task_ids]
        model_calls = [row for row in model_calls if str(_get(row, "task_id")) in task_ids]
        events = [row for row in events if str(_get(row, "execution_id")) in execution_ids]
    if skill_id:
        tasks = [row for row in tasks if str(_get(row, "skill_id")) == str(skill_id)]
        execution_ids = {str(_get(row, "execution_id")) for row in tasks}
        executions = [row for row in executions if str(_get(row, "id")) in execution_ids]
        tool_calls = [row for row in tool_calls if str(_get(row, "skill_id")) == str(skill_id)]
        model_calls = [row for row in model_calls if str(_get(row, "skill_id")) == str(skill_id)]
        events = [row for row in events if str(_get(row, "execution_id")) in execution_ids]

    duplicate = detect_duplicate_tool_calls(tool_calls)
    duplicate_ids = {call_id for item in duplicate["duplicates"] for call_id in item["duplicate_call_ids"]}
    failures: list[dict[str, Any]] = []
    for row in tool_calls:
        if not _tool_ok(row):
            failures.append({
                "scope": "tool",
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
                "scope": "model",
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
                "scope": "tool",
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
                "scope": "task",
                "reason": classify_failure(task=row),
                "execution_id": str(_get(row, "execution_id", "")),
                "task_id": _get(row, "task_id"),
                "trace_id": _get(row, "task_id"),
                "error_code": _get(row, "error_code"),
                "tool_name": None,
            })
    for row in executions:
        if str(_get(row, "status", "")) == "failed":
            error_code = str(_get(row, "error_code") or "")
            failures.append({
                "scope": "execution",
                "reason": FAILURE_REASON_MAP.get(error_code, "EXECUTION_FAILED"),
                "execution_id": str(_get(row, "id", "")),
                "task_id": None,
                "trace_id": str(_get(row, "id", "")),
                "error_code": _get(row, "error_code"),
                "tool_name": None,
            })
    failure_distribution = Counter(item["reason"] for item in failures)

    execution_metrics = _execution_metrics(executions)
    task_metrics = _task_metrics(tasks)
    tool_metrics = _tool_metrics(tool_calls, tasks)
    model_metrics = _model_metrics(model_calls, tasks)
    event_metrics = _event_metrics(events, executions)
    observability = _observability_coverage(executions, tasks, tool_calls, model_calls, events)
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
    execution_cases = _execution_cases(executions, tasks, tool_calls, model_calls, events)
    diagnostics = _build_diagnostics(
        executions, tasks, tool_calls, model_calls, events, duplicate, failures,
        execution_cases,
    )
    summary = {
        **execution_metrics,
        **task_metrics,
        **tool_metrics,
        **model_metrics,
        "duplicate_count": duplicate["duplicate_count"],
        "duplicate_rate": duplicate["duplicate_rate"],
        "failure_count": len(failures),
        "failure_reason_distribution": dict(sorted(failure_distribution.items())),
        "event_count": event_metrics["event_count"],
        "status_counts": execution_metrics["status_counts"],
        "observability": observability,
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
        "events": event_metrics,
    }
    traces = [
        {**_safe_ref(row), "kind": "model", "model": _get(row, "model"), "purpose": _get(row, "purpose"),
         "call_index": _get(row, "call_index")}
        for row in model_calls
    ] + [
        {**_safe_ref(row, include_tool=True), "kind": "tool"}
        for row in tool_calls
    ] + [
        {
            "id": str(_get(row, "id", "")),
            "execution_id": str(_get(row, "execution_id", "")),
            "kind": "event",
            "seq": _get(row, "seq"),
            "event_type": _get(row, "event_type"),
            "stage": _get(row, "stage"),
            "created_at": _get(row, "created_at"),
        }
        for row in events
    ]
    return {
        "report_type": "agent_runtime",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "storage": "PostgreSQL",
            "tables": ["agent_executions", "research_tasks", "tool_calls", "model_calls", "agent_events"],
            "calculation": "deterministic",
            "prompt_or_reasoning_included": False,
            "provider_payload_included": False,
        },
        "collection": collection,
        "sample_size": {
            "executions": len(executions),
            "tasks": len(tasks),
            "tool_calls": len(tool_calls),
            "model_calls": len(model_calls),
            "events": len(events),
            "failure_records": len(failures),
        },
        "filters": filters,
        "summary": summary,
        "observability": observability,
        "event_metrics": event_metrics,
        "execution_types": _execution_slice(executions, "agent_type"),
        "runtime_versions": _execution_slice(executions, "runtime_version"),
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
        "diagnostic": diagnostics,
        "definitions": REPORT_DEFINITIONS,
        "execution_cases": execution_cases,
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
