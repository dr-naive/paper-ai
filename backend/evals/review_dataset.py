from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evals.models import EvalCase, validate_case


REVIEW_STATUSES = {"draft", "silver"}


def load_rows(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dataset_path = Path(path)
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{dataset_path}:{line_number} JSON 无效: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{dataset_path}:{line_number} 每行必须是 JSON 对象")
            rows.append(row)
    return rows


def write_rows(path: str | Path, rows: list[dict[str, Any]]) -> None:
    dataset_path = Path(path)
    dataset_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def review_candidates(rows: list[dict[str, Any]], statuses: set[str] | None = None) -> list[dict[str, Any]]:
    allowed = statuses or REVIEW_STATUSES
    return [
        row for row in rows
        if str(row.get("annotation_status", "draft")) in allowed
    ]


def set_case_status(
    rows: list[dict[str, Any]],
    case_id: str,
    status: str,
    review_note: str = "",
) -> bool:
    updated = False
    for row in rows:
        if row.get("id") != case_id:
            continue
        row["annotation_status"] = status
        if review_note:
            row["review_note"] = review_note
        errors = validate_case(EvalCase.from_dict(row))
        if errors:
            raise ValueError(f"{case_id} 校验失败：{'；'.join(errors)}")
        updated = True
        break
    return updated


def discard_case(rows: list[dict[str, Any]], case_id: str) -> bool:
    original_count = len(rows)
    rows[:] = [row for row in rows if row.get("id") != case_id]
    return len(rows) != original_count


def render_markdown(rows: list[dict[str, Any]], limit: int | None = None) -> str:
    selected = rows[:limit] if limit else rows
    parts = ["# PaperAI Dataset Review Queue", ""]
    for row in selected:
        evidence = row.get("evidence", [])
        claims = row.get("reference_claims", [])
        parts.extend([
            f"## {row.get('id', '')} [{row.get('annotation_status', 'draft')}]",
            "",
            f"- paper: {row.get('paper_title', '')}",
            f"- split: {row.get('split', '')}",
            f"- task_type: {row.get('task_type', '')}",
            f"- difficulty: {row.get('difficulty', '')}",
            f"- answerable: {row.get('answerable')}",
            f"- must_abstain: {row.get('must_abstain')}",
            "",
            f"**Question**: {row.get('question', '')}",
            "",
            f"**Reference Answer**: {row.get('reference_answer', '')}",
            "",
            "**Claims**:",
        ])
        if claims:
            parts.extend(f"- {claim}" for claim in claims)
        else:
            parts.append("- None")
        parts.extend(["", "**Evidence**:"])
        if evidence:
            for index, item in enumerate(evidence, 1):
                parts.extend([
                    f"{index}. page={item.get('page')} section={item.get('section', '')} table={item.get('table_number')}",
                    "",
                    f"> {item.get('quote', '')}",
                    "",
                ])
        else:
            parts.append("- None")
        parts.extend([
            "**Review decision**: verified / keep draft / discard",
            "",
        ])
    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="辅助审核 PaperAI JSONL 评测集")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--status", choices=("draft", "silver", "verified"), action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--export-md", help="导出待审核 Markdown 文件")
    parser.add_argument("--case-id", help="要修改状态的 case id")
    parser.add_argument("--set-status", choices=("draft", "silver", "verified"), help="设置指定 case 的标注状态")
    parser.add_argument("--discard", action="store_true", help="丢弃指定 case，从 JSONL 中删除")
    parser.add_argument("--review-note", default="")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit 必须大于等于 1")
    if args.discard and not args.case_id:
        parser.error("--discard 需要同时提供 --case-id")
    if args.discard and args.set_status:
        parser.error("--discard 不能和 --set-status 同时使用")
    if bool(args.case_id) != bool(args.set_status) and not args.discard:
        parser.error("--case-id 和 --set-status 必须同时提供")

    rows = load_rows(args.dataset)
    if args.discard:
        if not discard_case(rows, args.case_id):
            print(f"未找到 case：{args.case_id}")
            return 1
        write_rows(args.dataset, rows)
        print(f"已丢弃 {args.case_id}")
        return 0

    if args.set_status:
        if not set_case_status(rows, args.case_id, args.set_status, args.review_note):
            print(f"未找到 case：{args.case_id}")
            return 1
        write_rows(args.dataset, rows)
        print(f"已更新 {args.case_id} -> {args.set_status}")
        return 0

    statuses = set(args.status) if args.status else REVIEW_STATUSES
    candidates = review_candidates(rows, statuses)
    if args.export_md:
        output = Path(args.export_md)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_markdown(candidates, args.limit), encoding="utf-8")
        print(f"审核队列已导出：{output}（{min(len(candidates), args.limit or len(candidates))} 条）")
        return 0

    selected = candidates[:args.limit] if args.limit else candidates
    for row in selected:
        print(
            f"{row.get('id')} [{row.get('annotation_status')}] "
            f"{row.get('task_type')} answerable={row.get('answerable')} "
            f"{row.get('question')}"
        )
    print(f"共 {len(candidates)} 条候选")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
