"""Application boundary for durable agent executions and public events."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import AgentEvent, AgentExecution, TERMINAL_EXECUTION_STATUSES
from app.redis_client import get_async_redis

EVENT_STREAM_PREFIX = "paperai:execution-events:"
CONTROL_PREFIX = "paperai:execution-control:"


def execution_dict(item: AgentExecution) -> dict[str, Any]:
    return {column.name: (value.isoformat() if isinstance(value, datetime) else value)
            for column in item.__table__.columns for value in [getattr(item, column.name)]}


def event_envelope(item: AgentEvent) -> dict[str, Any]:
    return {
        "id": item.id, "seq": item.seq, "execution_id": item.execution_id,
        "type": item.event_type, "timestamp": item.created_at.isoformat(),
        "stage": item.stage, "message": item.message, "data": item.payload or {},
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
