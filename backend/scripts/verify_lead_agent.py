"""验证 lead_agent 的 ReAct loop 是否能正确自主选 tool。

跑法:
    docker exec paperai-backend python -m scripts.verify_lead_agent --paper-id <pid>

覆盖场景:
1. 元数据类问题 → 应该调 get_paper_metadata
2. 正文检索类问题 → 应该调 search_paper_content
3. 引用导出类问题 → 应该调 export_citation_format
4. 表格类问题 → 应该调 lookup_table_data 或 compute_over_tables
"""
import argparse
import asyncio
import sys

from app.database import AsyncSessionLocal, close_db
# 项目惯例:必须 import 所有 models,否则 SQLAlchemy mapper 初始化失败
from app.models.chat import ChatMessage, ChatSession, InterpretCache, SummaryCache  # noqa: F401
from app.models.user import User  # noqa: F401
from app.harness.agents.lead_agent import run_lead_agent


PAPER_ID_FOR_TEST = "587bb6d3-24bf-4bab-adda-3e8b7c5e7e6c"

# 测试用例: (问题, 期望命中的 tool 名之一)
TEST_CASES = [
    ("论文作者是谁?", ["get_paper_metadata"]),
    ("论文用了什么算法?", ["search_paper_content"]),
    ("给我这篇论文的 BibTeX", ["export_citation_format"]),
    ("论文有哪些章节?", ["list_paper_sections"]),
]


async def run_one_case(db, paper_id: str, question: str, expected_tools: list[str]) -> dict:
    """跑单个用例,返回结果摘要。"""
    print(f"\n[问] {question}")
    print(f"    期望命中 tool: {expected_tools}")
    result = await run_lead_agent(
        db=db,
        paper_id=paper_id,
        question=question,
        skill_names=["paper_internal"],  # 期 2 只用 paper_internal
        max_iterations=3,
    )
    called_tools = [tc["name"] for tc in result.trace.tool_calls]
    hit = any(t in called_tools for t in expected_tools)
    print(f"    实际调用 tool: {called_tools}")
    print(f"    命中: {'✓' if hit else '✗'}")
    print(f"    迭代轮次: {result.trace.iterations}")
    print(f"    总耗时: {result.trace.total_ms:.0f}ms")
    print(f"    回答预览: {result.answer[:150]}...")
    return {
        "question": question,
        "expected": expected_tools,
        "actual": called_tools,
        "hit": hit,
        "success": result.success,
    }


async def main(paper_id: str):
    results = []
    async with AsyncSessionLocal() as db:
        for question, expected in TEST_CASES:
            res = await run_one_case(db, paper_id, question, expected)
            results.append(res)
    await close_db()

    print("\n" + "=" * 50)
    hit_count = sum(1 for r in results if r["hit"])
    print(f"tool 选择命中率: {hit_count}/{len(results)}")
    if hit_count == len(results):
        print("[OK] lead_agent 全部用例通过")
        return 0
    else:
        failed = [r["question"] for r in results if not r["hit"]]
        print(f"[FAIL] 以下用例 tool 选择错误: {failed}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-id", default=PAPER_ID_FOR_TEST)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.paper_id)))
