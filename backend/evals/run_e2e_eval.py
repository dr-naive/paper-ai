from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.models import EvalCase, load_jsonl, validate_dataset


def select_cases(cases: list[EvalCase], split: str, limit: int | None = None) -> list[EvalCase]:
    selected = [
        case for case in cases
        if case.split == split and case.annotation_status == "verified"
    ]
    return selected[:limit] if limit else selected


def _paper_metadata(paper: Any) -> dict[str, Any]:
    return {
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "keywords": paper.keywords or [],
        "venue": paper.venue,
        "publication_year": paper.publication_year,
        "doi": paper.doi,
    }


def _chunk_snapshot(chunk: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "section": chunk.get("section"),
        "page": chunk.get("page"),
        "chunk_type": chunk.get("chunk_type"),
        "chunk_index": chunk.get("chunk_index"),
        "table_number": chunk.get("table_number"),
        "score": chunk.get("score"),
        "content": str(chunk.get("content", "")),
    }


def _new_report(args: Any, dataset_path: Path) -> dict[str, Any]:
    return {
        "report_type": "e2e_raw",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path.resolve()),
        "configuration": {
            "split": args.split,
            "top_k": args.top_k,
            "verified_only": True,
            "follow_up_generation": False,
        },
        "summary": {},
        "cases": [],
    }


def load_or_create_report(output: Path, args: Any, dataset_path: Path) -> dict[str, Any]:
    if args.resume and output.exists():
        report = json.loads(output.read_text(encoding="utf-8"))
        if report.get("report_type") != "e2e_raw":
            raise ValueError(f"{output} 不是端到端原始报告")
        return report
    return _new_report(args, dataset_path)


def save_report(report: dict[str, Any], output: Path) -> None:
    rows = report["cases"]
    successful = [row for row in rows if row.get("status") == "completed"]
    latencies = sorted(float(row.get("latency_ms", 0)) for row in successful)

    def percentile(ratio: float) -> float | None:
        if not latencies:
            return None
        position = (len(latencies) - 1) * ratio
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return round(latencies[lower], 2)
        weight = position - lower
        return round(latencies[lower] * (1 - weight) + latencies[upper] * weight, 2)

    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["summary"] = {
        "case_count": len(rows),
        "completed_count": len(successful),
        "failed_count": len(rows) - len(successful),
        "p50_latency_ms": percentile(0.5),
        "p95_latency_ms": percentile(0.95),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


async def run(args: Any) -> dict[str, Any]:
    dataset_path = Path(args.dataset)
    output = Path(args.output)
    cases = load_jsonl(dataset_path)
    errors = validate_dataset(cases)
    if errors:
        raise ValueError("数据集校验失败：\n" + "\n".join(f"- {error}" for error in errors))

    selected = select_cases(cases, args.split, args.case_limit)
    if not selected:
        raise ValueError("当前 split 没有 verified 评测项")

    report = load_or_create_report(output, args, dataset_path)
    completed_ids = {
        row["case"]["id"]
        for row in report["cases"]
        if row.get("status") == "completed"
    }

    # 延迟导入，避免 --help 和数据校验初始化数据库、向量库及模型。
    from sqlalchemy import select
    from app.agent.qa_agent.enhanced_graph import run_enhanced_qa_agent
    from app.database import AsyncSessionLocal
    # SQLAlchemy relationships use class names, so all related models must be
    # registered when this runner starts outside the FastAPI application.
    from app.models.user import User  # noqa: F401
    from app.models.chat import ChatMessage, ChatSession, InterpretCache, SummaryCache  # noqa: F401
    from app.models.paper import Paper
    from app.rag.knowledge_base import get_knowledge_base
    from app.rag.table_retrieval import get_exact_table_chunks, merge_retrieval_chunks

    knowledge_base = get_knowledge_base()
    async with AsyncSessionLocal() as db:
        for index, case in enumerate(selected, 1):
            if case.id in completed_ids:
                print(f"[{index}/{len(selected)}] {case.id}: 已存在，跳过")
                continue

            # A previous failed attempt is replaced by this retry.
            report["cases"] = [
                row for row in report["cases"] if row["case"]["id"] != case.id
            ]

            started_at = time.perf_counter()
            row: dict[str, Any] = {
                "case": {
                    "id": case.id,
                    "paper_id": case.paper_id,
                    "paper_title": case.paper_title,
                    "question": case.question,
                    "task_type": case.task_type,
                    "difficulty": case.difficulty,
                    "reference_answer": case.reference_answer,
                    "reference_claims": list(case.reference_claims),
                    "evidence": [evidence.__dict__ for evidence in case.evidence],
                },
                "status": "failed",
            }
            try:
                result = await db.execute(select(Paper).where(Paper.id == case.paper_id))
                paper = result.scalar_one_or_none()
                if paper is None:
                    raise ValueError(f"数据库中不存在论文 {case.paper_id}")

                retrieval_started = time.perf_counter()
                exact_chunks = await get_exact_table_chunks(db, case.paper_id, case.question)
                semantic_chunks = await knowledge_base.query(
                    case.paper_id, case.question, top_k=args.top_k
                )
                chunks = merge_retrieval_chunks(exact_chunks, semantic_chunks, top_k=args.top_k)
                retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)

                generation_started = time.perf_counter()
                answer = await run_enhanced_qa_agent(
                    case.paper_id,
                    case.question,
                    chunks,
                    _paper_metadata(paper),
                    generate_follow_up=False,
                )
                generation_ms = round((time.perf_counter() - generation_started) * 1000, 2)
                row.update({
                    "status": "completed",
                    "retrieval_latency_ms": retrieval_ms,
                    "generation_latency_ms": generation_ms,
                    "answer": answer.get("answer", ""),
                    "intent": answer.get("intent", ""),
                    "intent_confidence": answer.get("intent_confidence", 0.0),
                    "evidence_confidence": answer.get("evidence_confidence", 0.0),
                    "citations": answer.get("citations", []),
                    "sources": answer.get("sources", []),
                    "retrieved": [
                        _chunk_snapshot(chunk, rank)
                        for rank, chunk in enumerate(chunks, 1)
                    ],
                })
            except Exception as exc:  # 保留失败样本，避免整轮结果丢失。
                row["error"] = f"{type(exc).__name__}: {exc}"

            row["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
            report["cases"].append(row)
            save_report(report, output)
            print(
                f"[{index}/{len(selected)}] {case.id}: {row['status']} "
                f"{row['latency_ms'] / 1000:.1f}s"
            )

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="采集 PaperAI 端到端回答与引用")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", choices=("dev", "test"), default="test")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume", action="store_true", help="跳过报告中已有的 case")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k 必须大于等于 1")
    if args.case_limit is not None and args.case_limit < 1:
        parser.error("--case-limit 必须大于等于 1")

    try:
        report = asyncio.run(run(args))
    except (ValueError, json.JSONDecodeError) as exc:
        print(exc)
        return 1

    print("\n采集汇总：")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"原始报告：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
