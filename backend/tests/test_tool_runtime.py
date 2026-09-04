from pydantic import BaseModel

from app.harness.runtime.standard_tools import build_standard_tool_runtime
from app.harness.runtime.tool_runtime import ToolResult, ToolSpec


EXPECTED_TOOLS = {
    "paper.get_metadata", "paper.get_outline", "paper.search_content",
    "project.list_papers", "project.search_content", "literature.search_external",
}


def test_phase_three_standard_tools_have_complete_contracts():
    runtime = build_standard_tool_runtime()
    specs = {spec.name: spec for spec in runtime.specs()}
    assert set(specs) == EXPECTED_TOOLS
    for spec in specs.values():
        assert spec.version == "1.0.0"
        assert spec.side_effect in {"read", "network"}
        assert spec.timeout_seconds > 0
        assert spec.idempotent is True
        assert issubclass(spec.input_schema, BaseModel)


def test_tool_input_schemas_reject_invalid_limits():
    runtime = build_standard_tool_runtime()
    schema = runtime.get_spec("literature.search_external").input_schema
    assert schema.model_validate({"query": "agents", "max_results": 5}).max_results == 5
    try:
        schema.model_validate({"query": "agents", "max_results": 100})
    except Exception:
        pass
    else:
        raise AssertionError("max_results boundary was not enforced")


def test_tool_result_is_structured_and_has_safe_defaults():
    result = ToolResult(ok=True, summary="done")
    assert result.data is None
    assert result.evidence_ids == [] and result.artifact_ids == []
