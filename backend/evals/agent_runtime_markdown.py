"""Render the deterministic Agent Runtime report as a human-readable Chinese Markdown file."""
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

STATUS_MEANINGS = {
    "pending": "尚未进入队列或等待前置条件。",
    "queued": "已经进入队列，等待 Worker 执行。",
    "running": "当前正在执行。",
    "waiting_user": "需要用户补充输入后才能继续。",
    "paused": "被用户或系统暂停，尚未结束。",
    "retrying": "本次执行失败后仍有可用重试次数。",
    "completed": "完成条件全部通过。",
    "partial": "部分产物已经完成，但整体目标尚未完全满足。",
    "blocked": "缺少硬依赖或被确定性规则阻塞。",
    "failed": "执行失败且不能继续自动恢复。",
    "cancelled": "被用户或系统取消。",
}


def _escape(value: Any) -> str:
    text = "暂无数据" if value is None or value == "" else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "暂无数据"
    try:
        return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return _escape(value)


def _percentage(value: Any, denominator: int | float | None) -> str:
    if not denominator:
        return "暂无数据"
    try:
        return f"{float(value or 0) * 100:.2f}%"
    except (TypeError, ValueError):
        return "暂无数据"


def _date(value: Any) -> str:
    if value is None:
        return "暂无数据"
    return str(value).replace("T", " ").replace("+00:00", " UTC")


def _table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    headers = list(headers)
    lines = [
        "| " + " | ".join(_escape(item) for item in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_escape(item) for item in row) + " |" for row in rows)
    return "\n".join(lines) if len(lines) > 2 else "暂无数据。"


def _conclusions(report: dict[str, Any]) -> list[str]:
    sample = report.get("sample_size") or {}
    summary = report.get("summary") or {}
    collection = report.get("collection") or {}
    observations: list[str] = []
    execution_count = int(sample.get("executions") or 0)

    if execution_count == 0:
        observations.append("当前筛选范围没有 Execution，不能对系统运行质量下结论。")
        return observations
    if collection.get("truncated"):
        observations.append(
            f"报告被 limit 截断：只读取 {collection.get('selected_execution_count', execution_count)} 条，"
            f"数据库筛选范围共有 {collection.get('total_execution_count', '未知')} 条 Execution。"
        )
    if not sample.get("tasks"):
        observations.append("当前样本没有 ResearchTask，无法评价任务成功率、重试、Task DAG 和任务级预算。")
    if not sample.get("tool_calls"):
        observations.append("当前样本没有 ToolCall 明细，无法评价工具成功率、超时、失败和重复动作。")
    if not sample.get("model_calls"):
        observations.append("当前样本没有 ModelCall 明细，无法评价模型延迟、Token 和模型错误率。")
    execution_types = list((report.get("execution_types") or {}).keys())
    if execution_types and all("mock" in item.lower() for item in execution_types):
        observations.append("当前样本的 Execution 类型全部是 mock 运行类型，不能直接代表真实用户流量或真实模型服务质量。")
    cancelled = (summary.get("status_counts") or {}).get("cancelled", 0)
    if cancelled:
        observations.append(f"发现 {cancelled} 条已取消 Execution，占比 {_percentage(summary.get('cancelled_rate'), execution_count)}，需要结合取消原因判断是否异常。")
    failed = (summary.get("status_counts") or {}).get("failed", 0)
    if failed:
        observations.append(f"发现 {failed} 条失败 Execution，占比 {_percentage(summary.get('failed_rate'), execution_count)}，请查看失败分类和 Execution 明细。")
    blocked = (summary.get("status_counts") or {}).get("blocked", 0)
    if blocked:
        observations.append(f"发现 {blocked} 条被阻塞的 Execution，占比 {_percentage(summary.get('blocked_rate'), execution_count)}，不能将其计入完成。")
    unknown_status = summary.get("unknown_status_count", 0)
    if unknown_status:
        observations.append(f"发现 {unknown_status} 条未知状态记录，说明状态枚举或历史兼容映射仍需检查。")
    coverage = report.get("observability") or {}
    if coverage.get("counter_only_tool_execution_count") or coverage.get("counter_only_model_execution_count"):
        observations.append("部分 Execution 只有累计调用计数，没有对应的明细追踪记录，观测覆盖不完整。")
    if not observations:
        observations.append("当前样本具备 Execution、Task、ToolCall 和 ModelCall 明细，可以继续查看下方分项指标。")
    return observations


def render_runtime_report_markdown(report: dict[str, Any]) -> str:
    """Render report JSON without exposing prompts, reasoning or provider payloads."""
    sample = report.get("sample_size") or {}
    summary = report.get("summary") or {}
    execution = summary.get("execution") or summary
    task = summary.get("task") or {}
    tool = summary.get("tool") or {}
    model = summary.get("model") or {}
    events = report.get("event_metrics") or summary.get("events") or {}
    coverage = report.get("observability") or summary.get("observability") or {}
    collection = report.get("collection") or {}
    execution_count = int(sample.get("executions") or 0)
    task_count = int(sample.get("tasks") or 0)
    tool_count = int(sample.get("tool_calls") or 0)
    model_count = int(sample.get("model_calls") or 0)
    total_execution_count = int(collection.get("total_execution_count") or execution_count or 0)
    selected_execution_count = int(collection.get("selected_execution_count") or execution_count or 0)
    execution_coverage = (
        _percentage(selected_execution_count / total_execution_count, total_execution_count)
        if total_execution_count else "暂无数据"
    )

    lines = [
        "# PaperAI Agent 运行观测报告",
        "",
        f"> 生成时间：{_date(report.get('generated_at'))}",
        "> 本报告由 PostgreSQL 中的持久化运行记录确定性聚合生成，不包含完整提示词、思维链或第三方原始响应。",
        "",
        "## 一、先看结论",
        "",
    ]
    lines.extend(f"- {item}" for item in _conclusions(report))
    lines.extend([
        "",
        "## 二、数据范围与覆盖情况",
        "",
        _table(
            ["数据对象", "本次样本量", "含义", "覆盖情况"],
            [
                    ["Execution", sample.get("executions", 0), "一个用户目标或一次兼容执行生命周期", execution_coverage],
                ["AgentEvent", sample.get("events", 0), "Execution 的排队、开始、阶段和结束事件", _percentage(events.get("event_execution_coverage"), execution_count)],
                ["ResearchTask", sample.get("tasks", 0), "一个可独立执行、可重试的业务任务", _percentage(coverage.get("task_execution_coverage"), execution_count)],
                ["ToolCall", sample.get("tool_calls", 0), "一次原子工具调用", _percentage(coverage.get("tool_execution_coverage"), execution_count)],
                ["ModelCall", sample.get("model_calls", 0), "一次无提示词内容的模型调用事实", _percentage(coverage.get("model_execution_coverage"), execution_count)],
                ["失败记录", sample.get("failure_records", 0), "从错误码、失败状态和重复动作整理出的记录", "—"],
            ],
        ),
        "",
        _table(
            ["采集项", "值", "说明"],
            [
                ["数据库筛选范围", collection.get("total_execution_count", execution_count), "满足 since 等 Execution 筛选条件的总量"],
                ["实际纳入统计", collection.get("selected_execution_count", execution_count), "真正参与本报告计算的 Execution 数量"],
                ["最早 Execution", _date(collection.get("oldest_created_at")), "纳入样本中最早的 created_at"],
                ["最晚 Execution", _date(collection.get("newest_created_at")), "纳入样本中最晚的 created_at"],
                ["是否被截断", "是" if collection.get("truncated") else "否", "limit 大于 0 且小于筛选范围总量时为是"],
                ["筛选条件", report.get("filters") or {}, "limit、since、task_type、skill_id 等过滤条件"],
            ],
        ),
        "",
        "## 三、Execution 状态",
        "",
    ])

    status_rows = []
    status_counts = execution.get("status_counts") or {}
    status_rate_keys = {
        status: f"{status}_rate" for status in status_counts
    }
    for status in list(STATUS_LABELS) + [key for key in status_counts if key not in STATUS_LABELS]:
        if status not in status_counts and not execution_count:
            continue
        status_count = status_counts.get(status, 0)
        status_rows.append([
            STATUS_LABELS.get(status, status),
            status_count,
            _percentage(
                execution.get(status_rate_keys.get(status))
                if status_rate_keys.get(status) in execution
                else (status_count / execution_count if execution_count else None),
                execution_count,
            ),
            STATUS_MEANINGS.get(status, "历史状态或当前代码未定义的状态。"),
        ])
    lines.extend([
        _table(["状态", "数量", "占比", "含义"], status_rows),
        "",
        _table(
            ["指标", "数值", "指标含义"],
            [
                ["完成率", _percentage(execution.get("completed_rate"), execution_count), "最终状态为 completed 的 Execution 比例"],
                ["部分完成率", _percentage(execution.get("partial_rate"), execution_count), "最终状态为 partial 的 Execution 比例"],
                ["失败率", _percentage(execution.get("failed_rate"), execution_count), "最终状态为 failed 的 Execution 比例"],
                ["阻塞率", _percentage(execution.get("blocked_rate"), execution_count), "最终状态为 blocked 的 Execution 比例"],
                ["取消率", _percentage(execution.get("cancelled_rate"), execution_count), "最终状态为 cancelled 的 Execution 比例"],
                ["平均耗时", f"{_number(execution.get('avg_duration_ms'))} 毫秒" if execution_count else "暂无数据", "所有可计算 Execution 耗时的平均值"],
                ["P50 耗时", f"{_number(execution.get('p50_duration_ms'))} 毫秒" if execution_count else "暂无数据", "一半样本不超过的耗时"],
                ["P95 耗时", f"{_number(execution.get('p95_duration_ms'))} 毫秒" if execution_count else "暂无数据", "95% 样本不超过的耗时"],
            ],
        ),
        "",
        "## 四、ResearchTask 指标",
        "",
        _table(
            ["指标", "数值", "指标含义"],
            [
                ["任务数", task.get("task_count", task_count), "纳入统计的 ResearchTask 数量"],
                ["任务完成率", _percentage(task.get("task_success_rate"), task_count), "完成任务数 / 任务总数"],
                ["任务部分完成率", _percentage(task.get("task_partial_rate"), task_count), "部分完成任务数 / 任务总数"],
                ["任务失败率", _percentage(task.get("task_failure_rate"), task_count), "失败任务数 / 任务总数"],
                ["任务重试率", _percentage(task.get("retry_rate"), task_count), "发生过重试的任务数 / 任务总数"],
                ["平均尝试次数", _number(task.get("avg_attempt_count")) if task_count else "暂无数据", "每个任务的 attempt_count 平均值"],
            ],
        ),
        "",
        "## 五、ToolCall 指标",
        "",
        _table(
            ["指标", "数值", "指标含义"],
            [
                ["工具调用数", tool.get("tool_call_count", tool_count), "原子工具调用总数"],
                ["成功率", _percentage(tool.get("success_rate"), tool_count), "成功工具调用 / 全部工具调用"],
                ["失败率", _percentage(tool.get("failure_rate"), tool_count), "失败、超时或未完成工具调用 / 全部工具调用"],
                ["超时率", _percentage(tool.get("timeout_rate"), tool_count), "错误码为 TOOL_TIMEOUT 的调用比例"],
                ["参数错误率", _percentage(tool.get("input_invalid_rate"), tool_count), "错误码为 TOOL_INPUT_INVALID 的调用比例"],
                ["平均耗时", f"{_number(tool.get('avg_latency_ms'))} 毫秒" if tool_count else "暂无数据", "工具调用完成耗时平均值"],
                ["平均调用数/任务", _number(tool.get("calls_per_task")) if tool_count else "暂无数据", "有工具记录的任务中，平均每个任务调用数"],
            ],
        ),
        "",
        "## 六、ModelCall 指标",
        "",
        _table(
            ["指标", "数值", "指标含义"],
            [
                ["模型调用数", model.get("model_call_count", model_count), "模型调用事实记录总数"],
                ["模型错误率", _percentage(model.get("model_error_rate"), model_count), "失败模型调用 / 全部模型调用"],
                ["平均调用数/任务", _number(model.get("model_calls_per_task")) if model_count else "暂无数据", "有模型记录的任务或兼容 Execution 的平均调用数"],
                ["平均输入 Token/任务", _number(model.get("avg_input_tokens_per_task")) if model_count else "暂无数据", "每个任务平均输入 Token 数"],
                ["平均输出 Token/任务", _number(model.get("avg_output_tokens_per_task")) if model_count else "暂无数据", "每个任务平均输出 Token 数"],
                ["平均耗时", f"{_number(model.get('avg_latency_ms'))} 毫秒" if model_count else "暂无数据", "模型调用耗时平均值"],
            ],
        ),
        "",
        "## 七、执行类型与调用切片",
        "",
        "### Execution 类型",
        "",
        _table(
            ["类型", "Execution 数", "完成率", "取消率", "平均耗时（毫秒）"],
            [
                [name, metrics.get("execution_count", 0),
                 _percentage(metrics.get("completed_rate"), metrics.get("execution_count")),
                 _percentage(metrics.get("cancelled_rate"), metrics.get("execution_count")),
                 _number(metrics.get("avg_duration_ms"))]
                for name, metrics in sorted((report.get("execution_types") or {}).items())
            ],
        ),
        "",
        "### Runtime 版本",
        "",
        _table(
            ["版本", "Execution 数", "完成率", "失败率", "取消率"],
            [
                [name, metrics.get("execution_count", 0),
                 _percentage(metrics.get("completed_rate"), metrics.get("execution_count")),
                 _percentage(metrics.get("failed_rate"), metrics.get("execution_count")),
                 _percentage(metrics.get("cancelled_rate"), metrics.get("execution_count"))]
                for name, metrics in sorted((report.get("runtime_versions") or {}).items())
            ],
        ),
        "",
        "### Task 类型、Skill 与执行器",
        "",
        _table(
            ["切片", "名称", "Task 数", "完成率", "重试率", "ToolCall", "ModelCall"],
            [
                ["Task 类型", name, metrics.get("task_count", 0),
                 _percentage(metrics.get("task_success_rate"), metrics.get("task_count")),
                 _percentage(metrics.get("retry_rate"), metrics.get("task_count")), "—", "—"]
                for name, metrics in sorted((report.get("task_types") or {}).items())
            ] + [
                ["Skill", name, metrics.get("task_count", 0),
                 _percentage(metrics.get("task_success_rate"), metrics.get("task_count")),
                 _percentage(metrics.get("retry_rate"), metrics.get("task_count")),
                 metrics.get("tool_call_count", 0), metrics.get("model_call_count", 0)]
                for name, metrics in sorted((report.get("skills") or {}).items())
            ] + [
                ["执行器", name, metrics.get("task_count", 0),
                 _percentage(metrics.get("task_success_rate"), metrics.get("task_count")),
                 _percentage(metrics.get("retry_rate"), metrics.get("task_count")), "—", "—"]
                for name, metrics in sorted((report.get("executors") or {}).items())
            ],
        ),
        "",
        "### Tool 与 Model",
        "",
        _table(
            ["类别", "名称", "调用数", "成功/错误率", "平均耗时（毫秒）"],
            [
                ["Tool", name, metrics.get("tool_call_count", 0),
                 _percentage(metrics.get("success_rate"), metrics.get("tool_call_count")),
                 _number(metrics.get("avg_latency_ms"))]
                for name, metrics in sorted((report.get("tools") or {}).items())
            ] + [
                ["Model", name, metrics.get("model_call_count", 0),
                 _percentage(metrics.get("model_error_rate"), metrics.get("model_call_count")),
                 _number(metrics.get("avg_latency_ms"))]
                for name, metrics in sorted((report.get("models") or {}).items())
            ],
        ),
        "",
        "## 八、事件、预算与失败",
        "",
        "### 事件类型",
        "",
        _table(
            ["事件类型", "数量", "含义"],
            [
                [name, count, "持久化的 Execution 生命周期或阶段事件"]
                for name, count in sorted((events.get("event_type_counts") or {}).items())
            ],
        ),
        "",
        _table(
            ["指标", "数值", "指标含义"],
            [
                ["事件数", events.get("event_count", sample.get("events", 0)), "AgentEvent 总数"],
                ["平均事件数/Execution", _number(events.get("events_per_execution")) if execution_count else "暂无数据", "每个 Execution 的事件平均数量"],
                ["重复成功工具调用数", summary.get("duplicate_count", 0), "同一任务内连续重复成功的工具调用数量"],
                ["重复调用率", _percentage(summary.get("duplicate_rate"), tool_count), "重复成功工具调用 / 工具调用总数"],
                ["失败记录数", summary.get("failure_count", sample.get("failure_records", 0)), "失败分类明细的总数量"],
                ["工具预算平均使用率", _percentage((summary.get("budget") or {}).get("avg_tool_utilization"), execution_count), "实际工具调用数 / 工具调用上限的平均比例"],
                ["模型预算平均使用率", _percentage((summary.get("budget") or {}).get("avg_model_utilization"), execution_count), "实际模型调用数 / 模型调用上限的平均比例"],
                ["Token 预算平均使用率", _percentage((summary.get("budget") or {}).get("avg_token_utilization"), execution_count), "实际 Token / Token 上限的平均比例"],
            ],
        ),
        "",
        "### 失败分类",
        "",
        _table(
            ["分类", "数量"],
            (report.get("failures") or {}).get("failure_reason_distribution", {}).items(),
        ),
        "",
        "## 九、观测覆盖诊断",
        "",
        _table(
            ["指标", "数值", "含义"],
            [
                ["有事件的 Execution", coverage.get("executions_with_events", 0), "至少有一条 AgentEvent 的 Execution"],
                ["有任务的 Execution", coverage.get("executions_with_tasks", 0), "至少有一条 ResearchTask 的 Execution"],
                ["有工具明细的 Execution", coverage.get("executions_with_tool_calls", 0), "至少有一条 ToolCall 的 Execution"],
                ["有模型明细的 Execution", coverage.get("executions_with_model_calls", 0), "至少有一条 ModelCall 的 Execution"],
                ["无 Task 关联的 ToolCall", coverage.get("tool_calls_without_task_id", 0), "历史即时路径或尚未关联任务的工具调用"],
                ["无 Task 关联的 ModelCall", coverage.get("model_calls_without_task_id", 0), "历史即时路径或尚未关联任务的模型调用"],
                ["只有累计工具计数的 Execution", coverage.get("counter_only_tool_execution_count", 0), "Execution 计数大于 0，但没有 ToolCall 明细"],
                ["只有累计模型计数的 Execution", coverage.get("counter_only_model_execution_count", 0), "Execution 计数大于 0，但没有 ModelCall 明细"],
            ],
        ),
        "",
        "## 十、Execution 明细",
        "",
        _table(
            ["Execution", "状态", "类型", "版本", "Task", "事件", "Tool 明细/累计", "Model 明细/累计", "耗时（毫秒）"],
            [
                [
                    item.get("execution_id"),
                    STATUS_LABELS.get(item.get("status"), item.get("status")),
                    item.get("agent_type"),
                    item.get("runtime_version"),
                    item.get("task_count", 0),
                    item.get("event_count", 0),
                    f"{item.get('tool_call_count', 0)}/{item.get('counter_tool_call_count', 0)}",
                    f"{item.get('model_call_count', 0)}/{item.get('counter_model_call_count', 0)}",
                    _number(item.get("duration_ms")),
                ]
                for item in report.get("execution_cases", [])
            ],
        ),
        "",
        "## 十一、ResearchTask 明细",
        "",
        _table(
            ["Task", "类型", "状态", "执行器", "Skill", "尝试次数", "完成条件", "错误码"],
            [
                [
                    item.get("task_id"), item.get("task_type"),
                    STATUS_LABELS.get(item.get("status"), item.get("status")),
                    item.get("executor_type"), item.get("skill_id"),
                    item.get("attempt_count", 0),
                    "通过" if item.get("completion_passed") else "未通过",
                    item.get("error_code"),
                ]
                for item in report.get("cases", [])
            ],
        ),
        "",
        "## 十二、指标说明",
        "",
    ])

    definitions = report.get("definitions") or {}
    lines.append(_table(["字段", "说明"], sorted(definitions.items())))
    lines.extend([
        "",
        "## 十三、报告限制",
        "",
        "- 这是运行事实报告，不评价回答内容的学术质量，也不使用大模型进行二次打分。",
        "- 没有对应样本的比例指标显示为“暂无数据”，不能解读为 0%。",
        "- 旧的即时 Reader/Chat 路径可能只有 Execution 累计计数，没有任务级 ToolCall/ModelCall 明细；需要结合“观测覆盖诊断”判断。",
        "- P50/P95 在样本量很小时只适合趋势参考，不适合作为稳定性能基线。",
        "",
    ])
    return "\n".join(lines)
