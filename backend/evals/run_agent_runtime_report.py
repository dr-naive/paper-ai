"""CLI for the deterministic Agent Runtime report.

Usage: ``cd backend && python -m evals.run_agent_runtime_report``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.execution import AgentExecution, ModelCall, ResearchTask, ToolCall
from evals.agent_runtime_metrics import build_runtime_report


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


async def load_runtime_rows(args):
    since = _parse_since(args.since)
    async with AsyncSessionLocal() as db:
        query = select(AgentExecution).order_by(AgentExecution.created_at.desc())
        if since is not None:
            query = query.where(AgentExecution.created_at >= since)
        if args.limit:
            query = query.limit(args.limit)
        executions = list((await db.scalars(query)).all())
        execution_ids = [row.id for row in executions]
        if not execution_ids:
            return executions, [], [], []
        tasks = list((await db.scalars(select(ResearchTask).where(ResearchTask.execution_id.in_(execution_ids)))).all())
        tool_calls = list((await db.scalars(select(ToolCall).where(ToolCall.execution_id.in_(execution_ids)))).all())
        model_calls = list((await db.scalars(select(ModelCall).where(ModelCall.execution_id.in_(execution_ids)))).all())
        return executions, tasks, tool_calls, model_calls


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 PaperAI Agent Runtime 观测报告")
    parser.add_argument("--limit", type=int, default=1000, help="最多读取多少条 Execution")
    parser.add_argument("--since", help="只读取该 ISO 时间之后的 Execution")
    parser.add_argument("--task-type", action="append", dest="task_types", help="按 task_type 过滤，可重复")
    parser.add_argument("--skill-id", help="按 skill_id 过滤")
    parser.add_argument("--output", help="报告输出路径")
    return parser


async def async_main(args) -> Path:
    executions, tasks, tool_calls, model_calls = await load_runtime_rows(args)
    filters = {
        "limit": args.limit,
        "since": args.since,
        "task_types": args.task_types or [],
        "skill_id": args.skill_id,
    }
    report = build_runtime_report(
        executions=executions,
        tasks=tasks,
        tool_calls=tool_calls,
        model_calls=model_calls,
        filters=filters,
    )
    output = Path(args.output) if args.output else Path("evals/reports") / (
        f"agent_runtime_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return output


def main() -> int:
    args = build_parser().parse_args()
    output = asyncio.run(async_main(args))
    print(f"Agent Runtime 报告已生成：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

