"""Independent Redis worker for chat generation and paper processing."""

from __future__ import annotations

import asyncio
import asyncio as _aio
import json
import logging
import signal
import time
from typing import Any

from sqlalchemy import select

from app.agent.qa_agent.enhanced_graph import generate_follow_up_questions
from app.agent.qa_agent.workflow import QAWorkflowState
from app.config import settings
from app.database import AsyncSessionLocal, close_db, init_db
from app.harness.agents.lead_agent import stream_lead_agent
from app.job_queue import (
    WorkerJob,
    acknowledge_job,
    drain_retry_queue,
    fail_or_retry_job,
    recover_processing_jobs,
    reserve_job,
)
from app.models.chat import AnswerTrace, ChatMessage
# 显式 import 所有模型类,确保 SQLAlchemy mapper 在 worker 启动时完成注册
# (worker 不走 main.py,需自己触发 model 注册,否则 relationship("ResearchProject") 会失败)
from app.models.user import User  # noqa: F401
from app.models.paper import Paper, Section, Image, Note, Table, TableStructure  # noqa: F401
from app.models.project import ResearchProject, ProjectPaper, WritingArtifact  # noqa: F401
from app.models.execution import AgentExecution, AgentEvent, ToolCall, TERMINAL_EXECUTION_STATUSES  # noqa: F401
from app.models.evaluation import EvaluationRun  # noqa: F401
from app.models.research import MemoryItem, EvidenceItem  # noqa: F401
from app.models.document import WritingDocument, DocumentRevision  # noqa: F401
from app.research.context.paper_profile import (
    PaperProfileNotFoundError,
    PaperProfileService,
    schedule_profiles_for_parsed_paper,
)
from app.services.remote_paper_import import download_arxiv_pdf
from app.utils.task_manager import update_task
from app.redis_client import close_redis, get_async_redis, initialize_redis, set_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ANSWER_TASK_PREFIX = "paperai:answer-task:"
ANSWER_CANCEL_PREFIX = "paperai:answer-cancel:"
WORKER_HEARTBEAT_KEY = "paperai:worker:heartbeat"
ANSWER_TRACE_PREFIX = "paperai:answer-trace:"


async def handle_admin_evaluation(job: WorkerJob) -> None:
    """在现有 Worker 中执行管理员评测并持久化结果。"""
    from app.application.admin_evaluation_runner import run_admin_evaluation
    from app.application.evaluation_run_service import transition_evaluation_run
    from app.job_queue import MAX_RETRY_ATTEMPTS

    run_id = str(job.payload["evaluation_run_id"])
    async with AsyncSessionLocal() as db:
        run = await db.get(EvaluationRun, run_id)
        if run is None or run.status in {"completed", "cancelled"}:
            return
        transition_evaluation_run(run, "running")
        run.attempt_count = int(run.attempt_count or 0) + 1
        await db.commit()
        evaluation_type = str(run.evaluation_type)
        config = dict(run.config or {})

    try:
        report, report_path, markdown_path = await run_admin_evaluation(
            run_id,
            evaluation_type,
            config,
        )
    except Exception as exc:
        async with AsyncSessionLocal() as db:
            run = await db.get(EvaluationRun, run_id)
            if run is not None and run.status not in {"completed", "cancelled"}:
                final_failure = job.attempts >= MAX_RETRY_ATTEMPTS
                transition_evaluation_run(
                    run,
                    "failed" if final_failure else "retrying",
                    error_code=type(exc).__name__.upper()[:80],
                    error_message=str(exc)[:4000],
                )
                await db.commit()
        raise

    async with AsyncSessionLocal() as db:
        run = await db.get(EvaluationRun, run_id)
        if run is None or run.status == "cancelled":
            return
        transition_evaluation_run(
            run,
            "completed",
            summary=dict(report.get("summary") or {}),
            report_path=report_path,
            markdown_path=markdown_path,
            error_code=None,
            error_message=None,
        )
        # A completed retry must not retain the previous transient error.
        run.error_code = None
        run.error_message = None
        await db.commit()


async def handle_agent_execution_v2(job: WorkerJob) -> None:
    """Compatibility adapter for historical writing execution jobs.

    New project writing never enters this queue type.  If an old queued job is
    still present, it is converted into the same persisted GoalExecution path
    instead of running a second writing lifecycle in the Worker.
    """
    execution_id = str(job.payload["execution_id"])
    async with AsyncSessionLocal() as db:
        item = await db.get(AgentExecution, execution_id)
        if item is None or item.status in TERMINAL_EXECUTION_STATUSES:
            return
        if item.agent_type not in {"writing_generate", "research_goal"}:
            raise ValueError("UNSUPPORTED_PROJECT_GOAL_EXECUTION")
        from app.application.project_execution_entrypoint import initialize_project_goal

        await initialize_project_goal(db, item)


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


async def _persist_answer_trace(
    trace_payload: dict[str, Any],
    *,
    task_id: str,
    user_id: str,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AnswerTrace).where(
                    AnswerTrace.trace_id == str(trace_payload["trace_id"])
                )
            )
            trace = result.scalar_one_or_none()
            values = {
                "task_id": task_id,
                "user_id": user_id,
                "session_id": str(trace_payload.get("session_id") or ""),
                "status": str(trace_payload.get("status") or "completed"),
                "thinking_tokens": int(trace_payload.get("input_tokens") or trace_payload.get("thinking_tokens") or 0),
                "answer_tokens": int(trace_payload.get("output_tokens") or trace_payload.get("answer_tokens") or 0),
                "total_ms": trace_payload.get("total_ms"),
                "first_token_ms": trace_payload.get("first_token_ms"),
                "retrieval_ms": trace_payload.get("retrieval_ms"),
                "citation_count": int(trace_payload.get("citation_count") or 0),
                "model_calls": int(trace_payload.get("llm_calls") or trace_payload.get("model_calls") or 0),
                "retry_count": int(trace_payload.get("worker_retry_count") or 0),
                "used_second_pass": bool(
                    trace_payload.get("retrieval_second_pass")
                ),
            }
            if trace is None:
                trace = AnswerTrace(
                    trace_id=str(trace_payload["trace_id"]),
                    **values,
                )
                db.add(trace)
            else:
                for key, value in values.items():
                    setattr(trace, key, value)
            await db.commit()
    except Exception:
        logger.exception(
            "回答指标持久化失败 trace_id=%s", trace_payload.get("trace_id")
        )


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
            # 走 harness agent 流式路径(替代原 UnifiedQAWorkflow)
            # project_id:项目对话模式时非空,stream_lead_agent 会注入项目上下文与 project_* tool
            project_id = str(payload.get("project_id") or "")
            async for event, event_payload in stream_lead_agent(
                db=db,
                session_id=str(payload["session_id"]),
                user_id=str(payload["user_id"]),
                question=str(payload["question"]),
                enable_thinking=bool(payload.get("enable_thinking", False)),
                project_id=project_id,
                request_id=str(payload.get("trace_id") or task_id),
            ):
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
                        "trace_id": event_payload.get("trace_id", state.trace_id),
                    })
                    # 从 done payload 提取 agent 产出的关键信息
                    state.message_id = event_payload.get("message_id", "")
                    state.intent = event_payload.get("intent", "general")
                    state.answer = task_data.get("answer", "")
                    state.citations = event_payload.get("sources", [])
                    state.evidence_confidence = event_payload.get("evidence_confidence", 0.0)
                    # 从 agent_trace 提取链路追踪指标,写入 state.trace 供 AnswerTrace 持久化
                    agent_trace = event_payload.get("agent_trace") or {}
                    state.trace["total_ms"] = agent_trace.get("total_ms")
                    state.trace["llm_calls"] = agent_trace.get("llm_calls", 0)
                    state.trace["total_tokens"] = agent_trace.get("total_tokens", 0)
                    state.trace["input_tokens"] = agent_trace.get("input_tokens", 0)
                    state.trace["output_tokens"] = agent_trace.get("output_tokens", 0)
                    state.trace["iterations"] = agent_trace.get("iterations", 0)
                    state.trace["tool_calls"] = agent_trace.get("tool_calls", [])
                    state.trace["first_token_ms"] = agent_trace.get("first_token_ms")
                    state.trace["retrieval_ms"] = agent_trace.get("retrieval_ms")
                    state.trace["status"] = "completed"
                elif event == "error":
                    task_data.update({
                        "status": "failed",
                        "stage": event_payload.get("stage", "agent"),
                        "stage_message": "回答失败",
                        "error": event_payload.get("message", "回答处理失败"),
                    })
                now = time.monotonic()
                if event not in {"answer_delta", "reasoning_delta"} or now - last_saved >= 0.05:
                    await _save_answer_data(task_id, task_data)
                    last_saved = now
        await _save_answer_data(task_id, task_data)
        # 追问生成 + trace 持久化 放后台 task,不阻塞 worker 线程释放
        # (用户已看完全部答案,这些是辅助功能,不应占用 worker 导致下个请求排队)
        if state.message_id:
            _aio.create_task(_generate_followups(
                state.message_id,
                state.question,
                state.answer,
                state.intent,
            ))
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
        # AnswerTrace DB 持久化放后台,不阻塞 worker 线程释放
        _aio.create_task(_persist_answer_trace(
            trace_payload,
            task_id=task_id,
            user_id=state.user_id,
        ))
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
        bool(payload.get("media_only")),
    )
    if payload.get("media_only"):
        return
    try:
        async with AsyncSessionLocal() as db:
            await schedule_profiles_for_parsed_paper(db, str(payload["paper_id"]), force=True)
    except Exception:
        logger.exception("解析已完成，但 Paper Profile 调度失败 paper_id=%s", payload["paper_id"])


async def handle_paper_profile(job: WorkerJob) -> None:
    """Generate one project-scoped profile; failures are persisted and acknowledged."""
    try:
        async with AsyncSessionLocal() as db:
            profile = await PaperProfileService(db).run_generation(
                project_id=str(job.payload["project_id"]),
                paper_id=str(job.payload["paper_id"]),
                expected_fingerprint=str(job.payload["source_fingerprint"]),
            )
            if profile.status == "failed":
                logger.warning(
                    "Paper Profile 生成失败但不阻塞论文使用 project_id=%s paper_id=%s code=%s",
                    profile.project_id,
                    profile.paper_id,
                    profile.error_code,
                )
    except PaperProfileNotFoundError:
        logger.info(
            "Paper Profile 任务目标已移除，直接确认 job_id=%s project_id=%s paper_id=%s",
            job.id,
            job.payload.get("project_id"),
            job.payload.get("paper_id"),
        )


async def handle_arxiv_import(job: WorkerJob) -> None:
    """Download in the Worker, run the standard pipeline, then attach the ProjectPaper."""
    from app.api.papers import _schedule_process_paper

    payload = job.payload
    project_id = str(payload["project_id"])
    paper_id = str(payload["paper_id"])
    arxiv_id = str(payload["arxiv_id"])

    async def update_import(status: str, error: str = "") -> None:
        async with AsyncSessionLocal() as db:
            project = await db.get(ResearchProject, project_id)
            if project is None:
                return
            preferences = dict(project.preferences or {})
            imports = [dict(item) for item in preferences.get("paper_imports") or []]
            for item in imports:
                if item.get("paper_id") == paper_id:
                    item.update({"status": status, "error": error, "updated_at": time.time()})
            preferences["paper_imports"] = imports
            project.preferences = preferences
            await db.commit()

    await update_import("processing")
    file_path = str(payload.get("file_path") or "")
    initial_counts = dict(payload.get("initial_counts") or {})
    if not file_path:
        update_task(
            job.id,
            status="processing",
            progress=1,
            message="正在安全下载 arXiv PDF...",
        )
        download_started_at = time.perf_counter()
        try:
            downloaded = await download_arxiv_pdf(
                arxiv_id,
                paper_id=paper_id,
                storage_path=settings.FILE_STORAGE_PATH,
                max_size=settings.MAX_UPLOAD_SIZE,
                timeout_seconds=settings.REMOTE_IMPORT_READ_TIMEOUT_SECONDS,
                total_timeout_seconds=settings.REMOTE_IMPORT_TOTAL_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logger.warning("arXiv PDF 下载失败 arxiv_id=%s: %s", arxiv_id, exc)
            update_task(
                job.id,
                status="failed",
                progress=0,
                message="arXiv PDF 下载失败，请稍后重试",
            )
            await update_import("failed", type(exc).__name__)
            return
        file_path = downloaded.file_path
        initial_counts.update({
            "remote_file_size": downloaded.file_size,
            "remote_download_seconds": round(time.perf_counter() - download_started_at, 3),
        })
    await _schedule_process_paper(
        paper_id, file_path, str(payload["user_id"]), None,
        {}, time.perf_counter(), initial_counts,
    )
    async with AsyncSessionLocal() as db:
        paper = await db.get(Paper, paper_id)
        project = await db.get(ResearchProject, project_id)
        if paper is None:
            await update_import("failed", "PDF 解析失败")
            return
        paper.source_url = str(payload["source_url"])
        if project is not None and project.user_id == str(payload["user_id"]):
            existing = (await db.execute(select(ProjectPaper).where(
                ProjectPaper.project_id == project_id, ProjectPaper.paper_id == paper_id,
            ))).scalars().first()
            if existing is None:
                db.add(ProjectPaper(
                    project_id=project_id, paper_id=paper_id, role=str(payload.get("role") or "related"),
                    tags=list(payload.get("tags") or []), notes=str(payload.get("notes") or ""),
                    reading_priority=int(payload.get("reading_priority") or 3),
                ))
        await db.commit()
        try:
            await schedule_profiles_for_parsed_paper(db, paper_id)
        except Exception:
            logger.exception("arXiv 已导入，但 Paper Profile 调度失败 paper_id=%s", paper_id)
    await update_import("ready")
    logger.info("arXiv 导入完成 project_id=%s arxiv_id=%s paper_id=%s", project_id, arxiv_id, paper_id)


async def dispatch_job(job: WorkerJob) -> None:
    from app.application.research_task_worker import run_task
    handlers = {
        "research_task": run_task,
        "chat_answer": handle_chat_answer,
        "paper_process": handle_paper_process,
        "paper_media_enhance": handle_paper_process,
        "paper_profile": handle_paper_profile,
        "arxiv_import": handle_arxiv_import,
        "agent_execution_v2": handle_agent_execution_v2,
        "admin_evaluation": handle_admin_evaluation,
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
    from app.application.research_task_worker import recover_tasks
    await recover_tasks()
    from app.api.papers import recover_incomplete_paper_tasks
    recovered_papers = recover_incomplete_paper_tasks()
    if recovered_papers:
        logger.warning("Worker 恢复 %d 个未完成论文任务", recovered_papers)
    logger.info("✅ PaperAI Worker 已启动")
    heartbeat_task = asyncio.create_task(_heartbeat(stop_event))
    try:
        while not stop_event.is_set():
            # 先把延迟重试队列里到期的任务搬回主队列
            await drain_retry_queue()
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
