from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from evals.metrics.e2e import aggregate_e2e_metrics, score_e2e_case


def score_report(raw: dict) -> dict:
    completed = [row for row in raw.get("cases", []) if row.get("status") == "completed"]
    cases = []
    metrics = []
    for row in completed:
        scored = score_e2e_case(row)
        metrics.append(scored)
        cases.append({
            "case": row.get("case", {}),
            "metrics": scored.to_dict(),
            "answer": row.get("answer", ""),
            "citations": row.get("citations", []),
            "latency_ms": row.get("latency_ms"),
        })
    summary = aggregate_e2e_metrics(metrics)
    summary.update({
        "p50_latency_ms": raw.get("summary", {}).get("p50_latency_ms"),
        "p95_latency_ms": raw.get("summary", {}).get("p95_latency_ms"),
    })
    return {
        "report_type": "e2e_scored",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_report": raw.get("dataset"),
        "summary": summary,
        "cases": cases,
        "metric_notes": {
            "citation_precision": "引用文字可由其 source_id 指向的检索块支持的比例",
            "citation_recall": "Gold 证据被已引用检索块覆盖的比例",
            "page_accuracy": "引用页码与 source_id 指向检索块页码一致的比例",
            "claim_coverage_proxy": "答案与 Gold 原子事实的字符重合代理，不等同于答案准确率",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="对端到端原始报告执行确定性规则评分")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = score_report(raw)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"评分报告：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
