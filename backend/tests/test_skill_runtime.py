from pathlib import Path

import pytest

from app.harness.runtime.skill_runtime import SkillRuntime
from app.harness.runtime.standard_tools import build_standard_tool_runtime


SKILLS_DIR = Path(__file__).resolve().parents[1] / "app" / "harness" / "skills"


def runtime():
    return SkillRuntime(SKILLS_DIR, build_standard_tool_runtime().specs())


@pytest.mark.parametrize("skill_id", ["paper_internal", "external_literature", "literature_research"])
def test_migrated_skill_definitions_are_valid(skill_id):
    definition = runtime().load(skill_id)
    assert definition.id == skill_id
    assert definition.version == "1.0.0"
    assert definition.allowed_tools
    assert definition.budget.max_tool_calls > 0
    assert definition.completion.criteria


def test_skill_tool_allowlist_and_completion_metadata():
    skills = runtime()
    assert skills.allows("literature_research", "project.search_content")
    assert not skills.allows("paper_internal", "literature.search_external")
    definition = skills.load("paper_internal")
    assert definition.completion_metadata({"paper_id": "p1", "source_ids": ["S1"], "ignored": True}) == {
        "paper_id": "p1", "source_ids": ["S1"]}


def test_skill_budget_rejects_exhausted_calls():
    with pytest.raises(RuntimeError, match="SKILL_TOOL_BUDGET_EXCEEDED"):
        runtime().assert_budget("paper_internal", tool_calls=20)
