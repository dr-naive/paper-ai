"""对话历史和缓存 API 模块"""
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Any, AsyncIterator, Optional
from datetime import datetime
from dataclasses import dataclass, field
import asyncio
import json
import logging
import re
import uuid

from app.database import AsyncSessionLocal, get_db
from app.models.chat import ChatSession, ChatMessage, SummaryCache, InterpretCache
from app.models.paper import Paper, Section
from app.api.auth import decode_token
from app.api.dependencies import get_current_user_id
from app.agent.qa_agent.enhanced_graph import (
    build_deterministic_citations,
    calculate_evidence_confidence,
    detect_metadata_intent,
    generate_follow_up_questions,
    run_enhanced_qa_agent,
)
from app.agent.summarizer.graph import run_summarizer_agent
from app.rag.knowledge_base import get_knowledge_base
from app.rag.table_retrieval import get_exact_table_chunks, merge_retrieval_chunks
from app.llm.client import get_llm_client
from app.utils.background_tasks import spawn_background_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat")


@dataclass
class _AnswerTask:
    task_id: str
    session_id: str
    user_id: str
    question: str
    enable_thinking: bool = False
    status: str = "running"
    stage: str = "queued"
    stage_message: str = "正在准备回答"
    answer: str = ""
    reasoning: str = ""
    reasoning_done: bool = False
    citations: list = field(default_factory=list)
    result: dict = field(default_factory=dict)
    error: str = ""


_answer_tasks: dict[str, _AnswerTask] = {}
_answer_task_handles: dict[str, asyncio.Task] = {}


def _decode_sse_event(block: str) -> tuple[str, dict]:
    event = "message"
    data_lines = []
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
    try:
        async for block in source:
            event, payload = _decode_sse_event(block)
            if event == "status":
                task.stage = payload.get("stage", task.stage)
                task.stage_message = payload.get("message", task.stage_message)
                if task.stage == "organizing_citations":
                    # Keep this short stage observable without delaying generation.
                    await asyncio.sleep(0.12)
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
        if task.status == "running":
            task.status = "failed"
            task.error = f"{task.stage_message}时连接意外结束"
    except asyncio.CancelledError:
        task.status = "stopped"
        task.stage = "stopped"
        task.stage_message = "回答已停止"
    except Exception:
        logger.exception("后台回答任务异常 task_id=%s", task.task_id)
        task.status = "failed"
        task.error = f"{task.stage_message}时发生异常"
    finally:
        _answer_task_handles.pop(task.task_id, None)


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
        "question": task.question,
        "status": task.status,
        "answer_length": len(task.answer),
        "reasoning_length": len(task.reasoning),
        "enable_thinking": task.enable_thinking,
    })
    while True:
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
    context_parts = []
    for index, chunk in enumerate(chunks):
        table_label = "[表格]\n" if chunk.get("chunk_type") == "table" else ""
        context_parts.append(
            f"[来源 S{index + 1}]\n"
            f"[章节 {chunk.get('section', '未知章节')}]\n"
            f"{table_label}{chunk.get('content', '')}"
        )
    context = "\n\n---\n\n".join(context_parts)
    history = (
        f"\n【历史对话】\n{history_context}\n"
        if history_context else ""
    )
    return f"""
请只依据下方论文资料回答用户问题。

要求：
1. 推理过程和最终回答均使用简体中文。专业术语、模型名称、变量、公式和通用缩写可保留英文；英文术语首次出现时，适合的情况下补充中文含义。
2. 即使用户问题、历史对话或论文资料包含英文，也不要因此切换为整段英文推理或回答。
3. 直接输出 Markdown 正文，不要输出 JSON，不要写“答案：”。
4. 回答准确、有条理；论文未提及时明确说明，不得自行补全。
5. 每个关键结论后必须标注对应来源编号，如 [S1]、[S2]；只能使用已提供的来源编号。
6. 段落之间空一行，并列内容分行；比较数据适合时使用 Markdown 表格。
7. 表格数据必须逐项核对，缺失值写“-”，不要推测。
{history}
【用户问题】
{question}

【论文资料】
{context}
""".strip()


def _citations_from_streamed_answer(answer: str, chunks: list) -> list:
    return build_deterministic_citations(answer, chunks)


def _fallback_session_title(question: str) -> str:
    return question[:20] + ("..." if len(question) > 20 else "")


async def _generate_followups_background(
    message_id: str,
    question: str,
    answer: str,
    intent: str = "general",
) -> None:
    """Generate follow-up questions after the main answer has been returned."""
    try:
        followups = await asyncio.wait_for(
            generate_follow_up_questions(question, answer or "", intent or "general"),
            timeout=25,
        )
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
            message = result.scalar_one_or_none()
            if not message:
                return
            message.follow_up_questions = followups
            await db.commit()
        logger.info("后台追问生成完成 message_id=%s count=%d", message_id, len(followups))
    except Exception as e:
        logger.error("后台追问生成失败 message_id=%s: %s", message_id, e)


async def _generate_title_background(session_id: str, question: str, answer: str) -> None:
    """Generate a concise session title without blocking the answer response."""
    try:
        title = _fallback_session_title(question)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
            session = result.scalar_one_or_none()
            if not session:
                return
            session.title = title
            session.updated_at = datetime.utcnow()
            await db.commit()
        logger.info("后台会话标题生成完成 session_id=%s title=%s", session_id, title)
    except Exception as e:
        logger.error("后台会话标题生成失败 session_id=%s: %s", session_id, e)


# ==================== 对话会话管理 ====================

@router.get("/sessions")
async def list_sessions(
    paper_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的对话会话列表"""
    user_id = await get_current_user_id(authorization, db)
    
    query = select(ChatSession).filter(ChatSession.user_id == user_id)
    if paper_id:
        query = query.filter(ChatSession.paper_id == paper_id)
    
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
    """创建新的对话会话"""
    user_id = await get_current_user_id(authorization, db)
    
    paper_id = data.get("paper_id")
    if not paper_id:
        raise HTTPException(status_code=400, detail="paper_id 不能为空")
    
    # 验证论文存在且属于该用户
    result = await db.execute(select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    title = data.get("title", "新对话")
    
    session = ChatSession(
        user_id=user_id,
        paper_id=paper_id,
        title=title
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return {
        "id": session.id,
        "paper_id": session.paper_id,
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
    
    question = data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    
    paper_id = session.paper_id
    metadata_field = detect_metadata_intent(question)
    
    # 获取历史消息作为上下文
    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.order_index)
    )
    history_messages = messages_result.scalars().all()
    
    # 获取论文信息
    paper_result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = paper_result.scalar_one_or_none()
    
    # RAG 检索。元数据类问题可以直接用数据库字段回答，不需要向量检索。
    if metadata_field:
        chunks = []
    else:
        kb = get_knowledge_base()
        exact_table_chunks = await get_exact_table_chunks(db, paper_id, question)
        semantic_chunks = await kb.query(paper_id, question, top_k=5)
        chunks = merge_retrieval_chunks(exact_table_chunks, semantic_chunks, top_k=5)
    
    # 构建历史对话上下文
    history_context = ""
    if history_messages:
        history_parts = []
        for msg in history_messages[-5:]:  # 最近 5 轮对话
            history_parts.append(f"用户: {msg.question}\nAI: {msg.answer}")
        history_context = "\n\n".join(history_parts)
    
    # 构建论文元数据
    paper_metadata = {
        "title": paper.title if paper else "",
        "authors": paper.authors if paper else "",
        "abstract": paper.abstract if paper else "",
        "keywords": paper.keywords or [] if paper else [],
        "venue": getattr(paper, "venue", "") if paper else "",
        "publication_year": getattr(paper, "publication_year", "") if paper else "",
        "doi": getattr(paper, "doi", "") if paper else "",
    }
    
    # 使用增强版问答 Agent；追问后台生成，避免阻塞主回答。
    qa_result = await run_enhanced_qa_agent(
        paper_id,
        question,
        chunks,
        paper_metadata,
        history_context,
        generate_follow_up=False
    )
    
    # 保存消息
    msg_count = await db.execute(select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session_id))
    order_index = msg_count.scalar() or 0
    
    message = ChatMessage(
        session_id=session_id,
        order_index=order_index + 1,
        question=question,
        answer=qa_result.get('answer'),
        citations=qa_result.get('citations', []),
        follow_up_questions=[],
        confidence=qa_result.get('evidence_confidence')
    )
    db.add(message)
    if order_index == 0:
        session.title = _fallback_session_title(question)

    await db.flush()
    message_id = str(message.id)
    await db.commit()

    answer = qa_result.get("answer") or ""
    intent = qa_result.get("intent") or "general"
    asyncio.create_task(_generate_followups_background(message_id, question, answer, intent))
    
    return {
        "answer": qa_result.get("answer"),
        "intent": qa_result.get("intent"),
        "sources": qa_result.get("sources", []),
        "citations": qa_result.get("citations", []),
        "follow_up_questions": [],
        "follow_up_pending": True,
        "title_pending": False,
        "intent_confidence": qa_result.get("intent_confidence", 0.0),
        "evidence_confidence": qa_result.get("evidence_confidence", 0.0),
        "confidence": qa_result.get("evidence_confidence", 0.0),
        "confidence_type": "evidence_support",
        "message_id": message_id
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
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="会话不存在")

    question = str(data.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    enable_thinking = bool(data.get("enable_thinking", False))

    async def event_stream():
        current_stage = "retrieving"
        try:
            yield _sse_event("status", {
                "stage": "retrieving",
                "message": "正在检索论文",
            })

            async with AsyncSessionLocal() as stream_db:
                session_result = await stream_db.execute(
                    select(ChatSession).where(
                        ChatSession.id == session_id,
                        ChatSession.user_id == user_id,
                    )
                )
                session = session_result.scalar_one_or_none()
                if not session:
                    yield _sse_event("error", {"message": "会话不存在"})
                    return

                paper_result = await stream_db.execute(
                    select(Paper).where(Paper.id == session.paper_id)
                )
                paper = paper_result.scalar_one_or_none()
                if not paper:
                    yield _sse_event("error", {"message": "论文不存在"})
                    return

                history_result = await stream_db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .order_by(ChatMessage.order_index)
                )
                history_messages = history_result.scalars().all()
                history_context = "\n\n".join(
                    f"用户: {message.question}\nAI: {message.answer}"
                    for message in history_messages[-5:]
                )

                metadata_field = detect_metadata_intent(question)
                if metadata_field:
                    metadata_text = "\n".join([
                        f"标题：{paper.title or '-'}",
                        f"作者：{paper.authors or '-'}",
                        f"摘要：{paper.abstract or '-'}",
                        f"关键词：{'、'.join(paper.keywords or []) or '-'}",
                        f"期刊或会议：{getattr(paper, 'venue', '') or '-'}",
                        f"发表年份：{getattr(paper, 'publication_year', '') or '-'}",
                        f"DOI：{getattr(paper, 'doi', '') or '-'}",
                    ])
                    chunks = [{
                        "section": "论文元数据",
                        "content": metadata_text,
                        "chunk_type": "metadata",
                    }]
                    intent = "metadata"
                else:
                    knowledge_base = get_knowledge_base()
                    exact_chunks = await get_exact_table_chunks(
                        stream_db, session.paper_id, question
                    )
                    semantic_chunks = await knowledge_base.query(
                        session.paper_id, question, top_k=5
                    )
                    chunks = merge_retrieval_chunks(
                        exact_chunks, semantic_chunks, top_k=5
                    )
                    intent = "general"

                if not chunks:
                    answer = "未在论文中找到相关内容，请尝试换一种问法。"
                    yield _sse_event("answer_delta", {"text": answer})
                    citations = []
                else:
                    current_stage = "generating"
                    yield _sse_event("status", {
                        "stage": "generating",
                        "message": "正在组织回答",
                        "source_count": len(chunks),
                    })
                    prompt = _streaming_prompt(question, chunks, history_context)
                    answer_parts = []
                    llm = get_llm_client()
                    reasoning_started = False
                    reasoning_finished = False
                    async for content_kind, delta in llm.astream_content(
                        prompt,
                        enable_thinking=enable_thinking,
                    ):
                        if content_kind == "reasoning":
                            reasoning_started = True
                            yield _sse_event("reasoning_delta", {"text": delta})
                            continue
                        if reasoning_started and not reasoning_finished:
                            reasoning_finished = True
                            yield _sse_event("reasoning_done", {})
                        answer_parts.append(delta)
                        yield _sse_event("answer_delta", {"text": delta})
                    if reasoning_started and not reasoning_finished:
                        yield _sse_event("reasoning_done", {})
                    answer = "".join(answer_parts).strip()
                    if not answer:
                        raise RuntimeError("模型未返回回答内容")
                    current_stage = "organizing_citations"
                    yield _sse_event("status", {
                        "stage": "organizing_citations",
                        "message": "正在整理引用",
                    })
                    citations = _citations_from_streamed_answer(answer, chunks)

                evidence_confidence = calculate_evidence_confidence(
                    answer, citations, chunks, intent
                )
                message_count = await stream_db.execute(
                    select(func.count())
                    .select_from(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                )
                order_index = message_count.scalar() or 0
                message = ChatMessage(
                    session_id=session_id,
                    order_index=order_index + 1,
                    question=question,
                    answer=answer,
                    citations=citations,
                    follow_up_questions=[],
                    confidence=evidence_confidence,
                )
                stream_db.add(message)
                if order_index == 0:
                    session.title = _fallback_session_title(question)
                    session.updated_at = datetime.utcnow()
                await stream_db.flush()
                message_id = str(message.id)
                await stream_db.commit()

            yield _sse_event("citations", {"items": citations})
            yield _sse_event("done", {
                "message_id": message_id,
                "intent": intent,
                "sources": [item.get("section", "") for item in citations],
                "evidence_confidence": evidence_confidence,
                "confidence": evidence_confidence,
                "confidence_type": "evidence_support",
                "follow_up_pending": True,
            })
            asyncio.create_task(
                _generate_followups_background(
                    message_id, question, answer, intent
                )
            )
        except asyncio.CancelledError:
            logger.info("客户端取消流式回答 session_id=%s", session_id)
            raise
        except Exception:
            logger.exception("流式回答失败 session_id=%s", session_id)
            stage_messages = {
                "retrieving": "检索论文失败",
                "generating": "生成回答失败",
                "organizing_citations": "整理引用失败",
            }
            yield _sse_event("error", {
                "stage": current_stage,
                "message": stage_messages.get(current_stage, "回答生成失败"),
            })

    active_task = next(
        (
            task for task in _answer_tasks.values()
            if task.session_id == session_id
            and task.user_id == user_id
            and task.question == question
            and task.enable_thinking == enable_thinking
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
        active_task = _AnswerTask(
            task_id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            question=question,
            enable_thinking=enable_thinking,
        )
        _answer_tasks[active_task.task_id] = active_task
        handle = spawn_background_task(
            _consume_answer_events(active_task, event_stream()),
            name=f"chat-answer-{active_task.task_id}",
        )
        _answer_task_handles[active_task.task_id] = handle

    return StreamingResponse(
        _stream_answer_task(active_task),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Chat-Task-Id": active_task.task_id,
        },
    )


@router.get("/answer-tasks/{task_id}")
async def get_answer_task(
    task_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    task = _answer_tasks.get(task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="回答任务不存在或已过期")
    return {
        "task_id": task.task_id,
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


@router.get("/answer-tasks/{task_id}/stream")
async def resume_answer_task(
    task_id: str,
    offset: int = Query(0, ge=0),
    reasoning_offset: int = Query(0, ge=0),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    task = _answer_tasks.get(task_id)
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
        },
    )


@router.post("/answer-tasks/{task_id}/stop")
async def stop_answer_task(
    task_id: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(authorization, db)
    task = _answer_tasks.get(task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="回答任务不存在或已过期")
    handle = _answer_task_handles.get(task_id)
    if handle and not handle.done():
        handle.cancel()
    elif task.status == "running":
        task.status = "stopped"
        task.stage = "stopped"
        task.stage_message = "回答已停止"
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
    """生成或重新生成深度解读（带缓存）"""
    user_id = await get_current_user_id(authorization, db)
    
    if interpret_type not in ("concept", "compare", "key_info"):
        raise HTTPException(status_code=400, detail="无效的解读类型")
    
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
    
    sections_data = []
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
    
    if not sections_data:
        raise HTTPException(status_code=400, detail="论文内容为空")
    
    import json
    llm = get_llm_client()
    text = "\n\n".join([f"## {s['title']}\n{s['content'][:2000]}" for s in sections_data[:10]])
    
    prompts = {
        "concept": f"""
        请分析以下论文内容，提取并解释其中的关键概念和技术术语。
        
        返回 JSON 格式：
        {{
            "concepts": [
                {{"name": "概念名称", "explanation": "通俗解释（100字以内）", "context": "在论文中的作用"}}
            ]
        }}
        
        论文内容：
        {text[:8000]}
        """,
        "compare": f"""
        请分析以下论文内容，对比论文中提到的不同方法、模型或实验设置。
        
        返回 JSON 格式：
        {{
            "comparisons": [
                {{"item_a": "方法A", "item_b": "方法B", "difference": "主要差异", "advantage": "各自优势"}}
            ]
        }}
        
        论文内容：
        {text[:8000]}
        """,
        "key_info": f"""
        请分析以下论文内容，提取最关键的信息点。
        
        返回 JSON 格式：
        {{
            "key_formulas": ["关键公式或算法描述"],
            "key_figures": ["关键图表说明"],
            "key_findings": ["关键发现"],
            "takeaways": ["值得关注的要点"]
        }}
        
        论文内容：
        {text[:8000]}
        """
    }
    
    prompt = prompts.get(interpret_type, prompts["concept"])
    
    try:
        response = await llm.agenerate([prompt], json_mode=True, enable_thinking=False)
        text_result = response.generations[0][0].text.strip()
        if "```json" in text_result:
            text_result = text_result.split("```json")[1].split("```")[0]
        result_data = json.loads(text_result.strip())
        
        # 更新或创建缓存
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
                data=result_data
            )
            db.add(cache)
        
        await db.commit()
        
        return {
            "paper_id": paper_id,
            "type": interpret_type,
            "cached": True,
            "data": result_data,
            "message": "解读已生成并缓存"
        }
    except Exception as e:
        logger.error(f"❌ 深度解读失败：{e}")
        raise HTTPException(status_code=500, detail=f"解读失败：{str(e)}")
