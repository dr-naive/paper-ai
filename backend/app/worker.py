"""Independent Redis worker for chat generation and paper processing."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
from typing import Any

from sqlalchemy import select

from app.agent.qa_agent.enhanced_graph import generate_follow_up_questions
from app.agent.qa_agent.workflow import QAWorkflowState, UnifiedQAWorkflow
from app.config import settings
from app.database import AsyncSessionLocal, close_db, init_db
from app.job_queue import (
    WorkerJob,
    acknowledge_job,
    fail_or_retry_job,
    recover_processing_jobs,
    reserve_job,
)
from app.models.chat import ChatMessage
from app.redis_client import close_redis, get_async_redis, initialize_redis, set_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ANSWER_TASK_PREFIX = "paperai:answer-task:"
ANSWER_CANCEL_PREFIX = "paperai:answer-cancel:"
WORKER_HEARTBEAT_KEY = "paperai:worker:heartbeat"
ANSWER_TRACE_PREFIX = "paperai:answer-trace:"


async def _load_answer_data(task_id: str) -> dict[str, Any]:
    raw = await get_async_redis().get(f"{ANSWER_TASK_PREFIX}{task_id}")
    if not raw:
        raise LookupError(f"回答任务不存在 task_id={task_id}")
    import json
    return dict(json.loads(raw))


async def _save_answer_data(task_id: str, data: dict[str, Any]) -> None:
    data["updated_at"] = time.time()
    await set_json(
        f"{ANSWER_TASK_PREFIX}{task_id}",
        data,
        settings.REDIS_ANSWER_TASK_TTL_SECONDS,
    )


async def _answer_cancelled(task_id: str) -> bool:
    return bool(await get_async_redis().exists(f"{ANSWER_CANCEL_PREFIX}{task_id}"))


async def _generate_followups(message_id: str, question: str, answer: str, intent: str) -> None:
    try:
        questions = await generate_follow_up_questions(question, answer, intent)
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
            message = result.scalar_one_or_none()
            if message is not None:
                message.follow_up_questions = questions
                await db.commit()
    except Exception:
        logger.exception("Worker 生成追问失败 message_id=%s", message_id)


async def handle_chat_answer(job: WorkerJob) -> None:
    job_started_at = time.perf_counter()
    payload = job.payload
    task_id = str(payload["task_id"])
    task_data = await _load_answer_data(task_id)
    state = QAWorkflowState(
        session_id=str(payload["session_id"]),
        user_id=str(payload["user_id"]),
        question=str(payload["question"]),
        enable_thinking=bool(payload.get("enable_thinking", False)),
        trace_id=str(payload.get("trace_id") or task_data.get("trace_id") or task_id),
    )
    state.trace["retry_count"] = job.attempts
    last_saved = 0.0
    try:
        async with AsyncSessionLocal() as db:
            workflow = UnifiedQAWorkflow(state, db)
            async for event, event_payload in workflow.stream():
                if await _answer_cancelled(task_id):
                    task_data.update({
                        "status": "stopped",
                        "stage": "stopped",
                        "stage_message": "回答已停止",
                    })
                    await _save_answer_data(task_id, task_data)
                    return
                if event == "status":
                    task_data["stage"] = event_payload.get("stage", task_data.get("stage"))
                    task_data["stage_message"] = event_payload.get("message", "")
                elif event == "reasoning_delta":
                    task_data["reasoning"] = str(task_data.get("reasoning", "")) + str(
                        event_payload.get("text", "")
                    )
                elif event == "reasoning_done":
                    task_data["reasoning_done"] = True
                elif event == "answer_delta":
                    task_data["answer"] = str(task_data.get("answer", "")) + str(
                        event_payload.get("text", "")
                    )
                elif event == "citations":
                    task_data["citations"] = event_payload.get("items", [])
                elif event == "done":
                    task_data.update({
                        "status": "completed",
                        "stage": "completed",
                        "stage_message": "回答完成",
                        "result": event_payload,
                        "trace_id": state.trace_id,
                    })
                elif event == "error":
                    task_data.update({
                        "status": "failed",
                        "stage": event_payload.get("stage", "workflow"),
                        "stage_message": "回答失败",
                        "error": event_payload.get("message", "回答处理失败"),
                    })
                now = time.monotonic()
                if event not in {"answer_delta", "reasoning_delta"} or now - last_saved >= 0.2:
                    await _save_answer_data(task_id, task_data)
                    last_saved = now
        await _save_answer_data(task_id, task_data)
        if state.message_id:
            await _generate_followups(
                state.message_id,
                state.question,
                state.answer,
                state.intent,
            )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        task_data.update({
            "status": "failed",
            "stage": "worker",
            "stage_message": "Worker 执行失败",
            "error": str(exc) or "Worker 执行失败",
        })
        await _save_answer_data(task_id, task_data)
        raise
    finally:
        client = get_async_redis()
        state.trace["retry_count"] = job.attempts
        if task_data.get("status") == "stopped":
            state.trace["status"] = "stopped"
            state.trace["failure_stage"] = "cancelled"
        elif task_data.get("status") == "failed":
            state.trace["status"] = "failed"
            state.trace["failure_stage"] = (
                state.trace.get("failure_stage") or task_data.get("stage") or "worker"
            )
        trace_payload = {
            **state.trace,
            "trace_id": state.trace_id,
            "task_id": task_id,
            "session_id": state.session_id,
            "intent": state.intent,
            "retrieval_query": state.retrieval_query or state.question,
            "retrieval_top_k": state.retrieval_top_k or len(state.chunks),
            "retrieval_second_pass": state.retrieval_second_pass,
            "recorded_at": time.time(),
            "worker_retry_count": job.attempts,
            "configured_model_max_retries": settings.LLM_MAX_RETRIES,
        }
        if not trace_payload.get("total_ms"):
            trace_payload["total_ms"] = round(
                (time.perf_counter() - job_started_at) * 1000, 3
            )
        await set_json(
            f"{ANSWER_TRACE_PREFIX}{state.trace_id}",
            trace_payload,
            settings.REDIS_ANSWER_TASK_TTL_SECONDS,
        )
        task_data["trace_id"] = state.trace_id
        task_data.setdefault("result", {})["trace_id"] = state.trace_id
        task_data["result"]["trace"] = trace_payload
        await _save_answer_data(task_id, task_data)
        logger.info(
            "answer_trace %s",
            json.dumps(trace_payload, ensure_ascii=False, separators=(",", ":")),
        )
        keys = [f"{ANSWER_CANCEL_PREFIX}{task_id}"]
        if payload.get("dedupe_key"):
            keys.append(str(payload["dedupe_key"]))
        await client.delete(*keys)


async def handle_paper_process(job: WorkerJob) -> None:
    from app.api.papers import _schedule_process_paper

    payload = job.payload
    await _schedule_process_paper(
        str(payload["paper_id"]),
        str(payload["file_path"]),
        str(payload["user_id"]),
        payload.get("raw_text"),
        dict(payload.get("initial_timings") or {}),
        float(payload.get("pipeline_started_at") or time.perf_counter()),
        dict(payload.get("initial_counts") or {}),
    )


async def dispatch_job(job: WorkerJob) -> None:
    handlers = {
        "chat_answer": handle_chat_answer,
        "paper_process": handle_paper_process,
    }
    handler = handlers.get(job.type)
    if handler is None:
        raise ValueError(f"未知 Worker 任务类型: {job.type}")
    await handler(job)


async def _heartbeat(stop_event: asyncio.Event) -> None:
    """Keep liveness independent from slow model and PDF processing calls."""
    client = get_async_redis()
    while not stop_event.is_set():
        await client.set(WORKER_HEARTBEAT_KEY, str(time.time()), ex=10)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3)
        except asyncio.TimeoutError:
            pass


async def worker_loop() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    await init_db()
    if not await initialize_redis():
        raise RuntimeError("Worker 无法连接 Redis")
    await recover_processing_jobs()
    from app.api.papers import recover_incomplete_paper_tasks
    recovered_papers = recover_incomplete_paper_tasks()
    if recovered_papers:
        logger.warning("Worker 恢复 %d 个未完成论文任务", recovered_papers)
    logger.info("✅ PaperAI Worker 已启动")
    heartbeat_task = asyncio.create_task(_heartbeat(stop_event))
    try:
        while not stop_event.is_set():
            # Keep the blocking wait below the shared Redis client's socket
            # timeout so an empty queue is a normal poll, not a disconnect.
            reserved = await reserve_job(timeout_seconds=1)
            if reserved is None:
                continue
            job, raw = reserved
            logger.info("Worker 开始任务 job_id=%s type=%s", job.id, job.type)
            try:
                await dispatch_job(job)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Worker 任务失败 job_id=%s type=%s", job.id, job.type)
                await fail_or_retry_job(job, raw)
            else:
                await acknowledge_job(raw)
                logger.info("Worker 完成任务 job_id=%s type=%s", job.id, job.type)
    finally:
        stop_event.set()
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
        await get_async_redis().delete(WORKER_HEARTBEAT_KEY)
        await close_redis()
        await close_db()
        logger.info("PaperAI Worker 已停止")


if __name__ == "__main__":
    asyncio.run(worker_loop())
