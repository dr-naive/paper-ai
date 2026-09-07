"""把管理员评测运行适配到现有评测脚本。

这里不实现检索、问答或运行时指标，只负责选择已有 runner、固定输出位置并读取
结构化汇总。所有输出路径都由 run_id 派生，重复消费会复用同一份报告。
"""
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR


REPORTS_DIR = BACKEND_DIR / "evals" / "reports"
ADMIN_REPORTS_DIR = REPORTS_DIR / "admin_evaluations"
DATASET_PATH = BACKEND_DIR / "evals" / "datasets" / "paperqa_v1.jsonl"


def default_evaluation_config(evaluation_type: str) -> dict[str, Any]:
    if evaluation_type == "runtime":
        return {"scope": "all_executions"}
    if evaluation_type == "retrieval":
        return {
            "dataset": "paperqa_v1.jsonl",
            "split": "dev",
            "top_k": 5,
            "include_silver": False,
            "include_drafts": False,
        }
    if evaluation_type == "e2e":
        return {
            "dataset": "paperqa_v1.jsonl",
            "split": "test",
            "top_k": 5,
            "case_limit": None,
        }
    raise ValueError(f"不支持的评测类型: {evaluation_type}")


def report_paths(run_id: str) -> tuple[Path, Path, Path]:
    ADMIN_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ADMIN_REPORTS_DIR / f"{run_id}.json"
    markdown_path = ADMIN_REPORTS_DIR / f"{run_id}.md"
    raw_path = ADMIN_REPORTS_DIR / f"{run_id}.raw.json"
    return json_path, markdown_path, raw_path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_report(run_id: str) -> dict[str, Any] | None:
    json_path, _, _ = report_paths(run_id)
    if not json_path.is_file():
        return None
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


async def run_admin_evaluation(
    run_id: str,
    evaluation_type: str,
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str, str | None]:
    """执行一轮已有评测并返回报告、JSON 相对路径和 Markdown 相对路径。"""
    existing = load_report(run_id)
    json_path, markdown_path, raw_path = report_paths(run_id)
    if existing is not None:
        return existing, str(json_path.relative_to(REPORTS_DIR)), str(markdown_path.relative_to(REPORTS_DIR)) if markdown_path.is_file() else None

    options = {**default_evaluation_config(evaluation_type), **(config or {})}
    if evaluation_type == "runtime":
        from evals.run_agent_runtime_report import async_main

        await async_main(
            Namespace(
                limit=None,
                since=None,
                task_types=None,
                skill_id=None,
                output=str(json_path),
                markdown_output=str(markdown_path),
            )
        )
        report = load_report(run_id)
        if report is None:
            raise RuntimeError("Agent Runtime 评测未生成有效报告")
        return report, str(json_path.relative_to(REPORTS_DIR)), str(markdown_path.relative_to(REPORTS_DIR))

    if evaluation_type == "retrieval":
        from evals.run_retrieval_eval import run

        report = await run(
            Namespace(
                dataset=str(DATASET_PATH),
                split=str(options["split"]),
                top_k=int(options["top_k"]),
                include_silver=bool(options.get("include_silver")),
                include_drafts=bool(options.get("include_drafts")),
            )
        )
        _write_json(json_path, report)
        return report, str(json_path.relative_to(REPORTS_DIR)), None

    if evaluation_type == "e2e":
        from evals.run_e2e_eval import run
        from evals.score_e2e_eval import score_report

        raw_report = await run(
            Namespace(
                dataset=str(DATASET_PATH),
                split=str(options["split"]),
                top_k=int(options["top_k"]),
                case_limit=options.get("case_limit"),
                output=str(raw_path),
                resume=True,
            )
        )
        report = score_report(raw_report)
        _write_json(json_path, report)
        return report, str(json_path.relative_to(REPORTS_DIR)), None

    raise ValueError(f"不支持的评测类型: {evaluation_type}")
