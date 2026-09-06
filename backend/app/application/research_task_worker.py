"""Existing WorkerJob handler for one persisted business task."""
import asyncio
import hashlib
from datetime import datetime
from sqlalchemy import select, text
from app.database import AsyncSessionLocal, engine
from app.models.execution import AgentExecution, ModelCall, ResearchTask, ToolCall
from app.models.project import ResearchProject
from app.research.task_contracts import TaskResult, TaskError, transition, transition_execution, TERMINAL
from app.application.research_orchestrator import ResearchOrchestrator
from app.application.execution_service import append_event, get_control, save_checkpoint

from app.harness.runtime.task_context import (
    current_agent_tool_observer,
    current_model_call_observer,
    current_task_id,
    current_task_progress,
    current_task_skill_id,
)


class TaskInterrupted(Exception):
    pass


_KNOWN_RUNTIME_ERROR_CODES = (
    'TOOL_INPUT_INVALID', 'TOOL_TIMEOUT', 'TOOL_EXECUTION_FAILED',
    'TOOL_CONTEXT_FORBIDDEN', 'SKILL_TOOL_FORBIDDEN',
    'SKILL_TOOL_BUDGET_EXCEEDED', 'SKILL_EXTERNAL_SEARCH_BUDGET_EXCEEDED',
    'SKILL_PAPER_BUDGET_EXCEEDED', 'TASK_SKILL_BUDGET_EXCEEDED',
    'TOOL_BUDGET_EXCEEDED', 'MODEL_BUDGET_EXCEEDED',
    'TOKEN_BUDGET_EXCEEDED', 'TIME_BUDGET_EXCEEDED',
)


def _runtime_error_code(exc: Exception) -> str:
    message = str(exc)
    return next((code for code in _KNOWN_RUNTIME_ERROR_CODES if code in message),
                getattr(exc, 'code', None) or type(exc).__name__)


async def run_task(job):
    # Session-level project advisory lock uses a dedicated connection so executor
    # commits cannot release it. PostgreSQL releases it on connection/process death.
    async with AsyncSessionLocal() as lookup:
        execution = await lookup.get(AgentExecution, job.payload['execution_id'])
        if execution is None:
            return
        project_id = execution.project_id
    lock_key = int.from_bytes(hashlib.sha256(f'research:{project_id}'.encode()).digest()[:8], 'big', signed=True)
    async with engine.connect() as connection:
        await connection.execute(text('SELECT pg_advisory_lock(:key)'), {'key': lock_key})
        try:
            await _execute(job)
        finally:
            await connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': lock_key})
            await connection.commit()


async def _execute(job):
    from app.application.research_task_executors import TaskExecutors
    async with AsyncSessionLocal() as db:
        execution = await db.get(AgentExecution, job.payload['execution_id'])
        task = await db.get(ResearchTask, job.payload['task_id'])
        if task is None or execution is None or task.execution_id != execution.id:
            return
        orchestrator = ResearchOrchestrator(db)
        if execution.status in TERMINAL | {'paused', 'waiting_user', 'blocked'}:
            return
        if task.status == 'completed':
            await orchestrator.advance(execution)  # recover completion/publication gap
            return
        if task.status in TERMINAL | {'pending', 'waiting_user', 'blocked'}:
            return
        parents = await orchestrator.tasks(execution.id)
        if not set(task.dependencies) <= {t.task_id for t in parents if t.status == 'completed'}:
            return
        orchestrator.dispatcher.select_executor(task)
        project = await db.get(ResearchProject, execution.project_id)
        if project is None or project.user_id != execution.user_id:
            raise PermissionError('PROJECT_NOT_FOUND')
        if task.attempt_count >= task.max_attempts:
            if task.status != 'running':
                transition(task, 'running')
            await orchestrator.complete(execution, task, TaskResult(task_id=task.task_id, status='failed',
                output_refs=task.output_refs or [], error=TaskError(code='TASK_RETRY_EXHAUSTED', message='重试次数已耗尽')))
            return
        transition_execution(execution, 'running')
        transition(task, 'running')
        task.attempt_count += 1
        await db.commit()

        async def progress(stage, data):
            await db.refresh(execution)
            action = await get_control(execution.id)
            if execution.status in {'cancelled', 'paused'} or action in {'pause', 'cancel'}:
                raise TaskInterrupted()
            if stage == 'token_usage':
                execution.input_tokens += int(data.get('prompt_tokens') or 0)
                execution.output_tokens += int(data.get('completion_tokens') or 0)
            if execution.input_tokens + execution.output_tokens >= execution.max_tokens:
                raise PermissionError('TOKEN_BUDGET_EXCEEDED')
            metrics = dict((task.completion_payload or {}).get('metrics') or {})
            if task.skill_id and stage in {'model_call', 'tool_call'}:
                from pathlib import Path
                from app.harness.runtime.skill_runtime import SkillRuntime
                from app.harness.runtime.standard_tools import build_standard_tool_runtime
                skill = SkillRuntime(Path(__file__).parents[1] / 'harness/skills', build_standard_tool_runtime().specs()).load(task.skill_id)
                limit = skill.max_model_calls if stage == 'model_call' else skill.max_tool_calls
                if metrics.get(stage, 0) >= limit:
                    raise PermissionError('TASK_SKILL_BUDGET_EXCEEDED')
            if stage in {'model_call', 'tool_call'}:
                metrics[stage] = metrics.get(stage, 0) + 1
                task.completion_payload = {**(task.completion_payload or {}), 'metrics': metrics}
            if stage == 'model_call':
                if execution.model_call_count >= execution.max_model_calls:
                    raise PermissionError('MODEL_BUDGET_EXCEEDED')
                execution.model_call_count += 1
            if stage == 'tool_call':
                if execution.tool_call_count >= execution.max_tool_calls:
                    raise PermissionError('TOOL_BUDGET_EXCEEDED')
                execution.tool_call_count += 1
            if execution.started_at:
                from datetime import datetime
                if (datetime.utcnow() - execution.started_at).total_seconds() > execution.max_seconds:
                    raise PermissionError('TIME_BUDGET_EXCEEDED')
            await db.commit()
            await save_checkpoint(execution.id, {'task_id': task.task_id, 'stage': stage, 'plan_version': execution.plan_version})
            if stage == 'scope_rejected':
                await append_event(db, execution, 'task_scope_rejected', '操作超出当前任务范围，已拒绝', data=data)

        model_rows = {}
        model_call_index = execution.model_call_count

        async def observe_model_call(stage, data):
            """Persist prompt-free model traces for this ResearchTask only."""
            nonlocal model_call_index
            call_id = data.get('call_id')
            if not call_id:
                return
            if stage == 'started':
                model_call_index += 1
                row = ModelCall(
                    id=call_id,
                    execution_id=execution.id,
                    task_id=task.task_id,
                    skill_id=task.skill_id,
                    call_index=model_call_index,
                    model=str(data.get('model') or 'unknown'),
                    provider=data.get('provider'),
                    purpose=str(data.get('purpose') or 'agent_model_call'),
                    status='running',
                    started_at=datetime.utcnow(),
                )
                model_rows[call_id] = row
                db.add(row)
                await db.flush()
                return
            row = model_rows.get(call_id)
            if row is None:
                return
            row.status = str(data.get('status') or 'failed')
            row.input_tokens = data.get('input_tokens')
            row.output_tokens = data.get('output_tokens')
            row.duration_ms = data.get('duration_ms')
            row.error_code = data.get('error_code')
            row.completed_at = datetime.utcnow()
            await db.commit()

        tool_rows = {}
        tool_step_index = execution.tool_call_count

        async def observe_agent_tool(stage, data):
            """Persist Lead Agent tool traces through the existing ToolCall table."""
            nonlocal tool_step_index
            call_id = data.get('call_id')
            if not call_id:
                return
            if stage == 'started':
                tool_step_index += 1
                row = ToolCall(
                    id=call_id,
                    execution_id=execution.id,
                    task_id=task.task_id,
                    skill_id=task.skill_id,
                    step_index=tool_step_index,
                    tool_name=str(data.get('tool_name') or 'unknown'),
                    tool_version='lead-agent',
                    arguments=data.get('arguments') or {},
                    side_effect_level='none',
                    status='running',
                    started_at=datetime.utcnow(),
                )
                tool_rows[call_id] = row
                db.add(row)
                await db.flush()
                return
            row = tool_rows.get(call_id)
            if row is None:
                return
            row.status = 'completed' if data.get('status') == 'completed' else 'failed'
            row.result_summary = str(data.get('result_summary') or '')[:2000]
            row.error_code = data.get('error_code')
            row.completed_at = datetime.utcnow()
            await db.commit()

        token = current_task_id.set(task.task_id)
        skill_token = current_task_skill_id.set(task.skill_id)
        progress_token = current_task_progress.set(progress)
        model_observer_token = current_model_call_observer.set(observe_model_call)
        tool_observer_token = current_agent_tool_observer.set(observe_agent_tool)
        try:
            result = await asyncio.wait_for(TaskExecutors(db, execution, task, progress).execute(), execution.max_seconds)
        except TaskInterrupted:
            await db.refresh(execution)
            await db.refresh(task)
            if execution.status == 'cancelled' and task.status not in TERMINAL:
                transition(task, 'cancelled')
            elif task.status == 'running':
                transition(task, 'queued')
            await db.commit()
            return
        except asyncio.CancelledError:
            # Process shutdown/cancellation can happen after an executor has
            # committed an idempotent artifact but before the queue ack.  Put
            # the business task back into the durable queue state; startup
            # recovery will resume it from its stable task/artifact ids.
            await db.rollback()
            await db.refresh(execution)
            await db.refresh(task)
            if execution.status == 'cancelled' and task.status not in TERMINAL:
                transition(task, 'cancelled')
            elif task.status == 'running':
                transition(task, 'queued')
            await db.commit()
            raise
        except Exception as exc:
            await db.rollback()
            await db.refresh(execution)
            await db.refresh(task)
            result = TaskResult(task_id=task.task_id, status='failed', output_refs=task.output_refs or [],
                error=TaskError(code=_runtime_error_code(exc), message=str(exc)[:1000],
                                retryable=not isinstance(exc, (ValueError, PermissionError, LookupError))))
        finally:
            current_task_id.reset(token)
            current_task_skill_id.reset(skill_token)
            current_task_progress.reset(progress_token)
            current_model_call_observer.reset(model_observer_token)
            current_agent_tool_observer.reset(tool_observer_token)
        await orchestrator.complete(execution, task, result)
        if task.status == 'retrying':
            raise RuntimeError(task.error_code or 'TASK_RETRY')


async def recover_tasks():
    """Reconcile durable dispatch gaps into the incumbent queue at worker startup."""
    from app.job_queue import enqueue_job
    async with AsyncSessionLocal() as db:
        executions = list((await db.scalars(select(AgentExecution).where(
            AgentExecution.plan_version > 0, AgentExecution.status.in_(['queued', 'running', 'retrying'])))).all())
        for execution in executions:
            orchestrator = ResearchOrchestrator(db)
            await orchestrator.advance(execution)
            for task in await orchestrator.tasks(execution.id):
                if task.status in {'queued', 'running', 'retrying'}:
                    await enqueue_job('research_task', {'execution_id': execution.id, 'task_id': task.task_id}, job_id=task.task_id)
