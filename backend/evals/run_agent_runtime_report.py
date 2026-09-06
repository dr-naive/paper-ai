"""CLI for the deterministic Agent Runtime JSON and Markdown reports.

Usage: ``cd backend && python -m evals.run_agent_runtime_report``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models.execution import AgentEvent, AgentExecution, ModelCall, ResearchTask, ToolCall
from evals.agent_runtime_metrics import build_runtime_report
from evals.agent_runtime_markdown import render_runtime_report_markdown


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


async def load_runtime_rows(args):
    since = _parse_since(args.since)
    async with AsyncSessionLocal() as db:
        execution_filter = []
        if since is not None:
            execution_filter.append(AgentExecution.created_at >= since)
        total_execution_count = int(
            await db.scalar(select(func.count(AgentExecution.id)).where(*execution_filter)) or 0
        )
        query = select(AgentExecution).where(*execution_filter).order_by(AgentExecution.created_at.desc())
        if args.limit is not None and args.limit > 0:
            query = query.limit(args.limit)
        executions = list((await db.scalars(query)).all())
        execution_ids = [row.id for row in executions]
        created_at_values = [row.created_at for row in executions if row.created_at is not None]
        collection = {
            "total_execution_count": total_execution_count,
            "selected_execution_count": len(executions),
            "truncated": len(executions) < total_execution_count,
            "selection_order": "created_at_desc",
            "oldest_created_at": min(created_at_values).isoformat() if created_at_values else None,
            "newest_created_at": max(created_at_values).isoformat() if created_at_values else None,
        }
        if not execution_ids:
            return executions, [], [], [], [], collection
        tasks = list((await db.scalars(select(ResearchTask).where(ResearchTask.execution_id.in_(execution_ids)))).all())
        tool_calls = list((await db.scalars(select(ToolCall).where(ToolCall.execution_id.in_(execution_ids)))).all())
        model_calls = list((await db.scalars(select(ModelCall).where(ModelCall.execution_id.in_(execution_ids)))).all())
        events = list((await db.scalars(select(AgentEvent).where(AgentEvent.execution_id.in_(execution_ids)))).all())
        return executions, tasks, tool_calls, model_calls, events, collection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 PaperAI Agent Runtime 观测报告")
    parser.add_argument("--limit", type=int, default=None, help="最多读取多少条 Execution；默认读取全部")
    parser.add_argument("--since", help="只读取该 ISO 时间之后的 Execution")
    parser.add_argument("--task-type", action="append", dest="task_types", help="按 task_type 过滤，可重复")
    parser.add_argument("--skill-id", help="按 skill_id 过滤")
    parser.add_argument("--output", help="报告输出路径")
    parser.add_argument("--markdown-output", help="中文 Markdown 报告输出路径；默认与 JSON 同名")
    return parser


async def async_main(args) -> tuple[Path, Path]:
    executions, tasks, tool_calls, model_calls, events, collection = await load_runtime_rows(args)
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
        events=events,
        filters=filters,
        collection=collection,
    )
    output = Path(args.output) if args.output else Path("evals/reports") / (
        f"agent_runtime_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    markdown_output = Path(args.markdown_output) if args.markdown_output else output.with_suffix(".md")
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    markdown_output.write_text(render_runtime_report_markdown(report), encoding="utf-8")
    return output, markdown_output


def main() -> int:
    args = build_parser().parse_args()
    output, markdown_output = asyncio.run(async_main(args))
    print(f"Agent Runtime JSON 报告已生成：{output}")
    print(f"Agent Runtime 中文 Markdown 报告已生成：{markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
