from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from evals.metrics.retrieval import aggregate_retrieval_metrics, score_retrieval_case
from evals.models import EvalCase, load_jsonl, validate_dataset


def _retrieval_cases(
    cases: list[EvalCase],
    split: str,
    include_silver: bool,
    include_drafts: bool,
) -> list[EvalCase]:
    allowed_statuses = {"verified"}
    if include_silver:
        allowed_statuses.add("silver")
    if include_drafts:
        allowed_statuses.add("draft")
    return [
        case
        for case in cases
        if case.split == split
        and case.answerable
        and case.task_type != "metadata"
        and case.evidence
        and case.annotation_status in allowed_statuses
    ]


async def run(args) -> dict:
    cases = load_jsonl(args.dataset)
    errors = validate_dataset(cases)
    if errors:
        raise ValueError("数据集校验失败：\n" + "\n".join(f"- {error}" for error in errors))

    selected = _retrieval_cases(
        cases,
        args.split,
        args.include_silver,
        args.include_drafts,
    )
    if not selected:
        raise ValueError("没有符合条件的评测项。请检查 split 和 annotation_status。")

    # 延迟导入，保证纯数据校验不初始化向量库和模型配置。
    from app.rag.knowledge_base import get_knowledge_base

    knowledge_base = get_knowledge_base()
    case_reports = []
    metrics = []
    for index, case in enumerate(selected, 1):
        started_at = time.perf_counter()
        chunks = await knowledge_base.query(case.paper_id, case.question, top_k=args.top_k)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        row = score_retrieval_case(case, chunks, args.top_k)
        metrics.append(row)
        case_reports.append({
            "case": {
                "id": case.id,
                "paper_id": case.paper_id,
                "question": case.question,
                "task_type": case.task_type,
                "difficulty": case.difficulty,
            },
            "metrics": row.to_dict(),
            "latency_ms": elapsed_ms,
            "retrieved": [
                {
                    "rank": rank,
                    "section": chunk.get("section"),
                    "page": chunk.get("page"),
                    "chunk_type": chunk.get("chunk_type"),
                    "chunk_index": chunk.get("chunk_index"),
                    "table_number": chunk.get("table_number"),
                    "score": chunk.get("score"),
                    "content_preview": str(chunk.get("content", ""))[:500],
                }
                for rank, chunk in enumerate(chunks, 1)
            ],
        })
        print(
            f"[{index}/{len(selected)}] {case.id}: "
            f"hit={row.hit_at_k:.0f} recall={row.evidence_recall_at_k:.2f} "
            f"mrr={row.reciprocal_rank:.2f} {elapsed_ms:.0f}ms"
        )

    grouped: dict[str, list] = defaultdict(list)
    for case, row in zip(selected, metrics):
        grouped[f"task_type:{case.task_type}"].append(row)
        grouped[f"difficulty:{case.difficulty}"].append(row)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(Path(args.dataset).resolve()),
        "configuration": {
            "split": args.split,
            "top_k": args.top_k,
            "include_silver": args.include_silver,
            "include_drafts": args.include_drafts,
        },
        "summary": aggregate_retrieval_metrics(metrics),
        "slices": {
            name: aggregate_retrieval_metrics(rows)
            for name, rows in sorted(grouped.items())
        },
        "cases": case_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 PaperAI 检索评测")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--include-silver", action="store_true")
    parser.add_argument("--include-drafts", action="store_true")
    parser.add_argument("--output", help="报告 JSON 路径")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k 必须大于等于 1")

    try:
        report = asyncio.run(run(args))
    except ValueError as exc:
        print(exc)
        return 1

    output = Path(args.output) if args.output else Path("evals/reports") / (
        f"retrieval_{args.split}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n汇总：")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"报告已写入：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
