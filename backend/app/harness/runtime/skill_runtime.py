"""Strict loader and policy boundary for versioned declarative skills."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.harness.runtime.tool_runtime import ToolContext, ToolResult, ToolRuntime, ToolSpec
from app.models.execution import AgentExecution

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


class SkillPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    network: bool = False
    write_project: bool = False
    write_memory: bool = False
    destructive: bool = False


class SkillBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_tool_calls: int = Field(ge=1, le=1000)
    max_external_searches: int = Field(default=0, ge=0, le=100)
    max_papers_to_read: int = Field(default=0, ge=0, le=1000)
    max_seconds: int = Field(default=1800, ge=1, le=86400)


class SkillCompletion(BaseModel):
    model_config = ConfigDict(extra="allow")
    criteria: list[str] = Field(min_length=1)
    required_metadata: list[str] = Field(default_factory=list)


class SkillDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    allowed_tools: list[str] = Field(min_length=1)
    permissions: SkillPermissions
    budget: SkillBudget
    completion: SkillCompletion
    supported_task_types: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    produced_artifacts: list[str] = Field(default_factory=list)
    max_model_calls: int = Field(default=20, ge=0, le=1000)

    @property
    def completion_criteria(self) -> list[str]:
        return self.completion.criteria

    @property
    def max_tool_calls(self) -> int:
        return self.budget.max_tool_calls

    @model_validator(mode="after")
    def validate_definition(self):
        if not SEMVER.fullmatch(self.version):
            raise ValueError("skill version 必须使用 semver x.y.z")
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("allowed_tools 不能重复")
        return self

    def completion_metadata(self, values: dict[str, Any]) -> dict[str, Any]:
        return {key: values.get(key) for key in self.completion.required_metadata}


class SkillCriterionEvaluation(BaseModel):
    criterion: str
    passed: bool


class SkillCompletionReport(BaseModel):
    skill_id: str
    skill_version: str
    passed: bool
    criteria: list[SkillCriterionEvaluation]
    missing_metadata: list[str]
    metadata: dict[str, Any]


class SkillRuntime:
    def __init__(self, skills_dir: Path, tool_specs: list[ToolSpec]):
        self.skills_dir = skills_dir
        self.tool_specs = {spec.name: spec for spec in tool_specs}
        self._definitions: dict[str, SkillDefinition] = {}

    def load(self, skill_id: str) -> SkillDefinition:
        if skill_id in self._definitions:
            return self._definitions[skill_id]
        root = (self.skills_dir / skill_id).resolve()
        if root.parent != self.skills_dir.resolve():
            raise KeyError("非法 skill id")
        yaml_path = root / "skill.yaml"
        md_path = root / "SKILL.md"
        if not yaml_path.is_file() or not md_path.is_file():
            raise KeyError(f"Skill 文件不完整: {skill_id}")
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        definition = SkillDefinition.model_validate(raw)
        if definition.id != skill_id:
            raise ValueError(f"目录名 {skill_id} 与 skill id {definition.id} 不一致")
        missing = sorted(set(definition.allowed_tools) - set(self.tool_specs))
        if missing:
            raise ValueError(f"Skill {skill_id} 引用了未注册 Tool: {missing}")
        for name in definition.allowed_tools:
            effect = self.tool_specs[name].side_effect
            if effect == "network" and not definition.permissions.network:
                raise ValueError(f"Skill {skill_id} 未声明 network 权限")
            if effect == "destructive" and not definition.permissions.destructive:
                raise ValueError(f"Skill {skill_id} 未声明 destructive 权限")
        self._definitions[skill_id] = definition
        return definition

    def allows(self, skill_id: str, tool_name: str) -> bool:
        return tool_name in self.load(skill_id).allowed_tools

    async def activate(self, execution: AgentExecution, skill_id: str, *, db: Any) -> SkillDefinition:
        definition = self.load(skill_id)
        execution.active_skill = skill_id
        await db.commit()
        return definition

    def evaluate_completion(self, skill_id: str, *, metadata: dict[str, Any],
                            criterion_results: dict[str, bool]) -> SkillCompletionReport:
        definition = self.load(skill_id)
        expected = definition.completion.criteria
        unknown = sorted(set(criterion_results) - set(expected))
        if unknown:
            raise ValueError(f"Skill completion 包含未知 criteria: {unknown}")
        evaluations = [
            SkillCriterionEvaluation(criterion=criterion, passed=criterion_results.get(criterion) is True)
            for criterion in expected
        ]
        missing = [
            key for key in definition.completion.required_metadata
            if metadata.get(key) is None or metadata.get(key) == "" or metadata.get(key) == []
        ]
        return SkillCompletionReport(
            skill_id=definition.id,
            skill_version=definition.version,
            passed=all(item.passed for item in evaluations) and not missing,
            criteria=evaluations,
            missing_metadata=missing,
            metadata=definition.completion_metadata(metadata),
        )

    def assert_budget(self, skill_id: str, *, tool_calls: int, external_searches: int = 0,
                      papers_read: int = 0) -> None:
        budget = self.load(skill_id).budget
        if tool_calls >= budget.max_tool_calls:
            raise RuntimeError("SKILL_TOOL_BUDGET_EXCEEDED")
        if external_searches >= budget.max_external_searches and budget.max_external_searches:
            raise RuntimeError("SKILL_EXTERNAL_SEARCH_BUDGET_EXCEEDED")
        if papers_read >= budget.max_papers_to_read and budget.max_papers_to_read:
            raise RuntimeError("SKILL_PAPER_BUDGET_EXCEEDED")

    async def execute(self, tool_runtime: ToolRuntime, skill_id: str, tool_name: str,
                      arguments: dict[str, Any], context: ToolContext, *, confirmed: bool = False,
                      idempotency_key: str | None = None) -> ToolResult:
        """Enforce the skill boundary before entering the shared ToolRuntime."""
        definition = self.load(skill_id)
        if tool_name not in definition.allowed_tools:
            return ToolResult(ok=False, summary="该 Skill 不允许调用此工具", error_code="SKILL_TOOL_FORBIDDEN")
        execution = await context.db.get(AgentExecution, context.execution_id)
        if execution is None:
            return ToolResult(ok=False, summary="执行不存在", error_code="EXECUTION_NOT_FOUND")
        try:
            self.assert_budget(skill_id, tool_calls=execution.tool_call_count)
        except RuntimeError as exc:
            return ToolResult(ok=False, summary="Skill 预算已耗尽", error_code=str(exc))
        execution.active_skill = skill_id
        await context.db.commit()
        return await tool_runtime.execute(tool_name, arguments, context, confirmed=confirmed,
                                          idempotency_key=idempotency_key)
