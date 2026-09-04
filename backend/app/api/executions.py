"""Authenticated v2 agent execution API with durable SSE replay."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_id
from app.application.execution_service import append_event, event_envelope, execution_dict, set_control, set_status
from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.job_queue import enqueue_job
from app.models.execution import AgentEvent, AgentExecution, TERMINAL_EXECUTION_STATUSES
from app.models.project import ResearchProject

router = APIRouter(prefix="/api/v1", tags=["agent-executions"])


async def current_user_id(authorization: str | None = Header(None), db: AsyncSession = Depends(get_db)) -> str:
    return await get_current_user_id(authorization, db)


class ExecutionCreate(BaseModel):
    agent_type: str = Field(default="mock_agent", min_length=1, max_length=80)
    goal: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = None
    max_tool_calls: int = Field(default=30, ge=0, le=1000)
    max_model_calls: int = Field(default=20, ge=0, le=1000)
    max_tokens: int = Field(default=100000, ge=1)
    max_seconds: int = Field(default=1800, ge=1, le=86400)


def require_runtime() -> None:
    if not settings.ENABLE_AGENT_RUNTIME_V2:
        raise HTTPException(status_code=404, detail={"code": "AGENT_RUNTIME_DISABLED", "message": "Agent Runtime V2 未启用"})


async def owned_execution(db: AsyncSession, execution_id: str, user_id: str) -> AgentExecution:
    item = (await db.execute(select(AgentExecution).where(AgentExecution.id == execution_id,
                                                          AgentExecution.user_id == user_id))).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "EXECUTION_NOT_FOUND", "message": "执行不存在"})
    return item


@router.post("/projects/{project_id}/executions", status_code=202)
async def create_execution(project_id: str, body: ExecutionCreate, db: AsyncSession = Depends(get_db),
                           user_id: str = Depends(current_user_id)):
    require_runtime()
    project = (await db.execute(select(ResearchProject).where(ResearchProject.id == project_id,
                                                               ResearchProject.user_id == user_id))).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    item = AgentExecution(user_id=user_id, project_id=project_id, agent_type=body.agent_type, goal=body.goal,
                          conversation_id=body.conversation_id, max_tool_calls=body.max_tool_calls,
                          max_model_calls=body.max_model_calls, max_tokens=body.max_tokens,
                          max_seconds=body.max_seconds)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    await append_event(db, item, "execution_queued", "执行已进入队列", stage="queued")
    await enqueue_job("agent_execution_v2", {"execution_id": item.id}, job_id=item.id)
    return execution_dict(item)


@router.get("/projects/{project_id}/executions")
async def list_project_executions(project_id: str, limit: int = Query(50, ge=1, le=200),
                                  db: AsyncSession = Depends(get_db), user_id: str = Depends(current_user_id)):
    require_runtime()
    project = (await db.execute(select(ResearchProject).where(ResearchProject.id == project_id,
                                                               ResearchProject.user_id == user_id))).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    rows = (await db.execute(select(AgentExecution).where(AgentExecution.project_id == project_id,
                                                           AgentExecution.user_id == user_id)
                             .order_by(AgentExecution.created_at.desc()).limit(limit))).scalars().all()
    return {"items": [execution_dict(row) for row in rows]}


@router.get("/executions")
async def list_user_executions(limit: int = Query(100, ge=1, le=200),
                               db: AsyncSession = Depends(get_db), user_id: str = Depends(current_user_id)):
    """Restore the authenticated user's global task center from durable state."""
    require_runtime()
    rows = (await db.execute(select(AgentExecution).where(AgentExecution.user_id == user_id)
                             .order_by(AgentExecution.updated_at.desc()).limit(limit))).scalars().all()
    return {"items": [execution_dict(row) for row in rows]}


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str, db: AsyncSession = Depends(get_db),
                        user_id: str = Depends(current_user_id)):
    require_runtime()
    return execution_dict(await owned_execution(db, execution_id, user_id))


@router.get("/executions/{execution_id}/events")
async def get_events(execution_id: str, after: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000),
                     db: AsyncSession = Depends(get_db), user_id: str = Depends(current_user_id)):
    require_runtime()
    await owned_execution(db, execution_id, user_id)
    rows = (await db.execute(select(AgentEvent).where(AgentEvent.execution_id == execution_id,
                                                       AgentEvent.seq > after).order_by(AgentEvent.seq).limit(limit))).scalars().all()
    return {"items": [event_envelope(row) for row in rows]}


@router.get("/executions/{execution_id}/stream")
async def stream_events(execution_id: str, after: int = Query(0, ge=0), db: AsyncSession = Depends(get_db),
                        user_id: str = Depends(current_user_id)):
    require_runtime()
    await owned_execution(db, execution_id, user_id)

    async def generate():
        cursor = after
        while True:
            async with AsyncSessionLocal() as session:
                rows = (await session.execute(select(AgentEvent).where(AgentEvent.execution_id == execution_id,
                                                                        AgentEvent.seq > cursor)
                                              .order_by(AgentEvent.seq).limit(200))).scalars().all()
                status = await session.scalar(select(AgentExecution.status).where(AgentExecution.id == execution_id))
            for row in rows:
                cursor = row.seq
                yield f"id: {row.seq}\nevent: {row.event_type}\ndata: {json.dumps(event_envelope(row), ensure_ascii=False)}\n\n"
            if status in TERMINAL_EXECUTION_STATUSES and not rows:
                break
            if not rows:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


async def control(execution_id: str, action: str, db: AsyncSession, user_id: str) -> dict[str, Any]:
    require_runtime()
    item = await owned_execution(db, execution_id, user_id)
    if item.status in TERMINAL_EXECUTION_STATUSES:
        raise HTTPException(status_code=409, detail={"code": "EXECUTION_TERMINAL", "message": "执行已经结束"})
    if action == "cancel":
        await set_control(item.id, "cancel")
        if item.status == "queued":
            await set_status(db, item, "cancelled", stage="cancelled", error_code="EXECUTION_CANCELLED", error_message="用户取消")
            await append_event(db, item, "execution_cancelled", "执行已取消", stage="cancelled")
    elif action == "pause":
        await set_control(item.id, "pause")
        await set_status(db, item, "paused", stage=item.current_stage)
        await append_event(db, item, "execution_paused", "执行已暂停", stage=item.current_stage)
    elif action in {"resume", "approve"}:
        if action == "approve" and item.status != "waiting_user":
            raise HTTPException(status_code=409, detail={"code": "APPROVAL_NOT_REQUIRED", "message": "当前执行不等待审批"})
        await set_control(item.id, None)
        await set_status(db, item, "queued")
        await append_event(db, item, f"execution_{action}d", "执行已恢复" if action == "resume" else "审批已通过")
        await enqueue_job("agent_execution_v2", {"execution_id": item.id}, job_id=item.id)
    return execution_dict(item)


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(current_user_id)):
    return await control(execution_id, "cancel", db, user_id)

@router.post("/executions/{execution_id}/pause")
async def pause_execution(execution_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(current_user_id)):
    return await control(execution_id, "pause", db, user_id)

@router.post("/executions/{execution_id}/resume")
async def resume_execution(execution_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(current_user_id)):
    return await control(execution_id, "resume", db, user_id)

@router.post("/executions/{execution_id}/approve")
async def approve_execution(execution_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(current_user_id)):
    return await control(execution_id, "approve", db, user_id)
