"""Render the Agent Runtime report as a diagnosis-first Chinese Markdown file.

The JSON report keeps the complete deterministic metric set for offline
analysis.  This renderer deliberately shows only the evidence needed to make
an optimization decision.  It also refuses to manufacture a trend when the
persisted sample is empty, mock-only, or too small.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any


STATUS_LABELS = {
    "pending": "等待调度",
    "queued": "已入队",
    "running": "执行中",
    "waiting_user": "等待用户",
    "paused": "已暂停",
    "retrying": "重试中",
    "completed": "已完成",
    "partial": "部分完成",
    "blocked": "已阻塞",
    "failed": "失败",
    "cancelled": "已取消",
}

REASON_LABELS = {
    "NO_EXECUTIONS": "没有可分析的 Execution 样本。",
    "MOCK_ONLY": "现有 Execution 全部命中 Mock/测试标记，不能代表真实 Agent 链路。",
    "NO_RESEARCH_TASKS": "没有 ResearchTask，无法比较任务成功率、重试和任务级资源消耗。",
    "NO_TOOL_CALLS": "没有 ToolCall 明细，无法判断工具失败、超时和重复调用。",
    "NO_MODEL_CALLS": "没有 ModelCall 明细，无法判断模型调用和 Token 消耗。",
    "TASK_SAMPLE_BELOW_TREND_THRESHOLD": "ResearchTask 少于 20 个，暂时不能稳定观察趋势。",
}


def _escape(value: Any) -> str:
    text = "暂无数据" if value is None or value == "" else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "暂无数据"
    try:
        formatted = f"{float(value):.{digits}f}"
        return formatted if digits == 0 else formatted.rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return _escape(value)


def _ratio_percentage(value: Any) -> str:
    """Format a persisted ratio without converting missing data to zero."""
    if value is None:
        return "暂无数据"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "暂无数据"


def _rate_percentage(value: Any, denominator: Any) -> str:
    if value is None or denominator in (None, 0):
        return "暂无数据"
    return _ratio_percentage(value)


def _count(value: Any) -> str:
    """Show a known count while preserving an absent count as unknown."""
    return "暂无数据" if value is None else _number(value, 0)


def _length(mapping: dict[str, Any], key: str) -> int | None:
    value = mapping.get(key)
    return len(value) if isinstance(value, (list, tuple, set, dict)) else None


def _date(value: Any) -> str:
    if value is None:
        return "暂无数据"
    return str(value).replace("T", " ").replace("+00:00", " UTC")


def _table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    headers = list(headers)
    materialized = list(rows)
    if not materialized:
        return "暂无可比较数据。"
    lines = [
        "| " + " | ".join(_escape(item) for item in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(_escape(item) for item in row) + " |"
        for row in materialized
    )
    return "\n".join(lines)


def _quality_fallback(report: dict[str, Any]) -> dict[str, Any]:
    """Keep old JSON reports readable when they predate ``diagnostic``."""
    sample = report.get("sample_size") or {}
    execution_types = report.get("execution_types") or {}
    type_names = list(execution_types)
    mock_type_names = [
        name for name in type_names
        if any(marker in str(name).lower() for marker in ("mock", "test", "fixture", "fake", "dummy", "sample"))
    ]
    all_mock = bool(type_names) and len(mock_type_names) == len(type_names)
    execution_count = sample.get("executions")
    task_count = sample.get("tasks")
    tool_count = sample.get("tool_calls")
    model_count = sample.get("model_calls")
    if execution_count in (None, 0):
        label = "没有可分析样本"
        reasons = ["NO_EXECUTIONS"]
    elif all_mock:
        label = "仅有 Mock/测试样本，仅供调试"
        reasons = ["MOCK_ONLY"]
    elif not task_count:
        label = "没有 ResearchTask，仅供调试"
        reasons = ["NO_RESEARCH_TASKS"]
    elif not tool_count:
        label = "没有 ToolCall 明细，仅供调试"
        reasons = ["NO_TOOL_CALLS"]
    elif not model_count:
        label = "没有 ModelCall 明细，仅供调试"
        reasons = ["NO_MODEL_CALLS"]
    elif task_count < 20:
        label = "样本不足，仅供调试"
        reasons = ["TASK_SAMPLE_BELOW_TREND_THRESHOLD"]
    else:
        label = "可观察初步趋势"
        reasons = []
    return {
        "analysis_mode": "insufficient" if all_mock or task_count is None or task_count <= 50 else "diagnostic",
        "level": "debug_only",
        "label": label,
        "reason_codes": reasons,
        "execution_count": execution_count,
        "task_count": task_count,
        "tool_call_count": tool_count,
        "model_call_count": model_count,
        "mock_execution_count": execution_count if all_mock else None,
        "real_execution_count": 0 if all_mock else None,
        "mock_task_count": task_count if all_mock else None,
        "real_task_count": 0 if all_mock else None,
        "mock_tool_call_count": tool_count if all_mock else None,
        "real_tool_call_count": 0 if all_mock else None,
        "mock_model_call_count": model_count if all_mock else None,
        "real_model_call_count": 0 if all_mock else None,
        "real_sample_label": "旧报告未保存样本真实性分类。" if not all_mock else "旧报告的 Execution 类型全部命中 Mock/测试标记。",
        "samples_by_agent_type": [
            {
                "agent_type": name,
                "sample_size": (
                    (execution_types.get(name) or {}).get("execution_count")
                    if isinstance(execution_types.get(name), dict) else None
                ),
                "classification": "疑似 Mock/测试" if name in mock_type_names else "非 Mock（需结合业务确认）",
            }
            for name in type_names
        ],
        "thresholds": {"min_tasks_for_trend": 20, "min_tasks_for_comparison": 50},
        "recommended_real_chains": [
            "READ_PAPERS：使用已索引的真实项目论文完成一次项目级阅读。",
            "WRITE_SECTION：使用真实 Evidence 生成一个章节，并完成 AUDIT_DRAFT。",
            "DISCOVER_AND_IMPORT：执行真实论文发现，经过用户确认后导入论文。",
        ],
    }


def _diagnostic_context(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    diagnostic = report.get("diagnostic") or {}
    quality = diagnostic.get("sample_quality") or _quality_fallback(report)
    mode = diagnostic.get("analysis_mode") or quality.get("analysis_mode") or "insufficient"
    return diagnostic, quality, mode


def _sample_rows(report: dict[str, Any], quality: dict[str, Any]) -> list[list[Any]]:
    sample = report.get("sample_size") or {}
    return [
        ["Execution", _count(sample.get("executions")), "一次目标或兼容执行生命周期"],
        ["ResearchTask", _count(sample.get("tasks")), "一个可独立执行、可重试的业务任务"],
        ["ToolCall", _count(sample.get("tool_calls")), "一次原子工具调用"],
        ["ModelCall", _count(sample.get("model_calls")), "一次模型调用事实"],
        ["AgentEvent", _count(sample.get("events")), "生命周期事件；不是 Agent 行为样本"],
        ["疑似 Mock/测试 Execution", _count(quality.get("mock_execution_count")), "按 agent_type 标记识别"],
        ["非 Mock Execution", _count(quality.get("real_execution_count")), "未命中 Mock 标记，仍需业务确认"],
    ]


def _quality_reasons(quality: dict[str, Any]) -> list[str]:
    reasons = quality.get("reason_codes") or []
    lines = [REASON_LABELS.get(str(reason), str(reason)) for reason in reasons]
    if quality.get("real_sample_label"):
        lines.append(str(quality["real_sample_label"]))
    if not lines:
        lines.append("当前样本满足基本数量条件，可继续查看下方诊断结论。")
    return lines


def _render_insufficient(report: dict[str, Any], quality: dict[str, Any]) -> str:
    collection = report.get("collection") or {}
    by_type = quality.get("samples_by_agent_type") or []
    type_rows = [
        [row.get("agent_type"), row.get("sample_size"), row.get("classification")]
        for row in by_type
    ]
    if not type_rows:
        type_rows = [["暂无可识别 agent_type", "暂无数据", "无法分类"]]
    chain_rows = [[index, chain] for index, chain in enumerate(
        quality.get("recommended_real_chains") or [], start=1
    )]
    thresholds = quality.get("thresholds") or {}
    lines = [
        "# PaperAI Agent 运行诊断报告",
        "",
        f"> 生成时间：{_date(report.get('generated_at'))}",
        "> 数据来源：PostgreSQL 持久化运行记录；本报告不包含提示词、思维链或第三方原始响应。",
        "",
        "## 1. 样本有效性",
        "",
        f"**{_escape(quality.get('label'))}**。当前只判断样本是否足以分析，不把缺失观测解释成 0。",
        "",
        _table(["数据对象", "样本量", "代表什么"], _sample_rows(report, quality)),
        "",
        f"样本时间范围：{_date(collection.get('oldest_created_at'))} → {_date(collection.get('newest_created_at'))}。",
        "",
        "## 2. 当前为什么无法评价真实 Agent",
        "",
    ]
    lines.extend(f"- {line}" for line in _quality_reasons(quality))
    lines.extend([
        "",
        "## 3. 当前有哪些真实/Mock 样本",
        "",
        "> “非 Mock”只表示没有命中名称标记，不等同于已经完成真实线上流量验证。",
        "",
        _table(["agent_type", "Execution 样本", "分类"], type_rows),
        "",
        _table(
            ["数据对象", "疑似 Mock/测试", "未命中 Mock 标记"],
            [
                ["Execution", quality.get("mock_execution_count"), quality.get("real_execution_count")],
                ["ResearchTask", quality.get("mock_task_count"), quality.get("real_task_count")],
                ["ToolCall", quality.get("mock_tool_call_count"), quality.get("real_tool_call_count")],
                ["ModelCall", quality.get("mock_model_call_count"), quality.get("real_model_call_count")],
            ],
        ),
        "",
        "## 4. 建议先运行的真实链路",
        "",
        _table(["优先级", "建议链路"], chain_rows),
        "",
        "## 5. 至少需要多少 ResearchTask 后再看趋势",
        "",
        _table(
            ["ResearchTask 数量", "可得结论"],
            [
                [f"<{thresholds.get('min_tasks_for_trend', 20)}", "样本不足，仅供调试"],
                [
                    f"{thresholds.get('min_tasks_for_trend', 20)}–{thresholds.get('min_tasks_for_comparison', 50)}",
                    "可观察初步趋势",
                ],
                [f">{thresholds.get('min_tasks_for_comparison', 50)}", "可开始做 task_type / tool / failure 对比"],
            ],
        ),
        "",
        "> 详细原始指标、失败记录和 trace 仍保留在同名 JSON 报告中；当前 Markdown 只保留样本质量判断和下一步建议。",
    ])
    return "\n".join(lines) + "\n"


def _render_issue_rows(issues: list[dict[str, Any]]) -> list[list[Any]]:
    return [
        [index, issue.get("title"), issue.get("evidence"), issue.get("target")]
        for index, issue in enumerate(issues[:3], start=1)
    ]


def _resource_rows(resource_groups: dict[str, Any], dimension: str) -> list[list[Any]]:
    metric_labels = {
        "highest_avg_tool_calls": "平均 ToolCall 偏高",
        "highest_avg_model_calls": "平均 ModelCall 偏高",
        "highest_avg_tokens": "平均 Token 偏高",
    }
    grouped: dict[str, dict[str, Any]] = {}
    for metric_key, metric_label in metric_labels.items():
        for row in (resource_groups.get(metric_key) or [])[:3]:
            name = str(row.get("name") or "未设置")
            current = grouped.setdefault(name, {"row": row, "signals": []})
            if metric_label not in current["signals"]:
                current["signals"].append(metric_label)
    return [
        [
            dimension, item["row"].get("name"), item["row"].get("sample_size"),
            item["row"].get("avg_tool_calls"), item["row"].get("avg_model_calls"),
            _number(item["row"].get("avg_tokens")), "、".join(item["signals"]),
        ]
        for item in grouped.values()
    ]


def _render_normal(report: dict[str, Any], diagnostic: dict[str, Any], quality: dict[str, Any]) -> str:
    sample = report.get("sample_size") or {}
    collection = report.get("collection") or {}
    summary = report.get("summary") or {}
    issues = diagnostic.get("top_issues") or []
    task_rows = diagnostic.get("task_type_comparison") or []
    failure_rows = diagnostic.get("failure_categories") or []
    tool_rows = diagnostic.get("top_failed_tools") or []
    duplicate_rows = diagnostic.get("duplicate_tasks") or []
    resource = diagnostic.get("resource_anomalies") or {}
    task_resources = resource.get("task_types") or {}
    skill_resources = resource.get("skills") or {}
    budget = summary.get("budget") or {}
    drilldown = diagnostic.get("drilldown_targets") or {}

    lines = [
        "# PaperAI Agent 运行诊断报告",
        "",
        f"> 生成时间：{_date(report.get('generated_at'))}",
        "> 数据来源：PostgreSQL 持久化运行记录；结论由确定性聚合生成。",
        "",
        "## 1. 样本有效性",
        "",
        f"**{_escape(quality.get('label'))}**。真实/非 Mock 样本仍需结合业务流量确认。",
        "",
        _table(
            ["数据对象", "样本量", "说明"],
            [
                ["Execution", _count(sample.get("executions")), "目标生命周期"],
                ["ResearchTask", _count(sample.get("tasks")), "业务执行单元"],
                ["ToolCall", _count(sample.get("tool_calls")), "原子工具调用"],
                ["ModelCall", _count(sample.get("model_calls")), "模型调用事实"],
            ],
        ),
        "",
        f"样本时间范围：{_date(collection.get('oldest_created_at'))} → {_date(collection.get('newest_created_at'))}；",
        f"疑似 Mock/测试 Execution：{_count(quality.get('mock_execution_count'))}，未命中 Mock 标记：{_count(quality.get('real_execution_count'))}。",
        "",
        "## 2. 当前最严重的 3 个问题",
        "",
        _table(["优先级", "问题", "证据", "优先检查对象"], _render_issue_rows(issues))
        if issues else "当前样本未识别出明确的前三项问题；这不等于系统没有问题。",
        "",
        "## 3. Task 类型对比",
        "",
        _table(
            [
                "task_type", "sample_size", "success_rate", "failure_rate", "avg_duration",
                "avg_tool_calls", "avg_model_calls", "avg_tokens", "duplicate_rate",
            ],
            [
                [
                    row.get("task_type"), row.get("sample_size"),
                    _rate_percentage(row.get("success_rate"), row.get("sample_size")),
                    _rate_percentage(row.get("failure_rate"), row.get("sample_size")),
                    f"{_number(row.get('avg_duration'))} ms" if row.get("avg_duration") is not None else "暂无数据",
                    _number(row.get("avg_tool_calls")), _number(row.get("avg_model_calls")),
                    _number(row.get("avg_tokens")),
                    _rate_percentage(row.get("duplicate_rate"), row.get("sample_size")),
                ]
                for row in task_rows
            ],
        ),
        "",
        "## 4. Top Failure / Top Failed Tool / Duplicate",
        "",
        "### Failure Category",
        "",
        _table(
            ["Failure Category", "count", "failure_records 占比"],
            [[row.get("category"), row.get("count"), _ratio_percentage(row.get("rate"))] for row in failure_rows],
        ),
        "",
        "### Top Failed Tool",
        "",
        _table(
            ["tool_name", "sample_size", "failure_count", "failure_rate", "timeout_count", "timeout_rate"],
            [
                [
                    row.get("tool_name"), row.get("sample_size"), row.get("failure_count"),
                    _ratio_percentage(row.get("failure_rate")), row.get("timeout_count"),
                    _ratio_percentage(row.get("timeout_rate")),
                ]
                for row in tool_rows
            ],
        ),
        "",
        "### Duplicate ToolCall 最严重的 Task",
        "",
        _table(
            ["task_id", "execution_id", "task_type", "duplicate_count", "duplicate_rate", "repeated_tools"],
            [
                [
                    row.get("task_id"), row.get("execution_id"), row.get("task_type"),
                    row.get("duplicate_count"), _ratio_percentage(row.get("duplicate_rate")),
                    row.get("repeated_tools"),
                ]
                for row in duplicate_rows
            ],
        ),
        "",
        "## 5. 资源与 Budget 异常",
        "",
        "### Task / Skill 资源偏高",
        "",
        _table(
            ["维度", "名称", "样本", "平均 ToolCall", "平均 ModelCall", "平均 Token", "偏高指标"],
            _resource_rows(task_resources, "Task 类型") + _resource_rows(skill_resources, "Skill"),
        ),
        "",
        "### 资源异常 Task",
        "",
        _table(
            ["task_id", "execution_id", "task_type", "skill_id", "ToolCall", "ModelCall", "Token", "异常信号"],
            [
                [
                    row.get("task_id"), row.get("execution_id"), row.get("task_type"), row.get("skill_id"),
                    row.get("tool_calls"), row.get("model_calls"), _number(row.get("tokens")), "、".join(row.get("signals") or []),
                ]
                for row in (resource.get("resource_heavy_tasks") or [])
            ],
        ),
        "",
        "### Budget",
        "",
        _table(
            ["异常对象", "数量/状态", "说明"],
            [
                ["接近预算的 Execution", _length(budget, "near_budget_executions"), "任一已配置预算使用率达到 80%"],
                ["接近预算的 Task", _length(budget, "near_budget_tasks"), "Task 级已记录计数达到 80%"],
                ["预算超限率", _ratio_percentage(budget.get("budget_exceeded_rate")), "至少一个已配置预算达到或超过上限"],
            ],
        ),
        "",
        "## 6. 值得下钻的 Execution / Task",
        "",
        "### Execution",
        "",
        _table(
            ["execution_id", "status", "agent_type", "task_count", "优先检查原因"],
            [
                [row.get("execution_id"), STATUS_LABELS.get(str(row.get("status")), row.get("status")), row.get("agent_type"), row.get("task_count"), "；".join(row.get("reasons") or [])]
                for row in (drilldown.get("executions") or [])
            ],
        ),
        "",
        "### ResearchTask",
        "",
        _table(
            ["task_id", "execution_id", "task_type", "skill_id", "status", "attempt_count", "ToolCall", "ModelCall", "优先检查原因"],
            [
                [
                    row.get("task_id"), row.get("execution_id"), row.get("task_type"), row.get("skill_id"),
                    STATUS_LABELS.get(str(row.get("status")), row.get("status")), row.get("attempt_count"),
                    row.get("tool_calls"), row.get("model_calls"), "；".join(row.get("reasons") or []),
                ]
                for row in (drilldown.get("tasks") or [])
            ],
        ),
        "",
        "> 完整原始指标和 trace 仍保留在同名 JSON；Markdown 只保留用于优化决策的摘要。",
    ]
    return "\n".join(lines) + "\n"


def render_runtime_report_markdown(report: dict[str, Any]) -> str:
    """Render the report without exposing prompts, reasoning, or payloads."""
    diagnostic, quality, mode = _diagnostic_context(report)
    if mode != "diagnostic":
        return _render_insufficient(report, quality)
    return _render_normal(report, diagnostic, quality)
