"""对话历史和缓存 API 模块"""
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Any, AsyncIterator, Optional
from datetime import datetime
from dataclasses import dataclass, field
import asyncio
import hashlib
import json
import logging
import re
import time
import uuid

from app.database import get_db
from app.models.chat import ChatSession, ChatMessage, SummaryCache, InterpretCache
from app.models.paper import Paper, Section
from app.api.dependencies import get_current_user_id
from app.application.project_execution_entrypoint import classify_instant_interaction
from app.agent.summarizer.graph import run_summarizer_agent
from app.harness.agents.interpret_agent import run_interpret_agent
from app.config import settings
from app.job_queue import enqueue_job
from app.redis_client import get_async_redis, get_json, set_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat")


@dataclass
class _AnswerTask:
    task_id: str
    session_id: str
    user_id: str
    question: str
    enable_thinking: bool = False
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    # 项目对话模式:非空时 worker 会把 project_id 透传给 stream_lead_agent
    project_id: str = ""
    status: str = "running"
    stage: str = "queued"
    stage_message: str = "正在准备回答"
    answer: str = ""
    reasoning: str = ""
    reasoning_done: bool = False
    citations: list = field(default_factory=list)
    result: dict = field(default_factory=dict)
    error: str = ""
    updated_at: float = field(default_factory=time.time)


_answer_tasks: dict[str, _AnswerTask] = {}
_answer_task_handles: dict[str, asyncio.Task] = {}
_ANSWER_TASK_PREFIX = "paperai:answer-task:"
_ANSWER_DEDUPE_PREFIX = "paperai:answer-dedupe:"


def _fallback_session_title(question: str) -> str:
    """从问题文本生成简短会话标题(截断 + 去空白)。"""
    text = (question or "").strip().replace("\n", " ")
    if not text:
        return "新对话"
    return text[:30] + ("…" if len(text) > 30 else "")


def _answer_task_key(task_id: str) -> str:
    return f"{_ANSWER_TASK_PREFIX}{task_id}"


def _answer_dedupe_key(task: _AnswerTask) -> str:
    identity = "\0".join([
        task.user_id,
        task.session_id,
        task.question,
        "1" if task.enable_thinking else "0",
        task.project_id or "",
    ])
    return f"{_ANSWER_DEDUPE_PREFIX}{hashlib.sha256(identity.encode()).hexdigest()}"


def _answer_task_data(task: _AnswerTask) -> dict:
    return {
        "task_id": task.task_id,
        "session_id": task.session_id,
        "user_id": task.user_id,
        "question": task.question,
        "enable_thinking": task.enable_thinking,
        "trace_id": task.trace_id,
        "project_id": task.project_id,
        "status": task.status,
        "stage": task.stage,
        "stage_message": task.stage_message,
        "answer": task.answer,
        "reasoning": task.reasoning,
        "reasoning_done": task.reasoning_done,
        "citations": task.citations,
        "result": task.result,
        "error": task.error,
        "updated_at": task.updated_at,
    }


def _answer_task_from_data(data: dict) -> Optional[_AnswerTask]:
    try:
        return _AnswerTask(
            task_id=str(data["task_id"]),
            session_id=str(data["session_id"]),
            user_id=str(data["user_id"]),
            question=str(data["question"]),
            enable_thinking=bool(data.get("enable_thinking", False)),
            trace_id=str(data.get("trace_id") or data["task_id"]),
            project_id=str(data.get("project_id") or ""),
            status=str(data.get("status", "failed")),
            stage=str(data.get("stage", "failed")),
            stage_message=str(data.get("stage_message", "")),
            answer=str(data.get("answer", "")),
            reasoning=str(data.get("reasoning", "")),
            reasoning_done=bool(data.get("reasoning_done", False)),
            citations=list(data.get("citations") or []),
            result=dict(data.get("result") or {}),
            error=str(data.get("error", "")),
            updated_at=float(data.get("updated_at", time.time())),
        )
    except (KeyError, TypeError, ValueError):
        logger.warning("忽略无效 Redis 回答任务数据", exc_info=True)
        return None


async def _save_answer_task(task: _AnswerTask) -> None:
    task.updated_at = time.time()
    await set_json(
        _answer_task_key(task.task_id),
        _answer_task_data(task),
        settings.REDIS_ANSWER_TASK_TTL_SECONDS,
    )


async def _load_answer_task(task_id: str) -> Optional[_AnswerTask]:
    local = _answer_tasks.get(task_id)
    if local is not None and task_id in _answer_task_handles:
        return local
    data = await get_json(_answer_task_key(task_id))
    task = _answer_task_from_data(data) if isinstance(data, dict) else None
    if task is not None:
        # The LLM request itself cannot survive a backend process restart.
        if (
            task.status == "running"
            and task_id not in _answer_task_handles
            and time.time() - task.updated_at > settings.LLM_TIMEOUT_SECONDS + 30
        ):
            task.status = "failed"
            task.stage = "failed"
            task.stage_message = "生成进程已中断"
            task.error = "后端服务重启导致生成中断，请重新生成"
            await _save_answer_task(task)
        _answer_tasks[task_id] = task
    return task


def _decode_sse_event(block: str) -> tuple[str, dict]:
    event = "message"
    data_lines: list[str] = []
    for line in block.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    return event, json.loads("\n".join(data_lines) or "{}")


async def _consume_answer_events(
    task: _AnswerTask,
    source: AsyncIterator[str],
) -> None:
    """Compatibility consumer for in-process event producers.

    Production answers are normally consumed by the queue worker now.  Keeping
    this small adapter makes the resumable stream contract reusable by tests and
    by deployments that still execute an answer producer in the API process.
    """
    last_persisted_at = 0.0
    try:
        async for block in source:
            event, payload = _decode_sse_event(block)
            if event == "status":
                task.stage = payload.get("stage", task.stage)
                task.stage_message = payload.get("message", task.stage_message)
            elif event == "answer_delta":
                task.answer += payload.get("text", "")
            elif event == "reasoning_delta":
                task.reasoning += payload.get("text", "")
            elif event == "reasoning_done":
                task.reasoning_done = True
            elif event == "citations":
                task.citations = payload.get("items", [])
            elif event == "done":
                task.result = payload
                task.status = "completed"
                task.stage = "completed"
                task.stage_message = "回答完成"
            elif event == "error":
                task.status = "failed"
                task.error = payload.get("message", "回答生成失败")

            now = time.monotonic()
            if event not in {"answer_delta", "reasoning_delta"} or now - last_persisted_at >= 0.2:
                await _save_answer_task(task)
                last_persisted_at = now
        if task.status == "running":
            task.status = "failed"
            task.error = f"{task.stage_message}时连接意外结束"
            await _save_answer_task(task)
    except asyncio.CancelledError:
        task.status = "stopped"
        task.stage = "stopped"
        task.stage_message = "回答已停止"
        await _save_answer_task(task)
    except Exception:
        logger.exception("后台回答任务异常 task_id=%s", task.task_id)
        task.status = "failed"
        task.error = f"{task.stage_message}时发生异常"
        await _save_answer_task(task)
    finally:
        _answer_task_handles.pop(task.task_id, None)
        try:
            await get_async_redis().delete(_answer_dedupe_key(task))
        except Exception:
            logger.warning("Redis 回答任务锁清理失败 task_id=%s", task.task_id)


async def _stream_answer_task(
    task: _AnswerTask,
    offset: int = 0,
    reasoning_offset: int = 0,
) -> AsyncIterator[str]:
    sent = max(0, min(offset, len(task.answer)))
    reasoning_sent = max(0, min(reasoning_offset, len(task.reasoning)))
    reasoning_done_sent = False
    last_stage = ""
    yield _sse_event("task", {
        "task_id": task.task_id,
        "trace_id": task.trace_id,
        "question": task.question,
        "status": task.status,
        "answer_length": len(task.answer),
        "reasoning_length": len(task.reasoning),
        "enable_thinking": task.enable_thinking,
    })
    while True:
        if task.task_id not in _answer_task_handles:
            stored = await get_json(_answer_task_key(task.task_id))
            refreshed = _answer_task_from_data(stored) if isinstance(stored, dict) else None
            if refreshed is not None:
                task.status = refreshed.status
                task.stage = refreshed.stage
                task.stage_message = refreshed.stage_message
                task.answer = refreshed.answer
                task.reasoning = refreshed.reasoning
                task.reasoning_done = refreshed.reasoning_done
                task.citations = refreshed.citations
                task.result = refreshed.result
                task.error = refreshed.error
                task.updated_at = refreshed.updated_at
                if (
                    task.status == "running"
                    and time.time() - task.updated_at > settings.LLM_TIMEOUT_SECONDS + 30
                ):
                    task.status = "failed"
                    task.stage = "failed"
                    task.stage_message = "生成进程已中断"
                    task.error = "回答任务长时间没有更新，请重新生成"
                    await _save_answer_task(task)
        if task.stage != last_stage:
            last_stage = task.stage
            yield _sse_event("status", {
                "stage": task.stage,
                "message": task.stage_message,
            })
        if reasoning_sent < len(task.reasoning):
            reasoning_delta = task.reasoning[reasoning_sent:]
            reasoning_sent = len(task.reasoning)
            yield _sse_event("reasoning_delta", {"text": reasoning_delta})
        if task.reasoning_done and not reasoning_done_sent:
            reasoning_done_sent = True
            yield _sse_event("reasoning_done", {})
        if sent < len(task.answer):
            delta = task.answer[sent:]
            sent = len(task.answer)
            yield _sse_event("answer_delta", {"text": delta})

        if task.status == "completed":
            yield _sse_event("citations", {"items": task.citations})
            yield _sse_event("done", task.result)
            return
        if task.status == "stopped":
            yield _sse_event("stopped", {
                "message": "回答已停止",
                "answer_length": len(task.answer),
            })
            return
        if task.status == "failed":
            yield _sse_event("error", {
                "stage": task.stage,
                "message": task.error or f"{task.stage_message}失败",
            })
            return
        await asyncio.sleep(0.06)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _streaming_prompt(question: str, chunks: list, history_context: str) -> str:
    """Backward-compatible prompt helper retained for tests and extensions.

    Answer execution now lives in the harness agent, but callers that used the
    former chat helper should continue to receive the canonical grounded prompt.
    """
    from app.agent.qa_agent.workflow import build_answer_prompt

    return build_answer_prompt(question, chunks, history_context)


def _citations_from_streamed_answer(answer: str, chunks: list) -> list:
    """Build deterministic citations through the shared QA helper."""
    from app.utils.qa_helpers import build_deterministic_citations

    return build_deterministic_citations(answer, chunks)


# ==================== 对话会话管理 ====================

@router.get("/recent-messages")
async def list_recent_messages(
    limit: int = Query(5, ge=1, le=20),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Return recent persisted QA turns across the user's sessions."""
    user_id = await get_current_user_id(authorization, db)
    # LEFT JOIN Paper:项目模式 session.paper_id 可能为 NULL,但仍需返回消息
    result = await db.execute(
        select(ChatMessage, ChatSession, Paper)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .outerjoin(Paper, ChatSession.paper_id == Paper.id)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    return {
        "items": [{
            "id": message.id,
            "session_id": session.id,
            "paper_id": paper.id if paper else None,
            "paper_title": paper.title if paper else None,
            "project_id": session.project_id,
            "question": message.question,
            "answer_preview": re.sub(r"\s+", " ", message.answer or "")[:160],
            "created_at": message.created_at.isoformat() if message.created_at else None,
        } for message, session, paper in result.all()]
    }


@router.get("/sessions")
async def list_sessions(
    paper_id: Optional[str] = None,
    project_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的对话会话列表(可按 paper_id 或 project_id 过滤)"""
    user_id = await get_current_user_id(authorization, db)

    query = select(ChatSession).filter(ChatSession.user_id == user_id)
    if paper_id:
        query = query.filter(ChatSession.paper_id == paper_id)
    if project_id:
        query = query.filter(ChatSession.project_id == project_id)

    query = query.order_by(ChatSession.updated_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    sessions = result.scalars().all()

    # 使用子查询获取消息数量，避免延迟加载问题
    session_ids = [s.id for s in sessions]
    message_counts = {}
    if session_ids:
        count_result = await db.execute(
            select(ChatMessage.session_id, func.count(ChatMessage.id))
            .where(ChatMessage.session_id.in_(session_ids))
            .group_by(ChatMessage.session_id)
        )
        for sid, cnt in count_result:
            message_counts[sid] = cnt

    return {
        "items": [
            {
                "id": s.id,
                "paper_id": s.paper_id,
                "project_id": s.project_id,
                "title": s.title,
                "message_count": message_counts.get(s.id, 0),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None
            }
            for s in sessions
        ],
        "total": len(sessions)
    }


@router.post("/sessions")
async def create_session(
    data: dict,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """创建新的对话会话。

    支持两种模式:
    - 单论文模式:传 paper_id(向后兼容)
    - 项目模式:传 project_id(可选同时传 paper_id 作占位;若不传,worker 会从项目文档库选一篇)
    """
    user_id = await get_current_user_id(authorization, db)

    paper_id = data.get("paper_id") or ""
    project_id = data.get("project_id") or ""

    if not paper_id and not project_id:
        raise HTTPException(status_code=400, detail="paper_id 和 project_id 至少传一个")

    # 校验 paper_id(若提供)
    if paper_id:
        result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
        paper = result.scalar_one_or_none()
        if not paper:
            raise HTTPException(status_code=404, detail="论文不存在")

    # 校验 project_id(若提供)
    if project_id:
        from app.models.project import ResearchProject
        proj = await db.get(ResearchProject, project_id)
        if proj is None or proj.user_id != user_id:
            raise HTTPException(status_code=404, detail="项目不存在或无访问权限")

    title = data.get("title", "新对话")

    session = ChatSession(
        user_id=user_id,
        paper_id=paper_id or None,
        project_id=project_id or None,
        title=title
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        "id": session.id,
        "paper_id": session.paper_id,
        "project_id": session.project_id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """删除对话会话及其所有消息"""
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    await db.delete(session)
    await db.commit()
    
    return {"message": "删除成功"}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """获取会话中的所有消息"""
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.order_index)
    )
    messages = messages_result.scalars().all()
    
    return {
        "session_id": session_id,
        "title": session.title,
        "paper_id": session.paper_id,
        "project_id": session.project_id,
        "messages": [
            {
                "id": m.id,
                "order_index": m.order_index,
                "question": m.question,
                "answer": m.answer,
                "citations": m.citations,
                "follow_up_questions": m.follow_up_questions,
                "confidence": m.confidence,
                "confidence_type": "legacy_mixed",
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    }


@router.delete("/sessions/{session_id}/messages/{message_id}")
async def delete_session_message(
    session_id: str,
    message_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Delete one persisted question-answer turn owned by the current user."""
    user_id = await get_current_user_id(authorization, db)
    session_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    message_result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.id == message_id,
            ChatMessage.session_id == session_id,
        )
    )
    message = message_result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="问答记录不存在")

    await db.delete(message)
    await db.flush()
    remaining_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.order_index, ChatMessage.created_at)
    )
    remaining = list(remaining_result.scalars().all())
    for order_index, item in enumerate(remaining, start=1):
        item.order_index = order_index
    session.title = (
        _fallback_session_title(remaining[0].question)
        if remaining
        else "新对话"
    )
    session.updated_at = datetime.utcnow()
    await db.commit()
    return {
        "message": "问答记录已删除",
        "message_id": message_id,
        "remaining_count": len(remaining),
    }


# ==================== 对话问答（带历史记忆） ====================

@router.post("/sessions/{session_id}/ask")
async def ask_in_session(
    session_id: str,
    data: dict,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """在指定会话中提问，AI 会参考历史对话"""
    user_id = await get_current_user_id(authorization, db)
    
    # 验证会话
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    question = str(data.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    # 从 session 读取 project_id(项目模式),透传给 worker
    project_id = str(session.project_id) if getattr(session, "project_id", None) else ""
    if getattr(session, "paper_id", None) and not project_id:
        classify_instant_interaction("paper_chat")
    task = _AnswerTask(
        task_id=str(uuid.uuid4()),
        session_id=session_id,
        user_id=user_id,
        question=question,
        enable_thinking=bool(data.get("enable_thinking", False)),
        project_id=project_id,
    )
    _answer_tasks[task.task_id] = task
    await _save_answer_task(task)
    await enqueue_job(
        "chat_answer",
        {
            "task_id": task.task_id,
            "session_id": session_id,
            "user_id": user_id,
            "question": question,
            "enable_thinking": task.enable_thinking,
            "trace_id": task.trace_id,
            "project_id": project_id,
        },
        job_id=task.task_id,
    )
    deadline = time.monotonic() + settings.LLM_TIMEOUT_SECONDS + 60
    while task.status == "running" and time.monotonic() < deadline:
        await asyncio.sleep(0.1)
        refreshed = await _load_answer_task(task.task_id)
        if refreshed is not None:
            task = refreshed
    if task.status == "failed":
        raise HTTPException(status_code=500, detail=task.error or "回答处理失败")
    if task.status != "completed":
        raise HTTPException(status_code=504, detail="回答仍在后台生成，请稍后查看")
    result_payload = task.result or {}
    return {
        "answer": task.answer,
        "intent": result_payload.get("intent", "general"),
        "sources": result_payload.get("sources", []),
        "citations": task.citations,
        "follow_up_questions": [],
        "follow_up_pending": True,
        "title_pending": False,
        "intent_confidence": 1.0 if result_payload.get("intent") == "metadata" else 0.8,
        "evidence_confidence": result_payload.get("evidence_confidence", 0.0),
        "confidence": result_payload.get("evidence_confidence", 0.0),
        "confidence_type": "evidence_support",
        "message_id": result_payload.get("message_id", ""),
        "nodes": result_payload.get("nodes", []),
        "trace_id": task.trace_id,
        "trace": result_payload.get("trace", {}),
    }


@router.post("/sessions/{session_id}/ask/stream")
async def stream_ask_in_session(
    session_id: str,
    data: dict,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Stream an answer over SSE, then persist the completed message."""
    user_id = await get_current_user_id(authorization, db)
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    question = str(data.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    enable_thinking = bool(data.get("enable_thinking", False))
    # 从 session 读取 project_id(项目模式),透传给 worker
    project_id = str(session.project_id) if getattr(session, "project_id", None) else ""
    if getattr(session, "paper_id", None) and not project_id:
        classify_instant_interaction("paper_chat")

    active_task = next(
        (
            task for task in _answer_tasks.values()
            if task.session_id == session_id
            and task.user_id == user_id
            and task.question == question
            and task.enable_thinking == enable_thinking
            and task.project_id == project_id
            and task.status == "running"
        ),
        None,
    )
    if active_task is None:
        if len(_answer_tasks) >= 200:
            removable = next(
                (key for key, task in _answer_tasks.items() if task.status != "running"),
                None,
            )
            if removable:
                _answer_tasks.pop(removable, None)
        candidate = _AnswerTask(
            task_id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            question=question,
            enable_thinking=enable_thinking,
            project_id=project_id,
        )
        active_task = candidate
        try:
            redis_client = get_async_redis()
            dedupe_key = _answer_dedupe_key(candidate)
            claimed = await redis_client.set(
                dedupe_key,
                candidate.task_id,
                nx=True,
                ex=settings.REDIS_ANSWER_TASK_TTL_SECONDS,
            )
            if not claimed:
                existing_id = await redis_client.get(dedupe_key)
                existing = await _load_answer_task(existing_id) if existing_id else None
                if existing is not None and existing.status == "running":
                    active_task = existing
                else:
                    await redis_client.set(
                        dedupe_key,
                        candidate.task_id,
                        ex=settings.REDIS_ANSWER_TASK_TTL_SECONDS,
                    )
        except Exception:
            logger.warning("Redis 防重复锁不可用，使用进程内防重复")

    if active_task.task_id not in _answer_tasks:
        _answer_tasks[active_task.task_id] = active_task
        await _save_answer_task(active_task)
        try:
            await enqueue_job(
                "chat_answer",
                {
                    "task_id": active_task.task_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "question": question,
                    "enable_thinking": enable_thinking,
                    "trace_id": active_task.trace_id,
                    "project_id": project_id,
                    "dedupe_key": _answer_dedupe_key(active_task),
                },
                job_id=active_task.task_id,
            )
            active_task.stage = "queued"
            active_task.stage_message = "已进入回答队列"
            await _save_answer_task(active_task)
        except Exception:
            logger.exception("回答任务入队失败 task_id=%s", active_task.task_id)
            active_task.status = "failed"
            active_task.stage = "queue"
            active_task.stage_message = "任务入队失败"
            active_task.error = "回答 Worker 暂时不可用，请稍后重试"
            await _save_answer_task(active_task)

    return StreamingResponse(
        _stream_answer_task(active_task),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Chat-Task-Id": active_task.task_id,
            "X-Trace-Id": active_task.trace_id,
        },
    )


@router.get("/answer-tasks/{task_id}")
async def get_answer_task(
    task_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    task = await _load_answer_task(task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="回答任务不存在或已过期")
    return {
        "task_id": task.task_id,
        "trace_id": task.trace_id,
        "session_id": task.session_id,
        "question": task.question,
        "enable_thinking": task.enable_thinking,
        "status": task.status,
        "stage": task.stage,
        "message": task.stage_message,
        "answer": task.answer,
        "reasoning": task.reasoning,
        "reasoning_done": task.reasoning_done,
        "citations": task.citations,
        "result": task.result,
        "error": task.error,
    }


@router.get("/answer-tasks/{task_id}/trace")
async def get_answer_trace(
    task_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    task = await _load_answer_task(task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="回答任务不存在或已过期")
    trace = await get_json(f"paperai:answer-trace:{task.trace_id}")
    if not isinstance(trace, dict):
        trace = dict(task.result.get("trace") or {})
    if not trace:
        return {
            "trace_id": task.trace_id,
            "task_id": task.task_id,
            "status": task.status,
            "stage": task.stage,
            "metrics_pending": task.status == "running",
        }
    return trace


@router.get("/answer-tasks/{task_id}/stream")
async def resume_answer_task(
    task_id: str,
    offset: int = Query(0, ge=0),
    reasoning_offset: int = Query(0, ge=0),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    task = await _load_answer_task(task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="回答任务不存在或已过期")
    return StreamingResponse(
        _stream_answer_task(task, offset, reasoning_offset),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Chat-Task-Id": task.task_id,
            "X-Trace-Id": task.trace_id,
        },
    )


@router.post("/answer-tasks/{task_id}/stop")
async def stop_answer_task(
    task_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    task = await _load_answer_task(task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="回答任务不存在或已过期")
    handle = _answer_task_handles.get(task_id)
    if handle and not handle.done():
        handle.cancel()
    elif task.status == "running":
        task.status = "stopped"
        task.stage = "stopped"
        task.stage_message = "回答已停止"
        await _save_answer_task(task)
        await get_async_redis().set(
            f"paperai:answer-cancel:{task_id}",
            "1",
            ex=settings.REDIS_ANSWER_TASK_TTL_SECONDS,
        )
    return {"task_id": task_id, "status": "stopping"}


# ==================== 摘要缓存 ====================

@router.get("/papers/{paper_id}/summary")
async def get_summary_cache(
    paper_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """获取缓存的结构化摘要"""
    user_id = await get_current_user_id(authorization, db)
    
    result = await db.execute(
        select(SummaryCache).where(
            SummaryCache.paper_id == paper_id,
            SummaryCache.user_id == user_id
        )
    )
    cache = result.scalar_one_or_none()
    
    if not cache:
        return {
            "paper_id": paper_id,
            "cached": False,
            "message": "尚未生成摘要，请调用 POST /summarize 生成"
        }
    
    return {
        "paper_id": paper_id,
        "cached": True,
        "overview": cache.overview,
        "methodology": cache.methodology,
        "experiments": cache.experiments,
        "contributions": cache.contributions,
        "generated_at": cache.generated_at.isoformat() if cache.generated_at else None,
        "updated_at": cache.updated_at.isoformat() if cache.updated_at else None
    }


@router.post("/papers/{paper_id}/summarize")
async def generate_summary(
    paper_id: str,
    data: dict = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """生成或重新生成结构化摘要（带缓存）"""
    user_id = await get_current_user_id(authorization, db)
    classify_instant_interaction("paper_summary")
    
    # 验证论文
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    # 获取章节数据
    sections_result = await db.execute(
        select(Section).where(Section.paper_id == paper_id).order_by(Section.order_index)
    )
    sections = sections_result.scalars().all()
    
    if sections:
        sections_data = [
            {"title": s.section_title, "content": s.content or "", "order_index": s.order_index}
            for s in sections
        ]
    elif paper.full_text:
        paragraphs = [p.strip() for p in paper.full_text.split('\n\n') if p.strip()]
        sections_data = [
            {"title": f"段落 {i+1}", "content": p, "order_index": i}
            for i, p in enumerate(paragraphs[:100])
        ]
    else:
        raise HTTPException(status_code=400, detail="论文内容为空")
    
    # 运行摘要 Agent
    summary_result = await run_summarizer_agent(paper_id, sections_data)
    
    # 更新或创建缓存
    cache_result = await db.execute(
        select(SummaryCache).where(
            SummaryCache.paper_id == paper_id,
            SummaryCache.user_id == user_id
        )
    )
    cache = cache_result.scalar_one_or_none()
    
    if cache:
        cache.overview = summary_result.get("overview", {})
        cache.methodology = summary_result.get("methodology", {})
        cache.experiments = summary_result.get("experiments", {})
        cache.contributions = summary_result.get("contributions", {})
    else:
        cache = SummaryCache(
            user_id=user_id,
            paper_id=paper_id,
            overview=summary_result.get("overview", {}),
            methodology=summary_result.get("methodology", {}),
            experiments=summary_result.get("experiments", {}),
            contributions=summary_result.get("contributions", {})
        )
        db.add(cache)
    
    await db.commit()
    
    return {
        "paper_id": paper_id,
        "cached": True,
        "overview": summary_result.get("overview", {}),
        "methodology": summary_result.get("methodology", {}),
        "experiments": summary_result.get("experiments", {}),
        "contributions": summary_result.get("contributions", {}),
        "message": "摘要已生成并缓存"
    }


# ==================== 解读缓存 ====================

@router.get("/papers/{paper_id}/interpret/{interpret_type}")
async def get_interpret_cache(
    paper_id: str,
    interpret_type: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """获取缓存的深度解读结果"""
    user_id = await get_current_user_id(authorization, db)
    
    if interpret_type not in ("concept", "compare", "key_info"):
        raise HTTPException(status_code=400, detail="无效的解读类型")
    
    result = await db.execute(
        select(InterpretCache).where(
            InterpretCache.paper_id == paper_id,
            InterpretCache.user_id == user_id,
            InterpretCache.interpret_type == interpret_type
        )
    )
    cache = result.scalar_one_or_none()
    
    if not cache:
        return {
            "paper_id": paper_id,
            "type": interpret_type,
            "cached": False,
            "message": f"尚未生成{interpret_type}解读，请调用 POST /interpret 生成"
        }
    
    return {
        "paper_id": paper_id,
        "type": interpret_type,
        "cached": True,
        "data": cache.data,
        "generated_at": cache.generated_at.isoformat() if cache.generated_at else None,
        "updated_at": cache.updated_at.isoformat() if cache.updated_at else None
    }


@router.post("/papers/{paper_id}/interpret/{interpret_type}")
async def generate_interpret(
    paper_id: str,
    interpret_type: str,
    data: dict = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """生成或重新生成深度解读(带缓存)。
    
    底层通过 harness 层的 interpret_agent 执行:
    - 复用 paper_internal skill 的 search_paper_content / lookup_table_data tools
    - agent 产出带 [S1][S2] 引用的结构化 JSON,经 build_deterministic_citations 生成可点击 citations
    - 返回结构与旧版兼容:{paper_id, type, cached, data, message},并额外附加 citations/chunks/agent_trace
    """
    user_id = await get_current_user_id(authorization, db)
    classify_instant_interaction("paper_interpretation")

    if interpret_type not in ("concept", "compare", "key_info"):
        raise HTTPException(status_code=400, detail="无效的解读类型")
    
    # 验证论文
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")

    # 通过 harness/interpret_agent 生成结构化解读(复用 paper_internal tools + citations)
    try:
        import uuid as _uuid
        request_id = (data or {}).get("request_id") or _uuid.uuid4().hex
        interpret_result = await run_interpret_agent(
            db=db,
            paper_id=paper_id,
            interpret_type=interpret_type,
            user_id=user_id,
            request_id=request_id,
        )
    except Exception as e:
        logger.exception("interpret agent 执行失败")
        raise HTTPException(status_code=500, detail=f"解读失败: {type(e).__name__}: {e}")

    if not interpret_result.success or not interpret_result.data:
        raise HTTPException(
            status_code=500,
            detail=f"解读失败: {interpret_result.failure_reason or 'agent 未产出有效结果'}",
        )

    result_data = interpret_result.data

    # 更新或创建缓存(与旧路径兼容:InterpretCache.data 存同一字典结构)
    cache_result = await db.execute(
        select(InterpretCache).where(
            InterpretCache.paper_id == paper_id,
            InterpretCache.user_id == user_id,
            InterpretCache.interpret_type == interpret_type
        )
    )
    cache = cache_result.scalar_one_or_none()
    if cache:
        cache.data = result_data
    else:
        cache = InterpretCache(
            user_id=user_id,
            paper_id=paper_id,
            interpret_type=interpret_type,
            data=result_data,
        )
        db.add(cache)
    await db.commit()

    # 返回结构:与旧路径完全兼容 + 附加 harness 增强字段(citations/chunks/agent_trace)
    resp: dict[str, Any] = {
        "paper_id": paper_id,
        "type": interpret_type,
        "cached": True,
        "data": result_data,
        "message": "解读已生成并缓存",
        # === harness 增强:带引用 ===
        "citations": interpret_result.citations,
        "chunks": interpret_result.chunks,
        "agent_trace": {
            "iterations": interpret_result.trace.iterations,
            "tool_calls": interpret_result.trace.tool_calls,
            "total_ms": interpret_result.trace.total_ms,
            "success": interpret_result.success,
            "llm_calls": interpret_result.trace.llm_calls,
            "input_tokens": interpret_result.trace.input_tokens,
            "output_tokens": interpret_result.trace.output_tokens,
            "total_tokens": interpret_result.trace.total_tokens,
        },
    }
    return resp
