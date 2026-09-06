"""Goal lifecycle only. Business capabilities live in task executors."""
from __future__ import annotations
from sqlalchemy import select
from app.models.execution import ResearchTask
from app.application.research_planning import GoalResolver, ProjectStateReader, PlanBuilder
from app.application.execution_service import append_event, save_checkpoint
from app.research.task_contracts import transition, transition_execution, TERMINAL
from app.job_queue import enqueue_job

LABELS = {'DISCOVER': '搜索并筛选相关论文', 'IMPORT_PAPER': '导入选定论文',
          'READ_PAPER': '精读项目论文', 'BUILD_EVIDENCE': '整理可用论文证据',
          'WRITE_SECTION': '生成章节草稿', 'AUDIT_DRAFT': '检查引用可靠性'}
EXECUTOR_ROUTES = {
    ('DISCOVER', 'WORKFLOW'): 'existing_literature_discovery',
    ('IMPORT_PAPER', 'WORKFLOW'): 'existing_remote_import',
    ('READ_PAPER', 'AGENT'): 'task_scoped_lead_agent',
    ('BUILD_EVIDENCE', 'WORKFLOW'): 'existing_evidence_workflow',
    ('WRITE_SECTION', 'WORKFLOW'): 'existing_writing_workflow',
    ('AUDIT_DRAFT', 'DETERMINISTIC'): 'existing_citation_audit',
}


class CompletionEvaluator:
    def apply(self, execution, task, result):
        if result.task_id != task.task_id:
            raise ValueError('TASK_RESULT_MISMATCH')
        for ref in result.output_refs:
            if ref.project_id != execution.project_id or ref.source_task_id not in {None, task.task_id}:
                raise ValueError('OUTPUT_SCOPE_MISMATCH')
        if result.status == 'completed' and (not result.output_refs or not result.completion or not all(result.completion.values())):
            raise ValueError('TASK_COMPLETION_FAILED')
        if result.status == 'waiting_user' and not result.waiting:
            raise ValueError('WAITING_CONTEXT_REQUIRED')
        if result.status in {'blocked', 'failed'} and result.error is None:
            raise ValueError('TASK_ERROR_REQUIRED')
        target = result.status
        if target == 'failed' and result.error and result.error.retryable and task.attempt_count < task.max_attempts:
            target = 'retrying'
        transition(task, target)
        # A retry must not discard a durable result produced before a queue
        # acknowledgement was lost.  New refs are merged by stable identity.
        existing = list(task.output_refs or [])
        seen = {(r.get('artifact_type'), r.get('artifact_id')) for r in existing}
        for ref in result.output_refs:
            key = (ref.artifact_type, ref.artifact_id)
            if key not in seen:
                existing.append(ref.model_dump(mode='json'))
                seen.add(key)
        task.output_refs = existing
        task.completion_payload = {**result.model_dump(mode='json'), 'metrics': {**(task.completion_payload or {}).get('metrics', {}), **result.metrics}}
        selection = (task.blocker_reason or {}).get('selected_result_ids')
        task.blocker_reason = result.waiting or (result.error.model_dump() if result.error else None)
        if selection is not None:
            task.blocker_reason = {**(task.blocker_reason or {}), 'selected_result_ids': selection}
        task.error_code = result.error.code if result.error else None
        task.error_message = result.error.message if result.error else None

    def decide(self, tasks):
        statuses = {t.status for t in tasks}
        if not tasks or statuses <= {'completed'}:
            return 'completed'
        if 'waiting_user' in statuses:
            return 'waiting_user'
        if 'blocked' in statuses:
            return 'blocked'
        if statuses & {'failed', 'partial'}:
            return 'partial' if any(t.output_refs for t in tasks) else 'failed'
        if 'cancelled' in statuses:
            return 'cancelled'
        if 'retrying' in statuses:
            return 'retrying'
        return 'running'


class TaskDispatcher:
    def select_executor(self, task):
        """Select an incumbent capability adapter, never a new runtime."""
        route = EXECUTOR_ROUTES.get((task.task_type, task.executor_type))
        if route is None:
            raise ValueError('TASK_EXECUTOR_UNSUPPORTED')
        return route

    async def dispatch(self, db, execution, tasks):
        if execution.status in TERMINAL | {'paused', 'waiting_user', 'blocked'}:
            return
        done = {t.task_id for t in tasks if t.status == 'completed'}
        for task in tasks:
            if task.status == 'pending' and set(task.dependencies) <= done:
                self.select_executor(task)
                # Materialize structured predecessor references before publication.
                existing = list(task.input_refs or [])
                seen = {(r.get('artifact_type'), r.get('artifact_id')) for r in existing}
                for parent in tasks:
                    if parent.task_id not in task.dependencies:
                        continue
                    for ref in parent.output_refs or []:
                        key = (ref.get('artifact_type'), ref.get('artifact_id'))
                        if key not in seen:
                            existing.append(ref)
                            seen.add(key)
                task.input_refs = existing
                transition(task, 'queued')
                await db.commit()
                await enqueue_job('research_task', {'execution_id': execution.id, 'task_id': task.task_id}, job_id=task.task_id)
                # Serial dispatch simplifies project mutations while preserving a DAG.
                return


class ResearchOrchestrator:
    def __init__(self, db):
        self.db = db
        self.evaluator = CompletionEvaluator()
        self.dispatcher = TaskDispatcher()

    async def tasks(self, execution_id):
        return list((await self.db.scalars(select(ResearchTask).where(ResearchTask.execution_id == execution_id)
                    .order_by(ResearchTask.created_at, ResearchTask.task_id))).all())

    async def initialize(self, execution):
        if execution.plan is not None:
            # Recovery NEVER replans.  It only reconciles the persisted plan
            # and task statuses with the queue.
            await self.advance(execution)
            return
        goal = GoalResolver().resolve(execution.agent_type, execution.input_payload, execution.goal)
        snapshot = await ProjectStateReader(self.db).read(execution.project_id, execution.user_id)
        plan = PlanBuilder().build(execution.id, goal, snapshot)
        execution.plan = plan.model_dump(mode='json')
        execution.plan_version = plan.plan_version
        for item in plan.tasks:
            self.db.add(ResearchTask(**item.model_dump(exclude={'reason', 'input_refs'}), execution_id=execution.id,
                status='pending', input_refs=[r.model_dump() for r in item.input_refs],
                output_refs=[], attempt_count=0, max_attempts=4))
        if execution.status == 'pending':
            transition_execution(execution, 'queued')
        if plan.missing_dependencies:
            if execution.status != 'blocked':
                transition_execution(execution, 'blocked')
            execution.blockers = [d.model_dump() for d in plan.missing_dependencies]
            execution.error_code = 'GOAL_DEPENDENCIES_MISSING'
            execution.error_message = '目标缺少可用的项目前置资产'
        elif not plan.tasks:
            if execution.status != 'running':
                transition_execution(execution, 'running')
            transition_execution(execution, 'completed')
            execution.completion_reason = 'All required assets already exist'
            execution.result_payload = {
                'status': 'completed', 'output_refs': [r.model_dump(mode='json') for r in plan.reused_assets],
                'completion': {'reused_project_assets': True, 'passed': True},
            }
        await self.db.commit()
        await self.advance(execution)

    async def advance(self, execution):
        tasks = await self.tasks(execution.id)
        if execution.status == 'pending':
            transition_execution(execution, 'queued')
        execution.progress = [{'id': t.task_id, 'label': LABELS[t.task_type], 'status': t.status} for t in tasks]
        await self.db.commit()
        if execution.status not in TERMINAL | {'blocked', 'waiting_user', 'paused'}:
            await self.dispatcher.dispatch(self.db, execution, tasks)
            execution.progress = [{'id': t.task_id, 'label': LABELS[t.task_type], 'status': t.status} for t in tasks]
            await self.db.commit()

    async def complete(self, execution, task, result):
        # Re-read after executor commits; API cancellation wins over late output.
        await self.db.refresh(execution)
        await self.db.refresh(task)
        if task.status in TERMINAL:
            # Duplicate queue delivery is harmless once a task has a durable
            # terminal result.  Reconcile any downstream dispatch gap only.
            await self.advance(execution)
            return
        if execution.status == 'cancelled':
            if task.status not in TERMINAL:
                transition(task, 'cancelled')
            await self.db.commit()
            return
        from app.models.project import WritingArtifact, ProjectPaper
        from app.models.research import EvidenceItem
        for ref in result.output_refs:
            if ref.artifact_type == 'paper':
                owned = await self.db.scalar(select(ProjectPaper.id).where(ProjectPaper.project_id == execution.project_id,
                                                                          ProjectPaper.paper_id == ref.artifact_id))
            else:
                model = {'paper_card': ProjectPaper, 'evidence': EvidenceItem}.get(ref.artifact_type, WritingArtifact)
                owned = await self.db.scalar(select(model.id).where(model.id == ref.artifact_id, model.project_id == execution.project_id))
            if not owned:
                raise ValueError('OUTPUT_ARTIFACT_NOT_FOUND')
        self.evaluator.apply(execution, task, result)
        tasks = await self.tasks(execution.id)
        target = self.evaluator.decide(tasks)
        if execution.status != 'paused' and target != execution.status:
            transition_execution(execution, target)
        execution.blockers = [{'task_id': t.task_id, 'context': t.blocker_reason} for t in tasks
                              if t.status in {'blocked', 'waiting_user'}] or None
        execution.completion_reason = target
        if result.error:
            execution.error_code = result.error.code
            execution.error_message = result.error.message
        elif target == 'waiting_user':
            execution.error_code = 'WAITING_USER_INPUT'
            execution.error_message = (result.waiting or {}).get('prompt', '等待用户输入')
        elif target == 'completed':
            execution.error_code = None
            execution.error_message = None
        execution.result_payload = {
            'status': target,
            'output_refs': [ref for item in tasks for ref in (item.output_refs or [])],
            'completion': {'all_tasks_completed': target == 'completed', 'passed': target == 'completed'},
        }
        await self.db.commit()
        await save_checkpoint(execution.id, {'plan_version': execution.plan_version, 'task_id': task.task_id, 'status': task.status})
        await append_event(self.db, execution, 'progress_changed', LABELS[task.task_type], stage=task.status,
                           data={'task_id': task.task_id, 'status': task.status})
        await self.advance(execution)

    async def control(self, execution, action, response=None):
        tasks = await self.tasks(execution.id)
        if action == 'cancel':
            if execution.status not in TERMINAL:
                transition_execution(execution, 'cancelled')
            for task in tasks:
                if task.status not in TERMINAL:
                    if task.status != 'cancelled':
                        transition(task, 'cancelled')
        elif action == 'pause':
            if execution.status in TERMINAL:
                raise ValueError('EXECUTION_TERMINAL')
            if execution.status != 'paused':
                transition_execution(execution, 'paused')
        else:
            if execution.status == 'waiting_user':
                waiting = next(t for t in tasks if t.status == 'waiting_user')
                selection = (response or {}).get('selected_result_ids')
                options = (waiting.blocker_reason or {}).get('options', [])
                allowed = {o['result_id'] for o in options if o.get('import_available')}
                if not isinstance(selection, list) or not selection or len(selection) != len(set(selection)) or not set(selection) <= allowed:
                    raise ValueError('SELECT_VALID_IMPORT_RESULTS')
                waiting.blocker_reason = {**waiting.blocker_reason, 'selected_result_ids': selection}
                transition(waiting, 'queued')
            elif execution.status not in {'paused', 'blocked'}:
                raise ValueError('EXECUTION_NOT_RESUMABLE')
            if execution.status == 'blocked':
                from app.research.task_contracts import GoalInput
                from app.application.research_planning import DependencyResolver
                state = await ProjectStateReader(self.db).read(execution.project_id, execution.user_id)
                deps = DependencyResolver().resolve(GoalInput.model_validate(execution.plan['goal']), state)
                if not tasks or any(d.kind == 'hard' and not d.satisfied for d in deps):
                    raise ValueError('GOAL_DEPENDENCIES_MISSING')
            if execution.status != 'queued':
                transition_execution(execution, 'queued')
            for task in tasks:
                if task.status == 'blocked':
                    transition(task, 'queued')
            execution.blockers = None
            execution.error_code = None
            execution.error_message = None
        await self.db.commit()
        await self.advance(execution)
        if action in {'resume', 'approve'}:
            for task in tasks:
                if task.status in {'queued', 'running', 'retrying'}:
                    await enqueue_job('research_task', {'execution_id': execution.id, 'task_id': task.task_id}, job_id=task.task_id)
        await append_event(self.db, execution, f'execution_{action}', '执行状态已更新', stage=execution.status)
