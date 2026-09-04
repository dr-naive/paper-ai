"""End-to-end smoke test for the research-project API.

The script uses a real access token and an existing user-owned paper.  It creates
isolated project data and removes the project in ``finally`` unless ``--keep`` is
specified, so it is safe to run repeatedly against a development deployment.

Examples:
    PAPERAI_TOKEN=... python -m scripts.verify_project_flow
    python -m scripts.verify_project_flow --token ... --paper-id ... --base-url http://localhost:8000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import io
import zipfile
from dataclasses import dataclass
from typing import Any


@dataclass
class ApiClient:
    base_url: str
    token: str

    def call(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        body = json.dumps(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                if response.status not in expected:
                    raise AssertionError(f"{method} {path}: HTTP {response.status}, expected {expected}")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AssertionError(
                f"{method} {path}: HTTP {exc.code}, expected {expected}; response={detail[:500]}"
            ) from exc

    def expect_error(self, method: str, path: str, data: dict[str, Any], status: int) -> str:
        try:
            self.call(method, path, data)
        except AssertionError as exc:
            if f"HTTP {status}" not in str(exc):
                raise
            return str(exc)
        raise AssertionError(f"{method} {path}: expected HTTP {status}, request unexpectedly succeeded")

    def download(self, path: str) -> tuple[bytes, str]:
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}{path}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read(), response.headers.get_content_type()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  [OK] {message}")


def select_paper(client: ApiClient, requested_id: str) -> str:
    if requested_id:
        return requested_id
    payload = client.call("GET", "/api/v1/papers/?limit=100")
    papers = payload.get("items", payload) if isinstance(payload, dict) else payload
    if not papers:
        raise AssertionError("当前账号没有论文，请先上传论文或传入 --paper-id")
    ready = next((paper for paper in papers if paper.get("status") in {"ready", "completed"}), papers[0])
    return str(ready["id"])


def run(client: ApiClient, paper_id: str, keep: bool) -> None:
    project_id = ""
    artifact_id = ""
    try:
        print("[1/8] 项目 CRUD")
        created = client.call(
            "POST",
            "/api/v1/projects",
            {
                "title": "Project flow smoke test",
                "research_topic": "Agent project workflow verification",
                "abstract": "由 verify_project_flow.py 创建，可安全删除。",
            },
            (201,),
        )
        project_id = created["id"]
        check(bool(project_id), "创建项目")
        detail = client.call("GET", f"/api/v1/projects/{project_id}")
        check(detail["id"] == project_id, "读取项目详情")
        updated = client.call("PATCH", f"/api/v1/projects/{project_id}", {"phase": "reading"})
        check(updated["phase"] == "reading", "更新项目阶段")
        listing = client.call("GET", "/api/v1/projects?page=1&page_size=100&q=Project%20flow")
        check(any(item["id"] == project_id for item in listing["items"]), "项目列表筛选")
        workflow = client.call("GET", f"/api/v1/projects/{project_id}/workflow-status")
        check(workflow["next_stage"] == "research_brief" and workflow["total"] >= 10, "空项目先进入题材澄清阶段")
        brief = client.call(
            "POST", f"/api/v1/projects/{project_id}/artifacts", {
                "artifact_type": "research_brief", "title": "Research brief smoke test",
                "content": {"topic": "Agent workflow", "objective": "Verify the chain",
                            "search_queries": ["agent research workflow"], "unknowns": ["coverage"]},
                "markdown_text": "# Research brief smoke test\n\nVerify the chain.",
            }, (201,),
        )
        check(brief["artifact_type"] == "research_brief", "保存研究任务书")
        workflow = client.call("GET", f"/api/v1/projects/{project_id}/workflow-status")
        check(workflow["next_stage"] == "literature_screening", "研究任务书完成后推进到候选筛选")
        screening = client.call(
            "POST", f"/api/v1/projects/{project_id}/artifacts", {
                "artifact_type": "literature_screening", "title": "Screening smoke test",
                "content": {"query_runs": [{"source": "local", "query": "agent workflow", "result_count": 1}],
                            "candidates": [{"title": "Existing test paper", "decision": "include"}],
                            "included_count": 1, "excluded_count": 0, "maybe_count": 0},
                "markdown_text": "# Screening smoke test\n\nOne included candidate.",
            }, (201,),
        )
        check(screening["artifact_type"] == "literature_screening", "保存候选文献筛选台账")
        workflow = client.call("GET", f"/api/v1/projects/{project_id}/workflow-status")
        check(workflow["next_stage"] == "library", "筛选完成后推进到文献入库")

        print("[2/8] 项目文档库")
        added = client.call(
            "POST",
            f"/api/v1/projects/{project_id}/papers",
            {"paper_id": paper_id, "role": "related", "tags": ["smoke"], "reading_priority": 3},
            (201,),
        )
        check(added["paper_id"] == paper_id, "加入项目论文")
        workflow = client.call("GET", f"/api/v1/projects/{project_id}/workflow-status")
        check(workflow["next_stage"] == "research_map", "加入论文后推进到领域地图")
        changed = client.call(
            "PATCH",
            f"/api/v1/projects/{project_id}/papers/{paper_id}",
            {"role": "core", "reading_priority": 5},
        )
        check(changed["role"] == "core" and changed["reading_priority"] == 5, "更新论文角色与优先级")
        changed = client.call(
            "PATCH",
            f"/api/v1/projects/{project_id}/papers/{paper_id}",
            {
                "reading_plan": {
                    "order": 1,
                    "status": "reading",
                    "reason": "Smoke queue",
                    "focus": ["API contract"],
                    "questions": ["Does the queue persist?"],
                }
            },
        )
        check(changed["reading_plan"]["status"] == "reading", "保存项目精读队列状态")
        papers = client.call("GET", f"/api/v1/projects/{project_id}/papers?role=core")
        check(papers["total"] == 1, "按角色读取项目论文")
        card = client.call(
            "PATCH",
            f"/api/v1/projects/{project_id}/papers/{paper_id}/card",
            {
                "summary": "Smoke paper card",
                "methods": ["integration test"],
                "findings": ["card persisted"],
                "evidence": [{"source_id": "S1", "page": 1, "text": "smoke"}],
            },
        )
        check(card["card"]["findings"] == ["card persisted"], "保存结构化论文卡片")
        card = client.call("GET", f"/api/v1/projects/{project_id}/papers/{paper_id}/card")
        check(card["card"]["summary"] == "Smoke paper card", "读取结构化论文卡片")

        print("[3/8] 项目记忆")
        memory = client.call("GET", f"/api/v1/projects/{project_id}/memory")
        check(memory["note_count"] == 0, "读取空项目记忆")
        memory = client.call(
            "PATCH",
            f"/api/v1/projects/{project_id}/memory",
            {"summary": "Smoke summary", "notes": []},
        )
        check(memory["summary"] == "Smoke summary", "更新记忆摘要")
        note = client.call(
            "POST",
            f"/api/v1/projects/{project_id}/memory/note",
            {
                "text": "Project flow verified",
                "tag": "finding",
                "source_type": "paper",
                "paper_id": paper_id,
                "paper_title": "Smoke source paper",
                "page": 1,
                "source_id": "S1",
            },
            (201,),
        )
        check(note["note_count"] == 1 and note["note"]["paper_id"] == paper_id, "追加可追溯项目记忆")

        print("[4/8] 研究与写作产物")
        artifact = client.call(
            "POST",
            f"/api/v1/projects/{project_id}/artifacts",
            {
                "artifact_type": "outline",
                "title": "Smoke outline",
                "markdown_text": "# Smoke outline\n\n- verified",
            },
            (201,),
        )
        artifact_id = artifact["id"]
        check(bool(artifact_id), "创建写作产物")
        artifacts = client.call("GET", f"/api/v1/projects/{project_id}/artifacts?type=outline")
        check(any(item["id"] == artifact_id for item in artifacts["items"]), "筛选写作产物")
        artifact = client.call("GET", f"/api/v1/projects/{project_id}/artifacts/{artifact_id}")
        check(artifact["markdown_text"].startswith("# Smoke"), "读取产物正文")
        artifact = client.call(
            "PATCH",
            f"/api/v1/projects/{project_id}/artifacts/{artifact_id}",
            {"status": "ready", "title": "Smoke outline verified"},
        )
        check(artifact["status"] == "ready", "更新写作产物")
        research_map = client.call(
            "POST",
            f"/api/v1/projects/{project_id}/artifacts",
            {
                "artifact_type": "research_map",
                "title": "Smoke research map",
                "content": {
                    "topic_summary": "Smoke domain summary",
                    "keywords": ["smoke"],
                    "research_questions": [{"question": "Does the flow persist maps?"}],
                    "method_families": [],
                    "datasets": [],
                    "research_gaps": [{"gap": "Flow validation", "source_ids": ["S1"]}],
                    "candidate_topics": [{"title": "Smoke topic", "next_step": "Verify UI"}],
                    "evidence": [{"paper_id": paper_id, "source_id": "S1", "page": 1}],
                },
                "markdown_text": "# Smoke research map",
            },
            (201,),
        )
        research_map_id = research_map["id"]
        maps = client.call("GET", f"/api/v1/projects/{project_id}/artifacts?type=research_map")
        check(maps["items"][0]["id"] == research_map_id, "保存并筛选领域地图")
        reading_plan = client.call(
            "POST",
            f"/api/v1/projects/{project_id}/artifacts",
            {
                "artifact_type": "reading_plan",
                "title": "Smoke reading plan",
                "content": {"objective": "Verify queue", "items": [{"paper_id": paper_id, "order": 1}]},
                "markdown_text": "# Smoke reading plan",
            },
            (201,),
        )
        reading_plan_id = reading_plan["id"]
        plans = client.call("GET", f"/api/v1/projects/{project_id}/artifacts?type=reading_plan")
        check(plans["items"][0]["id"] == reading_plan_id, "保存并筛选精读计划")

        evidence_matrix = client.call("POST", f"/api/v1/projects/{project_id}/artifacts", {
            "artifact_type": "evidence_matrix", "title": "Smoke evidence matrix",
            "content": {"research_question": "Can lineage persist?", "rows": [{"paper_id": paper_id}], "conflicts": [], "evidence_gaps": []},
            "markdown_text": "# Evidence matrix",
        }, (201,))
        experiment_design = client.call("POST", f"/api/v1/projects/{project_id}/artifacts", {
            "artifact_type": "experiment_design", "title": "Smoke experiment design",
            "content": {"evidence_matrix_id": evidence_matrix["id"], "hypothesis": "The lineage remains intact.",
                        "requires_empirical_results": False},
            "markdown_text": "# Experiment design",
        }, (201,))
        blueprint = client.call("POST", f"/api/v1/projects/{project_id}/artifacts", {
            "artifact_type": "paper_blueprint", "title": "Smoke blueprint",
            "content": {"experiment_design_id": experiment_design["id"], "sections": [{"section_id": "intro", "order": 1}]},
            "markdown_text": "# Blueprint",
        }, (201,))
        section = client.call("POST", f"/api/v1/projects/{project_id}/artifacts", {
            "artifact_type": "section_draft", "title": "Smoke section", "parent_id": blueprint["id"],
            "meta": {"section_id": "intro", "evidence_refs": [{"paper_id": paper_id, "source_id": "S1", "page": 1}]},
            "markdown_text": "# Introduction\nVerified evidence [S1].",
        }, (201,))
        check(
            experiment_design["content"]["evidence_matrix_id"] == evidence_matrix["id"]
            and blueprint["content"]["experiment_design_id"] == experiment_design["id"]
            and section["parent_id"] == blueprint["id"],
            "研究问题到章节草稿的产物血缘可追踪",
        )

        print("[5/8] 完整性旁路防护")
        client.expect_error("POST", f"/api/v1/projects/{project_id}/artifacts", {
            "artifact_type": "final_manuscript", "title": "Forged final", "markdown_text": "bypass",
        }, 409)
        client.expect_error("POST", f"/api/v1/projects/{project_id}/artifacts", {
            "artifact_type": "experiment_results", "title": "Forged results", "markdown_text": "bypass",
        }, 409)
        client.expect_error("POST", f"/api/v1/projects/{project_id}/artifacts", {
            "artifact_type": "review_report", "title": "Forged audit", "markdown_text": "bypass",
            "meta": {"audit_kind": "full_draft"},
        }, 400)
        check(True, "通用 REST 接口不能伪造实验结果、审计报告或终稿")

        print("[6/8] 项目会话")
        session = client.call(
            "POST",
            "/api/v1/chat/sessions",
            {"project_id": project_id, "title": "Project smoke chat"},
        )
        check(session["project_id"] == project_id and session["paper_id"] is None, "创建项目模式会话")
        sessions = client.call("GET", f"/api/v1/chat/sessions?project_id={project_id}")
        check(any(item["id"] == session["id"] for item in sessions["items"]), "按项目筛选会话")
        messages = client.call("GET", f"/api/v1/chat/sessions/{session['id']}/messages")
        check(messages["project_id"] == project_id, "项目 ID 贯穿会话详情")

        print("[7/8] 清理子资源")
        client.call("DELETE", f"/api/v1/projects/{project_id}/artifacts/{artifact_id}", expected=(204,))
        client.call("DELETE", f"/api/v1/projects/{project_id}/artifacts/{research_map_id}", expected=(204,))
        client.call("DELETE", f"/api/v1/projects/{project_id}/artifacts/{reading_plan_id}", expected=(204,))
        artifact_id = ""
        client.call("DELETE", f"/api/v1/projects/{project_id}/papers/{paper_id}", expected=(204,))
        check(True, "删除产物并移除项目论文")

        print("[8/8] 项目流程验证完成")
    finally:
        if project_id and not keep:
            try:
                client.call("DELETE", f"/api/v1/projects/{project_id}", expected=(204,))
                print(f"  [CLEANUP] 已删除测试项目 {project_id}")
            except Exception as exc:  # cleanup failure must be visible without hiding the original failure
                print(f"  [WARN] 测试项目清理失败: {exc}", file=sys.stderr)
        elif project_id:
            print(f"  [KEEP] 测试项目保留: {project_id}")


def verify_existing_exports(client: ApiClient, project_id: str, artifact_id: str) -> None:
    """Validate a real Agent-finalized manuscript and every downloadable representation."""
    print("[LIVE] 验证真实终稿与投稿包")
    artifact = client.call("GET", f"/api/v1/projects/{project_id}/artifacts/{artifact_id}")
    check(artifact["artifact_type"] == "final_manuscript", "目标产物是 Agent 锁定终稿")
    for fmt, expected_type in (("md", "text/markdown"), ("tex", "application/x-tex"), ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")):
        payload, content_type = client.download(f"/api/v1/projects/{project_id}/artifacts/{artifact_id}/download?format={fmt}")
        check(bool(payload) and content_type == expected_type, f"{fmt} 导出可下载且 MIME 正确")
        if fmt == "docx":
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                check("word/document.xml" in archive.namelist(), "Word 文档容器有效")
    package, content_type = client.download(f"/api/v1/projects/{project_id}/artifacts/{artifact_id}/download?format=zip")
    check(content_type == "application/zip", "投稿包 MIME 正确")
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        required = {"manuscript.md", "manuscript.tex", "manuscript.docx", "references.bib", "audit-report.md", "MANIFEST.txt"}
        check(required <= set(archive.namelist()), "投稿包文件完整")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the complete research-project API flow")
    parser.add_argument("--base-url", default=os.getenv("PAPERAI_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.getenv("PAPERAI_TOKEN", ""))
    parser.add_argument("--paper-id", default=os.getenv("PAPERAI_PAPER_ID", ""))
    parser.add_argument("--keep", action="store_true", help="保留脚本创建的项目，便于 UI 检查")
    parser.add_argument("--existing-project-id", default=os.getenv("PAPERAI_EXISTING_PROJECT_ID", ""), help="可选：验证已有真实项目终稿")
    parser.add_argument("--final-artifact-id", default=os.getenv("PAPERAI_FINAL_ARTIFACT_ID", ""), help="可选：已有项目中的 final_manuscript ID")
    args = parser.parse_args()
    if not args.token:
        parser.error("请通过 --token 或 PAPERAI_TOKEN 提供访问令牌")

    try:
        client = ApiClient(args.base_url, args.token)
        if bool(args.existing_project_id) != bool(args.final_artifact_id):
            raise AssertionError("--existing-project-id 与 --final-artifact-id 必须同时提供")
        if args.existing_project_id:
            verify_existing_exports(client, args.existing_project_id, args.final_artifact_id)
        paper_id = select_paper(client, args.paper_id)
        print(f"使用论文: {paper_id}")
        run(client, paper_id, args.keep)
        print("[PASS] Project API flow")
        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
