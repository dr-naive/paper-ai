"""Minimal live-LLM verification for project-scoped Lead Agent tool selection.

This script makes one short call to the configured model provider. It creates a
temporary project, asks the Lead Agent to persist one memory item, verifies the
tool trace and database side effect, then always removes the project.
"""
from __future__ import annotations

import asyncio
from sqlalchemy import delete, text

from app.main import app as _app  # noqa: F401
from app.database import AsyncSessionLocal
from app.harness.agents.lead_agent import run_lead_agent
from app.models.project import ProjectPaper, ResearchProject


async def run() -> None:
    project_id = ""
    async with AsyncSessionLocal() as db:
        try:
            owner = (await db.execute(text("SELECT user_id, id FROM papers ORDER BY uploaded_at LIMIT 1"))).first()
            if owner is None:
                raise AssertionError("数据库没有论文，无法运行项目 Agent 在线验证")
            user_id, paper_id = str(owner[0]), str(owner[1])
            project = ResearchProject(
                user_id=user_id, title="Live project Agent verification",
                research_topic="Verify project-scoped tool selection",
                abstract="Temporary live-LLM smoke project",
            )
            db.add(project)
            await db.flush()
            project_id = str(project.id)
            db.add(ProjectPaper(project_id=project_id, paper_id=paper_id, role="core"))
            await db.commit()
            result = await run_lead_agent(
                db=db, paper_id=paper_id, user_id=user_id, project_id=project_id,
                question=("这是一次工具调用验证。请调用 project_append_memory，把“在线项目 Agent 工具链已验证”"
                          "记录为 tag=verification 的项目记忆；不要调用其他写入工具。"),
                skill_names=["literature_research"], max_iterations=3, enable_critique=False,
            )
            called = [item["name"] for item in result.trace.tool_calls]
            if "project_append_memory" not in called:
                raise AssertionError(f"Lead Agent 未选择 project_append_memory，实际调用: {called}")
            await db.refresh(project)
            notes = (project.memory or {}).get("notes") or []
            if not any("在线项目 Agent 工具链已验证" in str(item.get("text") or "") for item in notes):
                raise AssertionError("工具轨迹存在，但项目记忆未持久化")
            print(f"  [OK] Lead Agent 工具轨迹: {called}")
            print("  [OK] project_id 已注入且记忆写入真实数据库")
            print("[PASS] Live project Lead Agent")
        finally:
            if project_id:
                await db.rollback()
                await db.execute(delete(ResearchProject).where(ResearchProject.id == project_id))
                await db.commit()
                print(f"  [CLEANUP] 已删除测试项目 {project_id}")


if __name__ == "__main__":
    asyncio.run(run())
