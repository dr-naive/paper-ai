from __future__ import annotations

import argparse
import json
from collections import Counter

from evals.models import load_jsonl, validate_dataset


def build_summary(cases):
    return {
        "total": len(cases),
        "verified": sum(case.annotation_status == "verified" for case in cases),
        "silver": sum(case.annotation_status == "silver" for case in cases),
        "draft": sum(case.annotation_status == "draft" for case in cases),
        "answerable": sum(case.answerable for case in cases),
        "unanswerable": sum(not case.answerable for case in cases),
        "papers": len({case.paper_id for case in cases}),
        "by_task_type": dict(sorted(Counter(case.task_type for case in cases).items())),
        "by_difficulty": dict(sorted(Counter(case.difficulty for case in cases).items())),
        "by_split": dict(sorted(Counter(case.split for case in cases).items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 PaperAI JSONL 评测集")
    parser.add_argument("--dataset", required=True, help="JSONL 数据集路径")
    args = parser.parse_args()

    cases = load_jsonl(args.dataset)
    errors = validate_dataset(cases)
    print(json.dumps(build_summary(cases), ensure_ascii=False, indent=2))
    if errors:
        print("\n校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print("\n数据集校验通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
