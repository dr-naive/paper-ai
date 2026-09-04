from dataclasses import dataclass

import yaml

from app.harness.runtime.skill_runtime import SkillRuntime
from app.harness.runtime.standard_tools import build_standard_tool_runtime


@dataclass
class MockModelTurn:
    tool: str | None = None
    arguments: dict | None = None
    final: str | None = None


def run_mock_loop(turns: list[MockModelTurn], tool_results: dict[str, dict]) -> tuple[list[str], str]:
    calls, final = [], ""
    for turn in turns:
        if turn.tool:
            calls.append(turn.tool)
            assert turn.tool in tool_results
        if turn.final:
            final = turn.final
    return calls, final


def test_mock_llm_tool_tool_final_sequence_is_deterministic():
    calls, final = run_mock_loop([
        MockModelTurn("project.list_papers", {}),
        MockModelTurn("project.search_content", {"query": "limitations"}),
        MockModelTurn(final="The evidence is insufficient for one subclaim."),
    ], {"project.list_papers": {"ok": True}, "project.search_content": {"ok": True}})
    assert calls == ["project.list_papers", "project.search_content"]
    assert "insufficient" in final


def test_each_migrated_skill_has_at_least_five_eval_cases():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "app" / "harness" / "skills"
    tool_specs = build_standard_tool_runtime().specs()
    runtime = SkillRuntime(root, tool_specs)
    for skill_id in ("paper_internal", "external_literature", "literature_research"):
        runtime.load(skill_id)
        payload = yaml.safe_load((root / skill_id / "evals" / "cases.yaml").read_text(encoding="utf-8"))
        assert len(payload["cases"]) >= 5
        assert len({case["id"] for case in payload["cases"]}) == len(payload["cases"])
