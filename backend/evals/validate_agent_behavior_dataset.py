"""校验 Agent Behavior V1 JSONL，不调用 LLM。"""
from __future__ import annotations

import argparse
import json

from evals.agent_behavior_dataset import (
    dataset_summary,
    load_jsonl_objects,
    load_paperqa_case_ids,
    load_skill_cases,
    load_skill_definitions,
    validate_cases,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 PaperAI Agent Behavior V1 约束数据集")
    parser.add_argument("--dataset", default="evals/datasets/agent_behavior_v1.jsonl", help="行为约束 JSONL 路径")
    parser.add_argument("--paperqa", default="evals/datasets/paperqa_v1.jsonl", help="来源 PaperQA JSONL 路径")
    parser.add_argument("--skills-root", default="app/harness/skills", help="Skill 根目录")
    args = parser.parse_args()

    rows = load_jsonl_objects(args.dataset)
    errors = validate_cases(
        rows,
        paperqa_case_ids=load_paperqa_case_ids(args.paperqa),
        skill_cases=load_skill_cases(args.skills_root),
        skill_definitions=load_skill_definitions(args.skills_root),
    )
    print(json.dumps(dataset_summary(rows), ensure_ascii=False, indent=2))
    if errors:
        print("\n校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print("\nAgent Behavior V1 数据集校验通过；未执行 LLM 评分。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
