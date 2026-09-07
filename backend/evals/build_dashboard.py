from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


RUN_LABELS = {
    "retrieval_dev_baseline": "Dev 初始基线",
    "retrieval_dev_after_frontmatter": "Dev 修复后",
    "retrieval_test_gold": "Gold 封闭测试",
    "retrieval_test_regression_after_fix": "Test 修复后回归",
}


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 2)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)


def load_agent_runtime_report(reports_dir: Path, report_path: Path | None = None) -> dict[str, Any] | None:
    """Load the newest internal Agent Runtime report when one is available."""
    candidate = report_path
    if candidate is None:
        reports = sorted(reports_dir.glob("agent_runtime_*.json"))
        candidate = reports[-1] if reports else None
    if candidate is None or not candidate.exists():
        return None
    report = json.loads(candidate.read_text(encoding="utf-8"))
    report["source_file"] = candidate.name
    return report


def load_dashboard_data(reports_dir: Path, dataset_path: Path,
                        agent_runtime_report: Path | None = None) -> dict[str, Any]:
    dataset = {
        row["id"]: row
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and (row := json.loads(line))
    }
    runs = []
    for report_path in sorted(reports_dir.glob("retrieval_*.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        cases = []
        latencies = []
        for item in report.get("cases", []):
            case_id = item.get("case", {}).get("id")
            gold = dataset.get(case_id, {})
            latency = float(item.get("latency_ms") or 0)
            latencies.append(latency)
            cases.append({
                **item,
                "gold": {
                    "reference_answer": gold.get("reference_answer", ""),
                    "reference_claims": gold.get("reference_claims", []),
                    "evidence": gold.get("evidence", []),
                    "annotation_status": gold.get("annotation_status", ""),
                },
            })
        stem = report_path.stem
        runs.append({
            "id": stem,
            "label": RUN_LABELS.get(stem, stem.replace("_", " ")),
            "file": report_path.name,
            "generated_at": report.get("generated_at"),
            "configuration": report.get("configuration", {}),
            "summary": report.get("summary", {}),
            "slices": report.get("slices", {}),
            "latency": {
                "p50_ms": percentile(latencies, 0.50),
                "p95_ms": percentile(latencies, 0.95),
            },
            "cases": cases,
        })
    if not runs:
        raise ValueError(f"{reports_dir} 中没有 retrieval_*.json 报告")
    e2e_path = reports_dir / "e2e_test_scored.json"
    e2e = json.loads(e2e_path.read_text(encoding="utf-8")) if e2e_path.exists() else None
    return {
        "dataset": {
            "path": str(dataset_path),
            "total": len(dataset),
            "verified": sum(row.get("annotation_status") == "verified" for row in dataset.values()),
            "silver": sum(row.get("annotation_status") == "silver" for row in dataset.values()),
            "draft": sum(row.get("annotation_status") == "draft" for row in dataset.values()),
        },
        "runs": runs,
        "e2e": e2e,
        "agent_runtime": load_agent_runtime_report(reports_dir, agent_runtime_report),
    }


def render_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PaperAI 评测面板</title>
  <style>
    :root {{
      --bg: #f7f5f2; --surface: #fff; --surface-soft: #f2eee9;
      --ink: #29231f; --text: #514942; --muted: #766d66; --border: #ddd5cd;
      --brand: #b94709; --brand-soft: #f8e9df; --success: #287a4b;
      --success-soft: #e6f4eb; --danger: #b33131; --danger-soft: #fae9e7;
      --warning: #966213; --warning-soft: #fbf1d9;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
    button, select {{ font: inherit; }}
    .shell {{ width: min(1440px, calc(100% - 40px)); margin: 0 auto; padding: 28px 0 60px; }}
    .topbar {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 22px; }}
    h1 {{ margin: 0 0 5px; font-size: 25px; letter-spacing: -.02em; }}
    .subtitle {{ margin: 0; color: var(--muted); }}
    .run-select {{ min-width: 230px; padding: 9px 34px 9px 11px; border: 1px solid var(--border); border-radius: 7px; background: var(--surface); color: var(--ink); }}
    .notice {{ margin-bottom: 18px; padding: 12px 14px; border: 1px solid #ead8ad; border-radius: 8px; background: var(--warning-soft); color: #65450e; }}
    .dataset-strip {{ display: flex; flex-wrap: wrap; gap: 8px 20px; margin-bottom: 18px; color: var(--text); }}
    .dataset-strip b {{ color: var(--ink); }}
    .metrics {{ display: grid; grid-template-columns: repeat(6, minmax(130px,1fr)); gap: 10px; margin-bottom: 22px; }}
    .metric {{ padding: 15px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 5px; font-size: 22px; letter-spacing: -.02em; }}
    .panel {{ margin-bottom: 18px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); overflow: hidden; }}
    .panel-head {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 16px; border-bottom: 1px solid var(--border); }}
    .panel-head h2 {{ margin: 0; font-size: 16px; }}
    .filter-group {{ display: flex; gap: 8px; }}
    .filter {{ padding: 7px 9px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #eee9e4; text-align: left; vertical-align: top; }}
    th {{ background: var(--surface-soft); color: var(--muted); font-size: 12px; font-weight: 600; white-space: nowrap; }}
    tr:last-child td {{ border-bottom: 0; }}
    .num {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
    .status {{ display: inline-flex; padding: 2px 7px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
    .status.ok {{ background: var(--success-soft); color: var(--success); }}
    .status.bad {{ background: var(--danger-soft); color: var(--danger); }}
    .status.partial {{ background: var(--warning-soft); color: var(--warning); }}
    .case-question {{ max-width: 56ch; color: var(--ink); font-weight: 550; }}
    details {{ border-top: 1px solid var(--border); }}
    details:first-child {{ border-top: 0; }}
    summary {{ display: grid; grid-template-columns: 92px minmax(260px,1fr) 90px 90px 90px; gap: 12px; align-items: center; padding: 12px 16px; cursor: pointer; }}
    summary:hover {{ background: #fcfaf8; }}
    .case-body {{ padding: 4px 16px 18px; background: #fcfaf8; }}
    .case-body h3 {{ margin: 14px 0 6px; font-size: 13px; }}
    .case-body p {{ margin: 0; max-width: 90ch; color: var(--text); }}
    .evidence, .retrieved {{ margin-top: 8px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 7px; background: var(--surface); }}
    .rank {{ color: var(--brand); font-weight: 700; }}
    .meta {{ color: var(--muted); font-size: 12px; }}
    .empty {{ padding: 28px; color: var(--muted); text-align: center; }}
    @media (max-width: 980px) {{ .metrics {{ grid-template-columns: repeat(3,1fr); }} summary {{ grid-template-columns: 80px 1fr 80px; }} .hide-small {{ display:none; }} }}
    @media (max-width: 620px) {{ .shell {{ width: min(100% - 24px,1440px); }} .topbar {{ flex-direction: column; }} .run-select {{ width:100%; }} .metrics {{ grid-template-columns: repeat(2,1fr); }} summary {{ grid-template-columns: 70px 1fr; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div><h1>PaperAI 评测面板</h1><p class="subtitle">检索质量、证据覆盖与失败样本</p></div>
      <select id="runSelect" class="run-select" aria-label="选择评测运行"></select>
    </header>
    <div class="notice">Gold 封闭测试是无偏结果；修复后回归用于验证缺陷修复，不能冒充新的封闭测试。</div>
    <div id="datasetStrip" class="dataset-strip"></div>
    <section id="e2ePanel" class="panel" hidden>
      <div class="panel-head"><h2>端到端回答与引用</h2></div>
      <div id="e2eMetrics" class="metrics" style="padding:16px;margin:0"></div>
    </section>
    <section id="agentRuntimePanel" class="panel" hidden>
      <div class="panel-head"><h2>Agent Runtime 运行观测</h2><span id="agentRuntimeSource" class="meta"></span></div>
      <div id="agentRuntimeMetrics" class="metrics" style="padding:16px;margin:0"></div>
      <div id="agentRuntimeDetails" style="padding:0 16px 16px"></div>
    </section>
    <section id="metrics" class="metrics" aria-label="核心指标"></section>
    <section class="panel"><div class="panel-head"><h2>版本对比</h2></div><div id="comparison" class="table-wrap"></div></section>
    <section class="panel"><div class="panel-head"><h2>切片表现</h2></div><div id="slices" class="table-wrap"></div></section>
    <section class="panel">
      <div class="panel-head"><h2>逐题结果</h2><div class="filter-group"><select id="statusFilter" class="filter"><option value="all">全部状态</option><option value="failed">仅失败/部分命中</option><option value="passed">仅通过</option></select></div></div>
      <div id="cases"></div>
    </section>
  </main>
  <script>
    const DATA = {payload};
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
    const pct = value => value == null ? '—' : `${{(Number(value) * 100).toFixed(2)}}%`;
    const num = value => value == null ? '—' : Number(value).toFixed(4).replace(/0+$/,'').replace(/[.]$/,'');
    const runSelect = document.querySelector('#runSelect');
    const statusFilter = document.querySelector('#statusFilter');
    DATA.runs.forEach((run, index) => runSelect.add(new Option(run.label, String(index))));
    runSelect.value = String(DATA.runs.length - 1);
    document.querySelector('#datasetStrip').innerHTML = `<span><b>${{DATA.dataset.total}}</b> 条样本</span><span><b>${{DATA.dataset.verified}}</b> Gold</span><span><b>${{DATA.dataset.silver}}</b> Silver</span><span><b>${{DATA.dataset.draft}}</b> Draft</span>`;
    if (DATA.e2e) {{
      const s=DATA.e2e.summary;
      const items=[['有效回答率',pct(s.valid_answer_rate)],['生成超时率',pct(s.timeout_rate)],['要点覆盖代理',pct(s.claim_coverage_proxy)],['引用原文支持率',pct(s.citation_precision)],['Gold 证据覆盖率',pct(s.citation_recall)],['页码一致率',pct(s.page_accuracy)],['拒答准确率',pct(s.abstention_accuracy)],['过度拒答率',pct(s.over_abstention_rate)],['无证据数字率',pct(s.unsupported_number_rate)],['关键幻觉率',pct(s.critical_hallucination_rate)],['P50 端到端',`${{num(s.p50_latency_ms)}} ms`],['P95 端到端',`${{num(s.p95_latency_ms)}} ms`]];
      document.querySelector('#e2ePanel').hidden=false;
      document.querySelector('#e2eMetrics').innerHTML=items.map(([label,value])=>`<div class="metric"><span>${{label}}</span><strong>${{value}}</strong></div>`).join('');
    }}
    function renderAgentRuntime() {{
      const report = DATA.agent_runtime;
      if (!report) return;
      const diagnostic = report.diagnostic || {{}};
      const quality = diagnostic.sample_quality || {{}};
      const sample = report.sample_size || {{}};
      const s = report.summary || {{}};
      const b = s.budget || {{}};
      const insufficient = diagnostic.analysis_mode !== 'diagnostic';
      const text = value => value == null || value === '' ? '暂无数据' : esc(value);
      const ratio = value => value == null ? '暂无数据' : `${{(Number(value) * 100).toFixed(2)}}%`;
      const listText = value => Array.isArray(value) ? value.map(item => text(item)).join('；') : text(value);
      const listLength = (object, key) => Array.isArray(object && object[key]) ? object[key].length : null;
      const table = (headers, rows, empty = '暂无可比较数据。') => {{
        if (!rows.length) return `<div class="empty">${{esc(empty)}}</div>`;
        return `<div class="table-wrap"><table><thead><tr>${{headers.map(header => `<th>${{esc(header)}}</th>`).join('')}}</tr></thead><tbody>${{rows.map(row => `<tr>${{row.map(value => `<td>${{text(value)}}</td>`).join('')}}</tr>`).join('')}}</tbody></table></div>`;
      }};
      const statusLabels = {{pending:'等待调度',queued:'已入队',running:'执行中',waiting_user:'等待用户',paused:'已暂停',retrying:'重试中',completed:'已完成',partial:'部分完成',blocked:'已阻塞',failed:'失败',cancelled:'已取消'}};
      const renderMetrics = items => document.querySelector('#agentRuntimeMetrics').innerHTML = items.map(([label,value]) => `<div class="metric"><span>${{esc(label)}}</span><strong>${{text(value)}}</strong></div>`).join('');
      document.querySelector('#agentRuntimePanel').hidden = false;
      document.querySelector('#agentRuntimeSource').textContent = report.source_file || '';
      if (insufficient) {{
        renderMetrics([
          ['样本状态', quality.label || '样本不足，仅供调试'],
          ['Execution 样本', sample.executions],
          ['ResearchTask 样本', sample.tasks],
          ['ToolCall 样本', sample.tool_calls],
          ['ModelCall 样本', sample.model_calls],
          ['疑似 Mock/测试 Execution', quality.mock_execution_count],
        ]);
        const reasonLabels = {{
          NO_EXECUTIONS: '没有可分析的 Execution 样本。',
          MOCK_ONLY: '现有 Execution 全部命中 Mock/测试标记，不能代表真实 Agent 链路。',
          NO_RESEARCH_TASKS: '没有 ResearchTask，无法比较任务表现和资源消耗。',
          NO_TOOL_CALLS: '没有 ToolCall 明细，无法判断工具失败、超时和重复调用。',
          NO_MODEL_CALLS: '没有 ModelCall 明细，无法判断模型调用和 Token 消耗。',
          TASK_SAMPLE_BELOW_TREND_THRESHOLD: 'ResearchTask 少于 20 个，暂时不能稳定观察趋势。',
        }};
        const reasons = (quality.reason_codes || []).map(reason => reasonLabels[reason] || reason);
        const agents = (quality.samples_by_agent_type || []).map(row => [row.agent_type, row.sample_size, row.classification]);
        const chains = (quality.recommended_real_chains || []).map((chain, index) => [index + 1, chain]);
        const minTrend = quality.thresholds && quality.thresholds.min_tasks_for_trend || 20;
        const minCompare = quality.thresholds && quality.thresholds.min_tasks_for_comparison || 50;
        document.querySelector('#agentRuntimeDetails').innerHTML = `<h3>当前为什么无法评价真实 Agent</h3><ul>${{(reasons.length ? reasons : ['当前 JSON 未提供样本质量原因。']).map(item => `<li>${{esc(item)}}</li>`).join('')}}</ul><h3>当前有哪些真实/Mock 样本</h3><p class="meta">${{text(quality.real_sample_label)}}</p>${{table(['agent_type','Execution 样本','分类'], agents, '暂无可识别 agent_type 样本。')}}<h3>建议先运行的真实链路</h3>${{table(['优先级','建议链路'], chains)}}<h3>ResearchTask 样本阈值</h3>${{table(['数量','可得结论'], [['<' + minTrend,'样本不足，仅供调试'],[minTrend + '–' + minCompare,'可观察初步趋势'],['>' + minCompare,'可开始做 task_type / tool / failure 对比']])}}`;
        return;
      }}

      const comparisons = diagnostic.task_type_comparison || [];
      const worst = comparisons.slice().sort((a, b) => (a.success_rate ?? 1) - (b.success_rate ?? 1))[0];
      const failedTools = diagnostic.top_failed_tools || [];
      const duplicateTasks = diagnostic.duplicate_tasks || [];
      const drilldownTargets = diagnostic.drilldown_targets || {{}};
      const executionTargets = Array.isArray(drilldownTargets.executions) ? drilldownTargets.executions : null;
      renderMetrics([
        ['样本状态', quality.label || '可观察初步趋势'],
        ['最差 Task 类型', worst && worst.task_type],
        ['主要失败类别', diagnostic.failure_categories && diagnostic.failure_categories[0] && diagnostic.failure_categories[0].category],
        ['最易失败工具', failedTools[0] && failedTools[0].tool_name],
        ['重复最严重 Task', duplicateTasks[0] && duplicateTasks[0].task_id],
        ['值得下钻 Execution', executionTargets && executionTargets.length],
      ]);
      const issueRows = (diagnostic.top_issues || []).map((item, index) => [index + 1, item.title, item.evidence, item.target]);
      const taskComparisonRows = comparisons.map(row => [row.task_type, row.sample_size, ratio(row.success_rate), ratio(row.failure_rate), row.avg_duration == null ? null : num(row.avg_duration) + ' ms', row.avg_tool_calls, row.avg_model_calls, row.avg_tokens, ratio(row.duplicate_rate)]);
      const failureRows = (diagnostic.failure_categories || []).map(row => [row.category, row.count, ratio(row.rate)]);
      const toolRows = failedTools.map(row => [row.tool_name, row.sample_size, row.failure_count, ratio(row.failure_rate), row.timeout_count, ratio(row.timeout_rate)]);
      const duplicateRows = duplicateTasks.map(row => [row.task_id, row.execution_id, row.task_type, row.duplicate_count, ratio(row.duplicate_rate), row.repeated_tools]);
      const taskResources = diagnostic.resource_anomalies && diagnostic.resource_anomalies.task_types || {{}};
      const skillResources = diagnostic.resource_anomalies && diagnostic.resource_anomalies.skills || {{}};
      const resourceRows = [];
      const resourceLabels = {{highest_avg_tool_calls:'平均 ToolCall 偏高', highest_avg_model_calls:'平均 ModelCall 偏高', highest_avg_tokens:'平均 Token 偏高'}};
      [['Task 类型', taskResources], ['Skill', skillResources]].forEach(([dimension, groups]) => Object.entries(groups).forEach(([metric, rows]) => (rows || []).slice(0, 3).forEach(row => resourceRows.push([dimension, row.name, row.sample_size, row.avg_tool_calls, row.avg_model_calls, row.avg_tokens, resourceLabels[metric] || metric]))));
      const heavyRows = ((diagnostic.resource_anomalies && diagnostic.resource_anomalies.resource_heavy_tasks) || []).map(row => [row.task_id, row.execution_id, row.task_type, row.skill_id, row.tool_calls, row.model_calls, row.tokens, listText(row.signals)]);
      const budgetRows = [
        ['接近预算的 Execution', listLength(b, 'near_budget_executions'), '任一已配置预算使用率达到 80%'],
        ['接近预算的 Task', listLength(b, 'near_budget_tasks'), 'Task 级已记录计数达到 80%'],
        ['预算超限率', ratio(b.budget_exceeded_rate), '至少一个已配置预算达到或超过上限'],
      ];
      const executionRows = (executionTargets || []).map(row => [row.execution_id, statusLabels[row.status] || row.status, row.agent_type, row.task_count, listText(row.reasons)]);
      const taskRows = (Array.isArray(drilldownTargets.tasks) ? drilldownTargets.tasks : []).map(row => [row.task_id, row.execution_id, row.task_type, row.skill_id, statusLabels[row.status] || row.status, row.attempt_count, row.tool_calls, row.model_calls, listText(row.reasons)]);
      document.querySelector('#agentRuntimeDetails').innerHTML = `<h3>当前最严重的 3 个问题</h3>${{table(['优先级','问题','证据','优先检查对象'], issueRows, '当前样本未识别出明确前三项问题。')}}<h3>Task 类型对比</h3>${{table(['task_type','sample_size','success_rate','failure_rate','avg_duration','avg_tool_calls','avg_model_calls','avg_tokens','duplicate_rate'], taskComparisonRows)}}<h3>Top Failure / Top Failed Tool / Duplicate</h3><h4>Failure Category</h4>${{table(['Failure Category','count','failure_records 占比'], failureRows)}}<h4>Top Failed Tool</h4>${{table(['tool_name','sample_size','failure_count','failure_rate','timeout_count','timeout_rate'], toolRows)}}<h4>Duplicate ToolCall 最严重的 Task</h4>${{table(['task_id','execution_id','task_type','duplicate_count','duplicate_rate','repeated_tools'], duplicateRows)}}<h3>资源与 Budget 异常</h3><h4>Task / Skill 资源偏高</h4>${{table(['维度','名称','样本','平均 ToolCall','平均 ModelCall','平均 Token','偏高指标'], resourceRows)}}<h4>资源异常 Task</h4>${{table(['task_id','execution_id','task_type','skill_id','ToolCall','ModelCall','Token','异常信号'], heavyRows)}}<h4>Budget</h4>${{table(['异常对象','数量/状态','说明'], budgetRows)}}<h3>值得下钻的 Execution / Task</h3><h4>Execution</h4>${{table(['execution_id','status','agent_type','task_count','优先检查原因'], executionRows)}}<h4>ResearchTask</h4>${{table(['task_id','execution_id','task_type','skill_id','status','attempt_count','ToolCall','ModelCall','优先检查原因'], taskRows)}}`;
    }}

    function renderMetrics(run) {{
      const s = run.summary, l = run.latency;
      const items = [['Hit@5',pct(s.hit_at_k)],['Recall@5',pct(s.evidence_recall_at_k)],['Precision@5',pct(s.precision_at_k)],['MRR',num(s.mrr)],['P50 延迟',`${{num(l.p50_ms)}} ms`],['P95 延迟',`${{num(l.p95_ms)}} ms`]];
      document.querySelector('#metrics').innerHTML = items.map(([label,value]) => `<div class="metric"><span>${{label}}</span><strong>${{value}}</strong></div>`).join('');
    }}
    function renderComparison() {{
      document.querySelector('#comparison').innerHTML = `<table><thead><tr><th>运行</th><th>样本</th><th>Hit@K</th><th>Recall@K</th><th>Precision@K</th><th>MRR</th><th>P95</th></tr></thead><tbody>${{DATA.runs.map(r => `<tr><td>${{esc(r.label)}}</td><td>${{r.summary.case_count}}</td><td class="num">${{pct(r.summary.hit_at_k)}}</td><td class="num">${{pct(r.summary.evidence_recall_at_k)}}</td><td class="num">${{pct(r.summary.precision_at_k)}}</td><td class="num">${{num(r.summary.mrr)}}</td><td class="num">${{num(r.latency.p95_ms)}} ms</td></tr>`).join('')}}</tbody></table>`;
    }}
    function renderSlices(run) {{
      const entries = Object.entries(run.slices || {{}});
      document.querySelector('#slices').innerHTML = entries.length ? `<table><thead><tr><th>切片</th><th>样本</th><th>Hit@K</th><th>Recall@K</th><th>MRR</th></tr></thead><tbody>${{entries.map(([name,s]) => `<tr><td>${{esc(name)}}</td><td>${{s.case_count}}</td><td>${{pct(s.hit_at_k)}}</td><td>${{pct(s.evidence_recall_at_k)}}</td><td>${{num(s.mrr)}}</td></tr>`).join('')}}</tbody></table>` : '<div class="empty">该报告没有切片数据</div>';
    }}
    function caseState(metrics) {{ if (!metrics.hit_at_k) return ['未命中','bad']; if (metrics.evidence_recall_at_k < 1) return ['部分命中','partial']; return ['通过','ok']; }}
    function renderCases(run) {{
      const filter = statusFilter.value;
      const rows = run.cases.filter(item => {{ const passed = item.metrics.hit_at_k && item.metrics.evidence_recall_at_k >= 1; return filter === 'all' || (filter === 'passed' && passed) || (filter === 'failed' && !passed); }});
      document.querySelector('#cases').innerHTML = rows.length ? rows.map(item => {{
        const c=item.case,m=item.metrics,g=item.gold,[label,klass]=caseState(m);
        const evidence=(g.evidence||[]).map(e=>`<div class="evidence"><div class="meta">PDF 第 ${{esc(e.page)}} 页 · ${{esc(e.section)}} · ${{esc(e.source_type)}}</div><p>${{esc(e.quote)}}</p></div>`).join('');
        const retrieved=(item.retrieved||[]).map(r=>`<div class="retrieved"><div><span class="rank">#${{r.rank}}</span> <span class="meta">PDF 第 ${{esc(r.page ?? '—')}} 页 · ${{esc(r.section)}} · score ${{num(r.score)}}</span></div><p>${{esc(r.content_preview)}}</p></div>`).join('');
        return `<details><summary><span class="status ${{klass}}">${{label}}</span><span class="case-question">${{esc(c.id)}} · ${{esc(c.question)}}</span><span class="num">Recall ${{pct(m.evidence_recall_at_k)}}</span><span class="num hide-small">MRR ${{num(m.reciprocal_rank)}}</span><span class="num hide-small">${{num(item.latency_ms)}} ms</span></summary><div class="case-body"><h3>Gold 答案</h3><p>${{esc(g.reference_answer)}}</p><h3>Gold 证据</h3>${{evidence || '<p>无证据</p>'}}<h3>Top-K 检索结果</h3>${{retrieved || '<p>无检索结果</p>'}}</div></details>`;
      }}).join('') : '<div class="empty">当前筛选条件没有样本</div>';
    }}
    function render() {{ const run=DATA.runs[Number(runSelect.value)]; renderMetrics(run); renderSlices(run); renderCases(run); }}
    runSelect.addEventListener('change', render); statusFilter.addEventListener('change', () => renderCases(DATA.runs[Number(runSelect.value)]));
    runSelect.addEventListener('change', () => {{ statusFilter.value='all'; }});
    renderComparison(); renderAgentRuntime(); render();
  </script>
</body>
</html>"""


def build_dashboard(reports_dir: Path, dataset_path: Path, output: Path,
                    agent_runtime_report: Path | None = None) -> None:
    data = load_dashboard_data(reports_dir, dataset_path, agent_runtime_report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(data), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 PaperAI 静态评测面板")
    parser.add_argument("--reports-dir", default="evals/reports")
    parser.add_argument("--dataset", default="evals/datasets/paperqa_v1.jsonl")
    parser.add_argument("--output", default="evals/reports/dashboard.html")
    parser.add_argument("--agent-runtime-report", help="指定内部 Agent Runtime 报告 JSON")
    args = parser.parse_args()
    build_dashboard(
        Path(args.reports_dir), Path(args.dataset), Path(args.output),
        Path(args.agent_runtime_report) if args.agent_runtime_report else None,
    )
    print(f"评测面板已生成：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
