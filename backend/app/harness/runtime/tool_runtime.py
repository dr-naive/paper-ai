"""Uniform, traced, cancellable runtime for atomic agent tools."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.execution_service import get_control
from app.models.execution import AgentExecution, ToolCall

SideEffect = Literal["read", "write", "network", "destructive"]
ToolHandler = Callable[["ToolContext", BaseModel], Awaitable["ToolResult"]]


class ToolResult(BaseModel):
    ok: bool
    summary: str
    data: dict | list | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    retryable: bool = False
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    description: str
    side_effect: SideEffect
    requires_confirmation: bool
    timeout_seconds: int
    idempotent: bool
    input_schema: type[BaseModel]


@dataclass(frozen=True)
class ToolContext:
    db: AsyncSession
    user_id: str
    execution_id: str
    project_id: str | None = None


class ToolRuntime:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, ToolHandler]] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.name in self._tools:
            raise ValueError(f"重复 Tool: {spec.name}")
        self._tools[spec.name] = (spec, handler)

    def specs(self) -> list[ToolSpec]:
        return [item[0] for item in self._tools.values()]

    def get_spec(self, name: str) -> ToolSpec | None:
        item = self._tools.get(name)
        return item[0] if item else None

    async def execute(self, name: str, arguments: dict[str, Any], context: ToolContext,
                      *, confirmed: bool = False, idempotency_key: str | None = None) -> ToolResult:
        registered = self._tools.get(name)
        if registered is None:
            return ToolResult(ok=False, summary="工具不存在", error_code="TOOL_NOT_FOUND", error_message=name)
        spec, handler = registered
        execution = await context.db.get(AgentExecution, context.execution_id)
        if execution is None or execution.user_id != context.user_id or execution.project_id != context.project_id:
            return ToolResult(ok=False, summary="执行上下文无权调用该工具", error_code="TOOL_CONTEXT_FORBIDDEN")
        if spec.requires_confirmation and not confirmed:
            return ToolResult(ok=False, summary="该操作需要用户确认", error_code="TOOL_CONFIRMATION_REQUIRED")
        if await get_control(context.execution_id) == "cancel":
            return ToolResult(ok=False, summary="执行已取消", error_code="EXECUTION_CANCELLED")
        try:
            validated = spec.input_schema.model_validate(arguments)
        except ValidationError as exc:
            return ToolResult(ok=False, summary="工具参数无效", error_code="TOOL_INPUT_INVALID", error_message=str(exc))

        trace = ToolCall(
            execution_id=context.execution_id,
            step_index=execution.tool_call_count + 1,
            tool_name=spec.name,
            tool_version=spec.version,
            arguments=validated.model_dump(mode="json"),
            side_effect_level=spec.side_effect,
            status="running",
            idempotency_key=idempotency_key or (str(uuid.uuid4()) if not spec.idempotent else None),
        )
        context.db.add(trace)
        execution.tool_call_count += 1
        await context.db.commit()
        try:
            result = await asyncio.wait_for(handler(context, validated), timeout=spec.timeout_seconds)
        except asyncio.TimeoutError:
            result = ToolResult(ok=False, summary="工具执行超时", retryable=True, error_code="TOOL_TIMEOUT")
        except Exception as exc:
            result = ToolResult(ok=False, summary="工具执行失败", error_code="TOOL_EXECUTION_FAILED", error_message=str(exc))
        trace.status = "completed" if result.ok else "failed"
        trace.result_summary = result.summary
        trace.result_payload = result.data
        trace.error_code = result.error_code
        trace.error_message = result.error_message
        trace.completed_at = datetime.utcnow()
        await context.db.commit()
        return result
