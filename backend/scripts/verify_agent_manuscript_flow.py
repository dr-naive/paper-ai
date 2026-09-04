"""Database-backed end-to-end verification of the project Agent tool chain.

This verifier deliberately does not call an LLM. It invokes the real LangChain
StructuredTool instances with deterministic inputs, proving that persistence,
lineage, guardrails, finalization, and exports work independently of model
quality. A temporary project is always removed unless ``--keep`` is supplied.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import zipfile
from typing import Any

from sqlalchemy import delete, select, text

# Importing main registers every SQLAlchemy relationship target before querying.
from app.main import app as _app  # noqa: F401
from app.database import AsyncSessionLocal
from app.harness.tools.literature_research import make_project_tools
from app.models.project import ProjectPaper, ResearchProject, WritingArtifact
from app.utils.manuscript_export import build_docx, build_submission_package, markdown_to_latex


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  [OK] {message}")


async def _invoke(tools: dict[str, Any], name: str, payload: dict[str, Any]) -> str:
    result = str(await tools[name].ainvoke(payload))
    if result.startswith("错误:"):
        raise AssertionError(f"{name} failed: {result}")
    print(f"  [TOOL] {name}")
    return result


async def _latest(db, project_id: str, artifact_type: str) -> WritingArtifact:
    artifact = (await db.execute(select(WritingArtifact).where(
        WritingArtifact.project_id == project_id,
        WritingArtifact.artifact_type == artifact_type,
    ).order_by(WritingArtifact.updated_at.desc()).limit(1))).scalars().first()
    if artifact is None:
        raise AssertionError(f"missing artifact: {artifact_type}")
    return artifact


async def run(keep: bool = False) -> str:
    project_id = ""
    async with AsyncSessionLocal() as db:
        try:
            owner = (await db.execute(text("SELECT user_id, id FROM papers ORDER BY uploaded_at LIMIT 1"))).first()
            if owner is None:
                raise AssertionError("数据库没有论文，无法运行 Agent 工具链验证")
            user_id, paper_id = str(owner[0]), str(owner[1])
            project = ResearchProject(
                user_id=user_id, title="Agent manuscript flow verification",
                research_topic="Deterministic project-agent verification",
                abstract="Temporary project created by verify_agent_manuscript_flow.py",
            )
            db.add(project)
            await db.flush()
            project_id = str(project.id)
            db.add(ProjectPaper(project_id=project_id, paper_id=paper_id, role="core", reading_priority=5))
            await db.commit()
            tools = {tool.name: tool for tool in make_project_tools(db, project_id, user_id)}
            check(len(tools) == 21, "加载 21 个项目 Agent 工具")
            bypass = str(await tools["project_save_artifact"].ainvoke({
                "artifact_type": "experiment_results", "title": "Forged results",
                "markdown_text": "invented", "content": {"metrics": [{"value": 1}]},
            }))
            check(bypass.startswith("错误:"), "通用 Agent 产物工具不能绕过结果完整性")
            bypass = str(await tools["project_save_artifact"].ainvoke({
                "artifact_type": "final_manuscript", "title": "Forged final", "markdown_text": "invented",
            }))
            check(bypass.startswith("错误:"), "通用 Agent 产物工具不能绕过终稿完整性")

            print("[1/6] 阅读与研究证据")
            await _invoke(tools, "project_save_research_brief", {
                "topic": "Traceable research agents", "objective": "Verify the full research-to-manuscript chain",
                "known_context": ["A local source paper is available"], "constraints": ["No live LLM"],
                "unknowns": ["Whether every artifact keeps lineage"], "seed_keywords": ["research agent", "provenance"],
                "search_queries": ["research agent manuscript provenance"],
                "inclusion_criteria": ["Reports verifiable lineage"], "exclusion_criteria": ["No source evidence"],
                "evaluation_criteria": ["traceability", "reproducibility"], "next_actions": ["read the source"],
            })
            await _invoke(tools, "project_save_literature_screening", {
                "query_runs": [{"source": "local", "query": "research agent manuscript provenance", "result_count": 1}],
                "candidates": [{"title": "Verified local source", "authors": ["Smoke Test"], "year": 2026,
                    "url": "local://paper", "decision": "include", "reason": "Provides a verified source",
                    "relevance_score": 100, "coverage": ["provenance"]}],
                "coverage_summary": [{"dimension": "provenance", "count": 1, "gap": ""}],
                "stopping_reason": "One deterministic source is sufficient for this tool-chain smoke test",
            })
            evidence = {"paper_id": paper_id, "source_id": "S1", "page": 1, "section": "Abstract", "text": "Verified source"}
            await _invoke(tools, "project_save_paper_card", {
                "paper_id": paper_id, "summary": "A verified paper card",
                "research_questions": ["Can the tool chain persist lineage?"],
                "methods": ["deterministic integration verification"], "datasets": ["local database"],
                "metrics": ["lineage completeness"], "contributions": ["end-to-end proof"],
                "findings": ["the source is persisted"], "limitations": ["no live LLM"], "evidence": [evidence],
            })
            await _invoke(tools, "project_save_research_map", {
                "topic_summary": "Verify the complete project Agent chain.", "keywords": ["agent", "verification"],
                "research_questions": [{"question": "Can every stage be traced?", "source_ids": ["S1"]}],
                "method_families": [{"name": "deterministic verification", "papers": [paper_id]}],
                "datasets": [], "research_gaps": [{"gap": "Missing chain proof", "source_ids": ["S1"]}],
                "candidate_topics": [{"title": "Traceable research Agent", "next_step": "run tool chain"}],
                "evidence": [evidence],
            })
            await _invoke(tools, "project_save_reading_plan", {
                "objective": "Verify the selected source", "items": [{"paper_id": paper_id, "order": 1, "priority": 5,
                    "reason": "Only verified source", "focus": ["evidence"], "questions": ["Is lineage retained?"]}],
            })
            await _invoke(tools, "project_build_evidence_matrix", {
                "research_question": "Can every manuscript claim retain a source?", "conflicts": [], "evidence_gaps": [],
            })
            matrix = await _latest(db, project_id, "evidence_matrix")

            print("[2/6] 实验设计与论文蓝图")
            await _invoke(tools, "project_save_experiment_design", {
                "research_question": "Does the tool chain preserve lineage?", "hypothesis": "Every stage remains linked.",
                "rationale": "The evidence matrix provides a verified source.",
                "independent_variables": ["workflow stage"], "dependent_variables": ["lineage validity"],
                "controls": ["same project"], "datasets": [], "baselines": [], "metrics": [{"name": "valid links"}],
                "experiment_steps": ["invoke tools", "inspect artifacts"], "ablations": [],
                "success_criteria": ["all links resolve"], "falsification_criteria": ["any link is missing"],
                "risks": [], "evidence_refs": [evidence],
            })
            design = await _latest(db, project_id, "experiment_design")
            check((design.content or {}).get("evidence_matrix_id") == str(matrix.id), "实验设计绑定证据矩阵")
            await _invoke(tools, "project_save_experiment_results", {
                "experiment_design_id": str(design.id), "run_id": "deterministic-smoke-run",
                "sources": [{"source_id": "R1", "source_type": "user_report", "locator": "verify_agent_manuscript_flow.py fixture"}],
                "metrics": [{"metric": "valid links", "value": 1.0, "unit": "ratio", "dataset": "local database",
                             "method": "full tool chain", "source_id": "R1"}],
                "hypothesis_outcome": "supported", "qualitative_findings": ["Every checked link resolved"],
                "protocol_deviations": [], "analysis_notes": ["Deterministic fixture, not a scientific claim"],
            })
            results = await _latest(db, project_id, "experiment_results")
            check((results.content or {}).get("experiment_design_id") == str(design.id), "实验结果绑定实验设计和来源")
            sections = [
                {"section_id": "intro", "title": "Introduction", "order": 1, "purpose": "Motivate the problem"},
                {"section_id": "method", "title": "Method", "order": 2, "purpose": "Describe verification"},
                {"section_id": "conclusion", "title": "Conclusion", "order": 3, "purpose": "Summarize evidence"},
            ]
            for section in sections:
                section.update({"key_claims": ["The chain is traceable"], "evidence_refs": [evidence],
                                "citation_needs": ["verified source"], "word_target": 100})
            await _invoke(tools, "project_save_paper_blueprint", {
                "working_title": "A Traceable Research Agent", "central_claim": "Every stage preserves provenance.",
                "target_audience": "PaperAI developers", "target_venue": "Integration Test", "sections": sections,
            })
            blueprint = await _latest(db, project_id, "paper_blueprint")
            check((blueprint.content or {}).get("experiment_design_id") == str(design.id), "论文蓝图绑定实验设计")

            print("[3/6] 分节写作与参考文献")
            for section in sections:
                body = (f"# {section['title']}\n\nThis section verifies persistent, source-backed manuscript lineage. " * 3).strip()
                section_payload = {
                    "blueprint_id": str(blueprint.id), "section_id": section["section_id"],
                    "title": section["title"], "markdown_text": body,
                    "evidence_refs": [evidence], "unresolved_items": [],
                    "contains_empirical_results": False, "results_source": "",
                }
                if section["section_id"] == "conclusion":
                    section_payload.update({
                        "contains_empirical_results": True,
                        "experiment_results_id": str(results.id),
                        "results_source": "R1",
                    })
                await _invoke(tools, "project_save_section_draft", section_payload)
            await _invoke(tools, "project_build_reference_list", {"blueprint_id": str(blueprint.id)})
            references = await _latest(db, project_id, "reference_list")
            check((references.meta or {}).get("generated_by") == "deterministic_reference_builder", "参考文献由受信任工具生成")

            print("[4/6] 全文组装、审计与定稿")
            await _invoke(tools, "project_assemble_full_draft", {"blueprint_id": str(blueprint.id), "title": "Verified full draft"})
            full_draft = await _latest(db, project_id, "full_draft")
            check("[@" in full_draft.markdown_text and (full_draft.content or {}).get("reference_list_id") == str(references.id), "全文写入稳定引用键并绑定参考文献版本")
            check(str(results.id) in ((full_draft.content or {}).get("experiment_results_ids") or []), "全文绑定可信实验结果")
            await _invoke(tools, "project_audit_full_draft", {"full_draft_id": str(full_draft.id), "issues": []})
            report = await _latest(db, project_id, "review_report")
            check(((report.content or {}).get("counts") or {}).get("blocker") == 0, "全文审计无阻断项")
            await _invoke(tools, "project_finalize_manuscript", {
                "full_draft_id": str(full_draft.id), "review_report_id": str(report.id), "title": "Verified final manuscript",
            })
            final = await _latest(db, project_id, "final_manuscript")
            check(final.parent_id == full_draft.id and final.status == "ready", "终稿绑定已审计全文并锁定")

            print("[5/6] 投稿格式与包结构")
            bibtex = str((references.content or {}).get("bibtex") or "")
            latex = markdown_to_latex(final.title, final.markdown_text)
            check("\\cite{" in latex and "\\printbibliography" in latex, "LaTeX 包含可编译引用")
            with zipfile.ZipFile(io.BytesIO(build_docx(final.title, final.markdown_text))) as archive:
                check("word/document.xml" in archive.namelist(), "Word 容器有效")
            package = build_submission_package(final.title, final.markdown_text, bibtex, report.markdown_text)
            with zipfile.ZipFile(io.BytesIO(package)) as archive:
                required = {"manuscript.md", "manuscript.tex", "manuscript.docx", "references.bib", "audit-report.md", "MANIFEST.txt"}
                check(required <= set(archive.namelist()), "投稿包包含正文、引用、审计和清单")

            print("[6/6] Agent 工具链验证完成")
            return project_id
        finally:
            if project_id and not keep:
                await db.rollback()
                await db.execute(delete(ResearchProject).where(ResearchProject.id == project_id))
                await db.commit()
                print(f"  [CLEANUP] 已删除测试项目 {project_id}")
            elif project_id:
                print(f"  [KEEP] 测试项目保留: {project_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the database-backed Agent manuscript tool chain")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.keep))
        print("[PASS] Agent manuscript tool chain")
        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
