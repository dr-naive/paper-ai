"""Independent Redis worker for chat generation and paper processing."""

from __future__ import annotations

import asyncio
import asyncio as _aio
import json
import logging
import signal
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.agent.qa_agent.enhanced_graph import generate_follow_up_questions
from app.agent.qa_agent.workflow import QAWorkflowState
from app.config import settings
from app.database import AsyncSessionLocal, close_db, init_db
from app.harness.agents.lead_agent import run_lead_agent, stream_lead_agent
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
from app.models.research import MemoryItem, EvidenceItem  # noqa: F401
from app.models.document import WritingDocument, DocumentRevision  # noqa: F401
from app.application.execution_service import (
    CompletionGateError,
    append_event,
    delete_checkpoint,
    get_control,
    save_checkpoint,
    set_control,
    set_status,
    validate_writing_completion,
)
from app.application.writing_service import (
    WritingGenerateRequest,
    WritingGenerationProposal,
    WritingService,
    WritingServiceError,
)
from app.harness.runtime.skill_runtime import SkillRuntime
from app.harness.runtime.standard_tools import build_standard_tool_runtime
from app.research.context.paper_profile import (
    PaperProfileNotFoundError,
    PaperProfileService,
    schedule_profiles_for_parsed_paper,
)
from app.services.remote_paper_import import download_arxiv_pdf
from app.utils.task_manager import update_task
from app.redis_client import close_redis, get_async_redis, get_json, initialize_redis, set_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ANSWER_TASK_PREFIX = "paperai:answer-task:"
ANSWER_CANCEL_PREFIX = "paperai:answer-cancel:"
WORKER_HEARTBEAT_KEY = "paperai:worker:heartbeat"
ANSWER_TRACE_PREFIX = "paperai:answer-trace:"
READING_EXECUTION_PREFIX = "paperai:reading-execution:"
READING_EXECUTION_TTL = 7 * 24 * 60 * 60
WRITING_SKILL_ID = "writing_evidence_generation"
SKILLS_DIR = Path(__file__).resolve().parent / "harness" / "skills"


async def handle_agent_execution_v2(job: WorkerJob) -> None:
    execution_id = str(job.payload["execution_id"])
    async with AsyncSessionLocal() as db:
        item = await db.get(AgentExecution, execution_id)
        if item is None or item.status in TERMINAL_EXECUTION_STATUSES:
            return
        if await get_control(execution_id) == "pause":
            return
        if item.agent_type != "writing_generate":
            await set_status(db, item, "failed", stage="failed", error_code="UNSUPPORTED_AGENT_TYPE",
                             error_message="不支持的执行类型")
            await append_event(db, item, "execution_failed", "执行类型不受支持", stage="failed")
            return

        stage_messages = {
            "context_started": "正在查找与写作要求相关的项目论文",
            "context_ready": "已找到候选论文与支持证据",
            "generation_started": "正在生成证据支持的段落",
            "proposal_generated": "段落草案已生成",
            "review_started": "正在审查草案质量与证据一致性",
            "review_passed": "Writing Reviewer 审查已通过",
            "review_repair_required": "Writing Reviewer 要求进行一次有限修复",
            "review_repair_completed": "一次有限修复已完成",
            "evidence_persisted": "引用证据已保存",
            "verification_started": "正在验证引用与论断",
            "citation_verified": "引用验证已完成",
        }
        safe_control_stages = {"context_started", "context_ready", "generation_started", "proposal_generated"}

        class ExecutionPaused(Exception):
            pass

        class ExecutionCancelled(Exception):
            pass

        async def check_control(stage: str) -> None:
            action = await get_control(execution_id)
            if action == "cancel":
                raise ExecutionCancelled
            if action == "pause":
                raise ExecutionPaused

        async def progress(stage: str, data: dict[str, Any]) -> None:
            item.current_stage = stage
            await db.commit()
            await save_checkpoint(execution_id, {"stage": stage, "data": data})
            await append_event(db, item, stage, stage_messages[stage], stage=stage, data=data)
            if stage in safe_control_stages:
                await check_control(stage)

        try:
            await set_status(db, item, "running", stage="starting")
            await append_event(db, item, "execution_started", "写作任务已启动", stage="starting")
            skill_runtime = SkillRuntime(SKILLS_DIR, build_standard_tool_runtime().specs())
            skill = await skill_runtime.activate(item, WRITING_SKILL_ID, db=db)
            await append_event(
                db, item, "skill_activated", "Evidence-backed Writing Skill 已激活",
                stage="skill_activated", data={"skill_id": skill.id, "skill_version": skill.version},
            )
            if item.result_payload and item.result_payload.get("proposal"):
                proposal = WritingGenerationProposal.model_validate(item.result_payload["proposal"])
            else:
                request = WritingGenerateRequest.model_validate(item.input_payload or {})
                proposal = await WritingService(db).generate_paragraph(
                    project_id=str(item.project_id),
                    user_id=item.user_id,
                    request=request,
                    on_progress=progress,
                )
                item.result_payload = {"proposal": proposal.model_dump(mode="json")}
                await db.commit()
                await save_checkpoint(execution_id, {"stage": "proposal_ready", "result_persisted": True})

            await check_control("proposal_ready")
            review = proposal.review
            single_paragraph = len([part for part in proposal.content.split("\n\n") if part.strip()]) == 1
            mappings_valid = bool(proposal.citations) and all(
                citation.citation_key and citation.paper_id and citation.evidence_id for citation in proposal.citations
            )
            reviewer_valid = review is not None and review.status in {"passed", "repaired"} and review.repair_count <= 1
            citations_supported = all(citation.status != "unsupported" for citation in proposal.citations)
            contract_ready = single_paragraph and mappings_valid and reviewer_valid and citations_supported
            criteria = {
                "生成结果只有一个段落": single_paragraph,
                "每个事实性引用具有结构化 Evidence 映射": mappings_valid,
                "Writing Reviewer 已通过或完成一次有限修复": reviewer_valid,
                "Citation Verification 不包含 unsupported": citations_supported,
                "生成结果满足 Completion Gate 输入契约": contract_ready,
            }
            skill_report = skill_runtime.evaluate_completion(
                WRITING_SKILL_ID,
                metadata={
                    "document_id": proposal.document_id,
                    "proposal_id": proposal.proposal_id,
                    "citation_count": len(proposal.citations),
                    "reviewer_status": review.status if review else None,
                    "repair_count": review.repair_count if review else None,
                    "completion_contract_ready": contract_ready,
                },
                criterion_results=criteria,
            ).model_dump(mode="json")
            item.result_payload = {"proposal": proposal.model_dump(mode="json"), "skill_completion": skill_report}
            await db.commit()
            await append_event(
                db, item, "skill_completion_evaluated",
                "Writing Skill 完成条件已通过" if skill_report["passed"] else "Writing Skill 完成条件未通过",
                stage="skill_completion", data={
                    "skill_id": skill_report["skill_id"], "passed": skill_report["passed"],
                    "failed_criteria_count": sum(not criterion["passed"] for criterion in skill_report["criteria"]),
                    "missing_metadata_count": len(skill_report["missing_metadata"]),
                },
            )
            completion = validate_writing_completion(item, proposal, skill_report)
            item.result_payload = {
                "proposal": proposal.model_dump(mode="json"),
                "skill_completion": skill_report,
                "completion": completion,
            }
            await db.commit()
            await append_event(db, item, "completion_gate_passed", "完成质量检查已通过",
                               stage="completion_gate", data=completion)
            await set_status(db, item, "completed", stage="completed")
            await append_event(db, item, "execution_completed", "写作建议已完成", stage="completed",
                               data={"proposal_id": proposal.proposal_id, "proposal_status": proposal.status})
            await delete_checkpoint(execution_id)
            await set_control(execution_id, None)
        except ExecutionPaused:
            await set_status(db, item, "paused", stage=item.current_stage)
            await append_event(db, item, "execution_paused", "执行已在安全边界暂停", stage=item.current_stage)
        except ExecutionCancelled:
            await set_status(db, item, "cancelled", stage="cancelled", error_code="EXECUTION_CANCELLED",
                             error_message="用户取消")
            await append_event(db, item, "execution_cancelled", "执行已取消", stage="cancelled")
            await delete_checkpoint(execution_id)
            await set_control(execution_id, None)
        except CompletionGateError as exc:
            await set_status(db, item, "failed", stage="completion_gate", error_code="COMPLETION_GATE_FAILED",
                             error_message=str(exc))
            await append_event(db, item, "completion_gate_failed", "完成质量检查未通过",
                               stage="completion_gate", data={"checks_failed": str(exc).split(",")})
            await set_control(execution_id, None)
        except WritingServiceError as exc:
            await set_status(db, item, "failed", stage="failed", error_code=exc.code, error_message=str(exc))
            await append_event(db, item, "execution_failed", str(exc), stage="failed", data={"code": exc.code})
            await set_control(execution_id, None)
        except Exception:
            logger.exception("Durable writing execution failed execution_id=%s", execution_id)
            await set_status(db, item, "failed", stage="failed", error_code="EXECUTION_FAILED",
                             error_message="执行失败，请稍后重试")
            await append_event(db, item, "execution_failed", "执行失败，请稍后重试", stage="failed")
            await set_control(execution_id, None)


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


async def handle_project_reading_execution(job: WorkerJob) -> None:
    payload = job.payload
    task_id = str(payload["task_id"])
    project_id = str(payload["project_id"])
    user_id = str(payload["user_id"])
    key = f"{READING_EXECUTION_PREFIX}{task_id}"
    task = await get_json(key)
    if not isinstance(task, dict):
        raise LookupError(f"精读任务不存在 task_id={task_id}")
    task.update({"status": "running", "updated_at": time.time()})
    await set_json(key, task, READING_EXECUTION_TTL)

    try:
        async with AsyncSessionLocal() as db:
            project = await db.get(ResearchProject, project_id)
            if project is None or project.user_id != user_id:
                raise LookupError("项目不存在或无访问权限")
            rows = (await db.execute(
                select(ProjectPaper, Paper)
                .join(Paper, Paper.id == ProjectPaper.paper_id)
                .where(ProjectPaper.project_id == project_id, Paper.user_id == user_id)
            )).all()
            pending = [
                (pp, paper) for pp, paper in rows
                if (pp.reading_plan or {}).get("status") in {"pending", "reading", "failed"}
            ]
            pending.sort(key=lambda row: int((row[0].reading_plan or {}).get("order") or 9999))
            pending = pending[: int(task.get("max_items") or 10)]
            task["total"] = int(task.get("completed") or 0) + len(pending)

            for pp, paper in pending:
                latest = await get_json(key)
                if isinstance(latest, dict):
                    task = latest
                if task.get("control") == "pause":
                    task.update({"status": "paused", "current_paper_id": None, "updated_at": time.time()})
                    await set_json(key, task, READING_EXECUTION_TTL)
                    return

                plan = dict(pp.reading_plan or {})
                plan.update({"status": "reading", "updated_at": time.time()})
                pp.reading_plan = plan
                await db.commit()
                task.update({
                    "status": "running",
                    "current_paper_id": str(paper.id),
                    "current_paper_title": paper.title,
                    "updated_at": time.time(),
                })
                await set_json(key, task, READING_EXECUTION_TTL)

                focus = "；".join(plan.get("focus") or []) or "核心方法、实验与局限"
                questions = "；".join(plan.get("questions") or []) or "论文的核心贡献、证据和局限是什么？"
                prompt = (
                    "你正在执行项目精读队列中的单篇任务。"
                    f"请只精读当前论文《{paper.title}》。阅读重点：{focus}。"
                    f"需要回答：{questions}。"
                    "必须先用 search_paper_content 查找证据，再调用 project_save_paper_card 保存结构化卡片，"
                    "并用 project_append_memory 记录至少一条带 paper_id、page、source_id 的关键发现。"
                    "不要生成领域综述，也不要修改阅读计划。"
                )
                result = await run_lead_agent(
                    db=db,
                    paper_id=str(paper.id),
                    question=prompt,
                    user_id=user_id,
                    project_id=project_id,
                    request_id=f"reading-{task_id}-{paper.id}",
                    enable_critique=False,
                )
                await db.refresh(pp)
                if not result.success or not (pp.analysis_card or {}).get("summary"):
                    failed_plan = dict(pp.reading_plan or plan)
                    failed_plan.update({"status": "failed", "updated_at": time.time()})
                    pp.reading_plan = failed_plan
                    await db.commit()
                    raise RuntimeError(result.trace.failure_reason or f"论文 {paper.id} 未生成阅读卡片")

                results = list(task.get("results") or [])
                results.append({"paper_id": str(paper.id), "paper_title": paper.title, "status": "completed"})
                task.update({
                    "completed": int(task.get("completed") or 0) + 1,
                    "results": results,
                    "current_paper_id": None,
                    "updated_at": time.time(),
                })
                await set_json(key, task, READING_EXECUTION_TTL)

        task.update({"status": "completed", "current_paper_id": None, "updated_at": time.time()})
        await set_json(key, task, READING_EXECUTION_TTL)
    except Exception as exc:
        task.update({"status": "failed", "error": str(exc), "current_paper_id": None, "updated_at": time.time()})
        await set_json(key, task, READING_EXECUTION_TTL)
        raise


async def dispatch_job(job: WorkerJob) -> None:
    from app.application.research_task_worker import run_task
    handlers = {
        "research_task": run_task,
        "chat_answer": handle_chat_answer,
        "paper_process": handle_paper_process,
        "paper_media_enhance": handle_paper_process,
        "paper_profile": handle_paper_profile,
        "arxiv_import": handle_arxiv_import,
        "project_reading_execution": handle_project_reading_execution,
        "agent_execution_v2": handle_agent_execution_v2,
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
