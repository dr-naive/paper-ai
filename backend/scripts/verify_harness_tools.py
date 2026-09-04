"""验证 paper_internal harness tools 的模式是否跑通。

不传 --paper-id 时:只验证 tool 工厂返回的元数据(数量/名字/schema),不需要 db。
传 --paper-id 时:实际调用 get_paper_metadata + list_paper_sections 验证调用链路。

用法:
    # 离线验证(不需要 db 连接)
    python -m scripts.verify_harness_tools

    # 在线验证(需要 db 连接 + 已上传的论文)
    python -m scripts.verify_harness_tools --paper-id <uuid>
"""
from __future__ import annotations

import argparse
import asyncio
import json

# 必须先 import 所有 models,避免 SQLAlchemy mapper 配置顺序问题
from app.models.chat import ChatMessage, ChatSession, InterpretCache, SummaryCache  # noqa: F401
from app.models.paper import Image, Note, Paper, Section, Table, TableStructure  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.project import ProjectPaper, ResearchProject, WritingArtifact  # noqa: F401

EXPECTED_TOOL_NAMES = [
    "get_paper_metadata",
    "list_paper_sections",
    "search_paper_content",
    "lookup_table_data",
    "compute_over_tables",
    "export_citation_format",
]

EXPECTED_PROJECT_TOOL_NAMES = [
    "project_search_content",
    "project_add_paper",
    "project_remove_paper",
    "project_import_arxiv_paper",
    "project_append_memory",
    "project_save_paper_card",
    "project_save_research_brief",
    "project_save_literature_screening",
    "project_save_research_map",
    "project_save_reading_plan",
    "project_build_evidence_matrix",
    "project_save_experiment_design",
    "project_save_experiment_results",
    "project_save_paper_blueprint",
    "project_save_section_draft",
    "project_assemble_full_draft",
    "project_build_reference_list",
    "project_audit_full_draft",
    "project_finalize_manuscript",
    "project_read_memory",
    "project_save_artifact",
]


def verify_tool_metadata() -> None:
    """验证 tool 工厂返回的元数据(不需要 db)。"""
    # 用一个 mock db(不会被实际访问,只验证元数据)
    class _MockDB:
        pass

    from app.harness.tools.paper_internal import make_paper_internal_tools

    tools = make_paper_internal_tools(_MockDB())
    assert len(tools) == len(EXPECTED_TOOL_NAMES), (
        f"tool 数量不对:期望 {len(EXPECTED_TOOL_NAMES)},实际 {len(tools)}"
    )

    actual_names = [tool.name for tool in tools]
    assert actual_names == EXPECTED_TOOL_NAMES, (
        f"tool 名字不对:期望 {EXPECTED_TOOL_NAMES},实际 {actual_names}"
    )

    for tool in tools:
        # 每个 tool 必须有 args_schema(Pydantic 类)
        assert tool.args_schema is not None, f"{tool.name} 缺少 args_schema"
        # 每个 tool 必须是 coroutine(LLM agent 需要 async)
        assert tool.coroutine is not None, f"{tool.name} 缺少 coroutine"
        # description 不能为空(LLM 据此选 tool)
        assert tool.description and tool.description.strip(), (
            f"{tool.name} 缺少 description"
        )

    print("[OK] tool 元数据验证通过")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description[:60]}...")

    from app.harness.tools.literature_research import make_project_tools

    project_tools = make_project_tools(_MockDB(), "project-test", "user-test")
    actual_project_names = [tool.name for tool in project_tools]
    assert actual_project_names == EXPECTED_PROJECT_TOOL_NAMES, (
        f"project tool 名字不对:期望 {EXPECTED_PROJECT_TOOL_NAMES},实际 {actual_project_names}"
    )
    for tool in project_tools:
        assert tool.args_schema is not None, f"{tool.name} 缺少 args_schema"
        assert tool.coroutine is not None, f"{tool.name} 缺少 coroutine"
        assert tool.description and tool.description.strip(), f"{tool.name} 缺少 description"
    print("[OK] project tool 元数据验证通过")
    for tool in project_tools:
        print(f"  - {tool.name}: {tool.description[:60]}...")


async def verify_online_call(paper_id: str) -> None:
    """实际调用 get_paper_metadata + list_paper_sections 验证链路。"""
    from app.database import AsyncSessionLocal, close_db
    from app.harness.tools.paper_internal import make_paper_internal_tools

    try:
        async with AsyncSessionLocal() as db:
            tools = make_paper_internal_tools(db)
            tools_by_name = {tool.name: tool for tool in tools}

            # 调用 get_paper_metadata
            print(f"\n[调用] get_paper_metadata(paper_id={paper_id})")
            result = await tools_by_name["get_paper_metadata"].ainvoke(
                {"paper_id": paper_id}
            )
            parsed = json.loads(result)
            if "error" in parsed:
                print(f"  [ERROR] {parsed['error']}")
            else:
                print(f"  [OK] 标题: {parsed.get('title', '')[:80]}")
                print(f"  [OK] 作者: {parsed.get('authors', '')[:80]}")
                print(f"  [OK] 年份: {parsed.get('publication_year')}")

            # 调用 list_paper_sections
            print(f"\n[调用] list_paper_sections(paper_id={paper_id})")
            result = await tools_by_name["list_paper_sections"].ainvoke(
                {"paper_id": paper_id, "include_summary": False}
            )
            parsed = json.loads(result)
            if "error" in parsed:
                print(f"  [ERROR] {parsed['error']}")
            else:
                print(f"  [OK] 章节数: {parsed.get('total', 0)}")
                for section in parsed.get("sections", [])[:5]:
                    print(
                        f"    #{section['order_index']} {section['title']} "
                        f"(p.{section['start_page']}, 字数≈{section['approx_word_count']})"
                    )

            # 调用 export_citation_format(纯派生,不需要正文)
            print(f"\n[调用] export_citation_format(paper_id={paper_id}, format=bibtex)")
            result = await tools_by_name["export_citation_format"].ainvoke(
                {"paper_id": paper_id, "format": "bibtex"}
            )
            parsed = json.loads(result)
            if "error" in parsed:
                print(f"  [ERROR] {parsed['error']}")
            else:
                print(f"  [OK] BibTeX:\n{parsed['citation']}")
    finally:
        await close_db()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--paper-id",
        default=None,
        help="可选。传入则实际调用 tool 验证链路;不传只验证元数据。",
    )
    args = parser.parse_args()

    verify_tool_metadata()

    if args.paper_id:
        await verify_online_call(args.paper_id)
    else:
        print("\n(未传 --paper-id,跳过在线调用验证)")


if __name__ == "__main__":
    asyncio.run(main())
