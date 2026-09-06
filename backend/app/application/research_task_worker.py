"""Existing WorkerJob handler for one persisted business task."""
import asyncio
import hashlib
from sqlalchemy import select, text
from app.database import AsyncSessionLocal, engine
from app.models.execution import AgentExecution, ResearchTask
from app.models.project import ResearchProject
from app.research.task_contracts import TaskResult, TaskError, transition, transition_execution, TERMINAL
from app.application.research_orchestrator import ResearchOrchestrator
from app.application.execution_service import append_event, get_control, save_checkpoint

from app.harness.runtime.task_context import current_task_id, current_task_progress


class TaskInterrupted(Exception):
    pass


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

        token = current_task_id.set(task.task_id)
        progress_token = current_task_progress.set(progress)
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
                error=TaskError(code=getattr(exc, 'code', type(exc).__name__), message=str(exc)[:1000],
                                retryable=not isinstance(exc, (ValueError, PermissionError, LookupError))))
        finally:
            current_task_id.reset(token)
            current_task_progress.reset(progress_token)
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
