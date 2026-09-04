"""Application boundary for durable agent executions and public events."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import AgentEvent, AgentExecution, TERMINAL_EXECUTION_STATUSES
from app.application.writing_service import WritingGenerationProposal
from app.redis_client import get_async_redis, get_json, set_json

EVENT_STREAM_PREFIX = "paperai:execution-events:"
CONTROL_PREFIX = "paperai:execution-control:"
CHECKPOINT_PREFIX = "paperai:execution-checkpoint:"
CHECKPOINT_TTL_SECONDS = 86400


class CompletionGateError(ValueError):
    """Raised when a workflow result does not satisfy its deterministic contract."""


def validate_writing_completion(
    execution: AgentExecution,
    proposal: WritingGenerationProposal,
    skill_completion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected_document_id = str((execution.input_payload or {}).get("document_id") or "")
    failures: list[str] = []
    if proposal.project_id != execution.project_id:
        failures.append("project_mismatch")
    if proposal.document_id != expected_document_id:
        failures.append("document_mismatch")
    if proposal.kind != "generate":
        failures.append("invalid_kind")
    if not proposal.content.strip() or len([part for part in proposal.content.split("\n\n") if part.strip()]) != 1:
        failures.append("invalid_paragraph")
    if not proposal.citations:
        failures.append("missing_citations")
    citation_ids = {(item.citation_key, item.paper_id, item.evidence_id) for item in proposal.citations}
    if len(citation_ids) != len(proposal.citations) or any(not all(parts) for parts in citation_ids):
        failures.append("invalid_citation_mapping")
    if proposal.status == "verification_failed" or any(item.status == "unsupported" for item in proposal.citations):
        failures.append("unsupported_citation")
    if proposal.review is None or proposal.review.repair_count > 1:
        failures.append("writing_review_incomplete")
    if execution.active_skill != "writing_evidence_generation":
        failures.append("writing_skill_not_active")
    if not skill_completion or skill_completion.get("passed") is not True:
        failures.append("skill_completion_failed")
    if failures:
        raise CompletionGateError(",".join(failures))
    return {
        "passed": True,
        "proposal_status": proposal.status,
        "citation_count": len(proposal.citations),
        "verified_count": sum(item.status == "verified" for item in proposal.citations),
        "weak_count": sum(item.status == "weak" for item in proposal.citations),
        "checks": [
            "project_and_document_owned_context",
            "single_paragraph_output",
            "structured_citation_mapping",
            "no_unsupported_citations",
            "skill_completion_passed",
        ],
    }


def execution_dict(item: AgentExecution) -> dict[str, Any]:
    return {column.name: (value.isoformat() if isinstance(value, datetime) else value)
            for column in item.__table__.columns for value in [getattr(item, column.name)]}


def event_envelope(item: AgentEvent) -> dict[str, Any]:
    return {
        "id": item.id, "seq": item.seq, "execution_id": item.execution_id,
        "type": item.event_type, "timestamp": item.created_at.isoformat(),
        "stage": item.stage, "message": item.message, "data": item.payload or {},
    }


def execution_trace_report(execution: AgentExecution, events: list[AgentEvent]) -> dict[str, Any]:
    """Build a deterministic, privacy-safe trace from durable execution state."""
    ordered = sorted(events, key=lambda item: (item.seq, item.created_at))
    spans: list[dict[str, Any]] = []
    for index, event in enumerate(ordered):
        end = ordered[index + 1].created_at if index + 1 < len(ordered) else (
            execution.completed_at or execution.updated_at or event.created_at
        )
        duration_ms = max(0, round((end - event.created_at).total_seconds() * 1000, 3))
        spans.append({
            "seq": event.seq,
            "name": event.event_type,
            "stage": event.stage,
            "started_at": event.created_at.isoformat(),
            "duration_ms": duration_ms,
            "outcome": "error" if event.event_type in {"execution_failed", "completion_gate_failed"} else "ok",
        })

    started_at = execution.started_at or (ordered[0].created_at if ordered else execution.created_at)
    ended_at = execution.completed_at or execution.updated_at
    total_ms = max(0, round((ended_at - started_at).total_seconds() * 1000, 3)) if started_at and ended_at else None
    input_payload = execution.input_payload or {}
    proposal = (execution.result_payload or {}).get("proposal") or {}
    completion = (execution.result_payload or {}).get("completion") or {}
    skill_completion = (execution.result_payload or {}).get("skill_completion") or {}
    citations = proposal.get("citations") or []
    return {
        "trace_id": execution.id,
        "execution_id": execution.id,
        "project_id": execution.project_id,
        "agent_type": execution.agent_type,
        "runtime_version": execution.runtime_version,
        "status": execution.status,
        "current_stage": execution.current_stage,
        "started_at": started_at.isoformat() if started_at else None,
        "ended_at": ended_at.isoformat() if ended_at else None,
        "total_ms": total_ms,
        "input_summary": {
            "document_id": input_payload.get("document_id"),
            "section_depth": len(input_payload.get("section_path") or []),
            "has_nearby_context": bool(input_payload.get("nearby_text")),
            "citation_style": input_payload.get("citation_style"),
        },
        "budget": {
            "tool_calls": {"used": execution.tool_call_count, "limit": execution.max_tool_calls},
            "model_calls": {"used": execution.model_call_count, "limit": execution.max_model_calls},
            "tokens": {"input": execution.input_tokens, "output": execution.output_tokens, "limit": execution.max_tokens},
            "seconds_limit": execution.max_seconds,
        },
        "quality": {
            "completion_gate_passed": completion.get("passed") is True,
            "proposal_status": completion.get("proposal_status") or proposal.get("status"),
            "citation_count": completion.get("citation_count", len(citations)),
            "verified_count": completion.get("verified_count", sum(item.get("status") == "verified" for item in citations)),
            "weak_count": completion.get("weak_count", sum(item.get("status") == "weak" for item in citations)),
            "unsupported_count": sum(item.get("status") == "unsupported" for item in citations),
            "checks": completion.get("checks") or [],
            "skill_id": skill_completion.get("skill_id") or execution.active_skill,
            "skill_completion_passed": skill_completion.get("passed") is True,
            "reviewer_status": (proposal.get("review") or {}).get("status"),
            "repair_count": (proposal.get("review") or {}).get("repair_count", 0),
        },
        "control_transitions": [
            {"seq": event.seq, "type": event.event_type, "timestamp": event.created_at.isoformat()}
            for event in ordered
            if event.event_type in {"execution_paused", "execution_resumed", "execution_cancelled"}
        ],
        "spans": spans,
        "error": {"code": execution.error_code, "message": execution.error_message} if execution.error_code else None,
    }


def evaluate_execution_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Score a trace with deterministic gates; never calls a model or provider."""
    status = str(trace.get("status") or "")
    quality = dict(trace.get("quality") or {})
    budget = dict(trace.get("budget") or {})
    spans = list(trace.get("spans") or [])
    stage_names = {str(item.get("stage") or item.get("name") or "") for item in spans}
    required_stages = {"context_started", "context_ready", "generation_started", "citation_verified", "completion_gate"}

    checks: list[dict[str, Any]] = []

    def add(name: str, earned: int, maximum: int, detail: str) -> None:
        checks.append({"name": name, "passed": earned == maximum, "earned": earned, "maximum": maximum, "detail": detail})

    add("terminal_success", 20 if status == "completed" else 0, 20, f"execution_status={status or 'unknown'}")
    gate_passed = quality.get("completion_gate_passed") is True
    add("completion_gate", 30 if gate_passed else 0, 30, "passed" if gate_passed else "not_passed")

    unsupported = int(quality.get("unsupported_count") or 0)
    weak = int(quality.get("weak_count") or 0)
    citations = int(quality.get("citation_count") or 0)
    citation_score = 25 if citations > 0 and unsupported == 0 and weak == 0 else (
        18 if citations > 0 and unsupported == 0 else 0
    )
    add("citation_support", citation_score, 25,
        f"citations={citations},weak={weak},unsupported={unsupported}")

    missing_stages = sorted(required_stages - stage_names)
    add("trace_completeness", 10 if not missing_stages else 0, 10,
        "complete" if not missing_stages else f"missing={','.join(missing_stages)}")

    tool_budget = dict(budget.get("tool_calls") or {})
    model_budget = dict(budget.get("model_calls") or {})
    token_budget = dict(budget.get("tokens") or {})
    within_budget = (
        int(tool_budget.get("used") or 0) <= int(tool_budget.get("limit") or 0)
        and int(model_budget.get("used") or 0) <= int(model_budget.get("limit") or 0)
        and int(token_budget.get("input") or 0) + int(token_budget.get("output") or 0) <= int(token_budget.get("limit") or 0)
    )
    add("budget_compliance", 10 if within_budget else 0, 10, "within_limits" if within_budget else "limit_exceeded")

    valid_latency = trace.get("total_ms") is not None and float(trace["total_ms"]) >= 0 and all(
        float(item.get("duration_ms") or 0) >= 0 for item in spans
    )
    add("latency_integrity", 5 if valid_latency else 0, 5, "valid" if valid_latency else "invalid_or_missing")

    score = sum(item["earned"] for item in checks)
    interrupted = status in {"queued", "running", "waiting_user", "paused", "cancelled"}
    critical_passed = status == "completed" and gate_passed and citations > 0 and unsupported == 0 and within_budget
    verdict = "incomplete" if interrupted else ("pass" if critical_passed and score >= 80 else "fail")
    return {
        "evaluation_version": "writing_execution_v1",
        "trace_id": trace.get("trace_id"),
        "verdict": verdict,
        "score": score,
        "maximum_score": 100,
        "critical_passed": critical_passed,
        "checks": checks,
    }


async def append_event(db: AsyncSession, execution: AgentExecution, event_type: str, message: str,
                       *, stage: str | None = None, title: str | None = None,
                       data: dict[str, Any] | None = None) -> AgentEvent:
    """Commit to PostgreSQL first, then mirror the public envelope to Redis."""
    # Serialize sequence allocation per execution across API and worker processes.
    await db.execute(select(AgentExecution.id).where(AgentExecution.id == execution.id).with_for_update())
    last_seq = await db.scalar(select(func.max(AgentEvent.seq)).where(AgentEvent.execution_id == execution.id))
    event = AgentEvent(execution_id=execution.id, seq=int(last_seq or 0) + 1, event_type=event_type,
                       stage=stage, title=title, message=message, payload=data or {})
    db.add(event)
    await db.commit()
    await db.refresh(event)
    envelope = event_envelope(event)
    try:
        await get_async_redis().xadd(f"{EVENT_STREAM_PREFIX}{execution.id}", {"event": json.dumps(envelope, ensure_ascii=False)}, maxlen=1000)
    except Exception:
        # Redis is an acceleration layer; durable replay remains available from SQL.
        pass
    return event


async def set_status(db: AsyncSession, execution: AgentExecution, status: str, *, stage: str | None = None,
                     error_code: str | None = None, error_message: str | None = None) -> None:
    now = datetime.utcnow()
    execution.status = status
    execution.current_stage = stage if stage is not None else execution.current_stage
    execution.updated_at = now
    execution.error_code = error_code
    execution.error_message = error_message
    if status == "running" and execution.started_at is None:
        execution.started_at = now
    if status in TERMINAL_EXECUTION_STATUSES:
        execution.completed_at = now
    await db.commit()


async def set_control(execution_id: str, action: str | None) -> None:
    key = f"{CONTROL_PREFIX}{execution_id}"
    if action:
        await get_async_redis().set(key, action, ex=86400)
    else:
        await get_async_redis().delete(key)


async def get_control(execution_id: str) -> str | None:
    return await get_async_redis().get(f"{CONTROL_PREFIX}{execution_id}")


async def save_checkpoint(execution_id: str, payload: dict[str, Any]) -> bool:
    return await set_json(f"{CHECKPOINT_PREFIX}{execution_id}", payload, CHECKPOINT_TTL_SECONDS)


async def load_checkpoint(execution_id: str) -> dict[str, Any] | None:
    payload = await get_json(f"{CHECKPOINT_PREFIX}{execution_id}")
    return dict(payload) if isinstance(payload, dict) else None


async def delete_checkpoint(execution_id: str) -> None:
    try:
        await get_async_redis().delete(f"{CHECKPOINT_PREFIX}{execution_id}")
    except Exception:
        pass
