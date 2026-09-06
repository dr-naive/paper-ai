"""Goal templates and durable worker integration in an isolated PostgreSQL schema."""
import asyncio
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app  # noqa: F401  # register incumbent model families
from app.database import Base
from app.config import settings
from app.models.user import User
from app.models.project import ResearchProject, WritingArtifact
from app.models.execution import AgentExecution
from app.application.research_planning import PlanBuilder
from app.application.research_orchestrator import CompletionEvaluator
from app.research.task_contracts import GoalInput, ProjectStateSnapshot, PaperState, ArtifactRef, TaskResult, TaskError, transition


def snapshot(papers=True, evidence=False):
    return ProjectStateSnapshot(project_id='p', user_id='u', captured_at=datetime.utcnow().isoformat(),
        papers=[PaperState(paper_id='paper', indexed=True, processing='completed')] if papers else [],
        assets=[ArtifactRef(artifact_type='document', artifact_id='doc', project_id='p'),
                *([ArtifactRef(artifact_type='evidence', artifact_id='ev', project_id='p')] if evidence else [])])


@pytest.mark.parametrize('papers,evidence,types,blocked', [
    (True, True, ['WRITE_SECTION', 'AUDIT_DRAFT'], False),
    (True, False, ['BUILD_EVIDENCE', 'WRITE_SECTION', 'AUDIT_DRAFT'], False),
    (False, False, ['BUILD_EVIDENCE', 'WRITE_SECTION', 'AUDIT_DRAFT'], True),
])
def test_write_dependencies(papers, evidence, types, blocked):
    plan = PlanBuilder().build('e', GoalInput(goal_type='WRITE_SECTION', document_id='doc', instruction='write',
        evidence_ids=['ev'] if evidence else []), snapshot(papers, evidence))
    assert [t.task_type for t in plan.tasks] == types
    assert bool(plan.missing_dependencies) == blocked
    assert all(t.task_type != 'DISCOVER' for t in plan.tasks)


def test_write_reuses_implicit_validated_project_evidence():
    state = snapshot(evidence=False)
    state.assets.append(ArtifactRef(artifact_type='evidence', artifact_id='ev-existing', project_id='p',
                                    source_paper_id='paper'))
    plan = PlanBuilder().build('e', GoalInput(goal_type='WRITE_SECTION', document_id='doc', instruction='write'), state)
    assert [t.task_type for t in plan.tasks] == ['WRITE_SECTION', 'AUDIT_DRAFT']
    assert any(ref.artifact_id == 'ev-existing' for ref in plan.reused_assets)


def test_dispatcher_routes_only_to_existing_capability_adapters():
    from types import SimpleNamespace
    from app.application.research_orchestrator import TaskDispatcher
    dispatcher = TaskDispatcher()
    assert dispatcher.select_executor(SimpleNamespace(task_type='READ_PAPER', executor_type='AGENT')) == 'task_scoped_lead_agent'
    assert dispatcher.select_executor(SimpleNamespace(task_type='AUDIT_DRAFT', executor_type='DETERMINISTIC')) == 'existing_citation_audit'
    with pytest.raises(ValueError, match='TASK_EXECUTOR_UNSUPPORTED'):
        dispatcher.select_executor(SimpleNamespace(task_type='READ_PAPER', executor_type='WORKFLOW'))


def test_read_reuses_cards_and_processing_is_not_an_extra_task_type():
    state = snapshot()
    goal = GoalInput(goal_type='READ_PAPERS')
    state.papers[0].indexed = False
    plan = PlanBuilder().build('e', goal, state)
    assert [t.task_type for t in plan.tasks] == ['READ_PAPER']
    assert 'processing' in plan.tasks[0].reason
    state.papers[0].card_ready = True
    assert PlanBuilder().build('e', goal, state).tasks == []


def test_plan_ids_stable_and_ownership_checked():
    builder, goal, state = PlanBuilder(), GoalInput(goal_type='READ_PAPERS'), snapshot()
    assert builder.build('e', goal, state) == builder.build('e', goal, state)
    with pytest.raises(ValueError, match='PAPER_NOT_IN_PROJECT'):
        builder.build('e', GoalInput(goal_type='READ_PAPERS', paper_ids=['foreign']), state)


def test_legacy_writing_generate_resolves_to_the_same_write_section_goal():
    from app.application.research_planning import GoalResolver

    goal = GoalResolver().resolve('writing_generate', {
        'document_id': 'doc', 'instruction': '写一段研究现状', 'section_path': ['引言'],
        'nearby_text': '上下文', 'citation_style': 'gbt7714', 'base_revision_id': 'rev',
    }, '兼容入口')

    assert goal.goal_type == 'WRITE_SECTION'
    assert goal.document_id == 'doc'
    assert goal.instruction == '写一段研究现状'


def test_state_machine_cannot_revive_cancelled_or_complete_blocked():
    item = SimpleNamespace(status='cancelled')
    with pytest.raises(ValueError):
        transition(item, 'running')
    item.status = 'blocked'
    with pytest.raises(ValueError):
        transition(item, 'completed')


def test_completion_is_structured_and_partial_keeps_outputs():
    evaluator = CompletionEvaluator()
    task = SimpleNamespace(task_id='t', status='running', attempt_count=1, max_attempts=4,
                           started_at=datetime.utcnow(), output_refs=[], completion_payload=None, blocker_reason=None)
    execution = SimpleNamespace(project_id='p')
    with pytest.raises(ValueError, match='TASK_COMPLETION_FAILED'):
        evaluator.apply(execution, task, TaskResult(task_id='t', status='completed'))
    evaluator.apply(execution, task, TaskResult(task_id='t', status='failed',
        error=TaskError(code='timeout', message='timeout', retryable=True)))
    assert task.status == 'retrying'
    task.status = 'failed'
    task.output_refs = [{'artifact_type': 'paper'}]
    assert evaluator.decide([task]) == 'partial'
    task.status = 'blocked'
    assert evaluator.decide([task]) == 'blocked'


def test_scope_rejects_foreign_resource_and_unrelated_tool():
    from app.harness.runtime.task_scope import TaskScope
    scope = TaskScope('t', 'READ_PAPER', 'p', 'u', frozenset(['paper']), frozenset(['paper.search_content']), 2, 2, AsyncMock())
    scope.check('search_paper_content', {'paper_id': 'paper'}, 1)
    for tool, args, calls in [('search_paper_content', {'paper_id': 'foreign'}, 1),
                               ('project_import_arxiv_paper', {}, 1), ('search_paper_content', {}, 3)]:
        with pytest.raises(PermissionError):
            scope.check(tool, args, calls)


async def integration_case(monkeypatch, scenario):
    from app.application import research_task_worker as worker
    from app.application import research_orchestrator as orch
    from app.application import research_planning as planning
    from app.application.research_task_executors import TaskExecutors
    from app.job_queue import WorkerJob
    schema = 'orch_test_' + uuid4().hex
    admin = create_async_engine(settings.DATABASE_URL)
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA {schema}'))
    test_engine = create_async_engine(settings.DATABASE_URL, connect_args={'server_settings': {'search_path': schema}})
    sessions = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    queue = []
    async def enqueue(kind, payload, **kwargs):
        queue.append(WorkerJob.create(kind, payload, kwargs.get('job_id')))
    monkeypatch.setattr(worker, 'AsyncSessionLocal', sessions)
    monkeypatch.setattr(worker, 'engine', test_engine)
    monkeypatch.setattr('app.worker.AsyncSessionLocal', sessions)
    monkeypatch.setattr(orch, 'enqueue_job', enqueue)
    monkeypatch.setattr('app.job_queue.enqueue_job', enqueue)
    monkeypatch.setattr(worker, 'get_control', AsyncMock(return_value=None))
    monkeypatch.setattr(worker, 'save_checkpoint', AsyncMock())
    monkeypatch.setattr(orch, 'save_checkpoint', AsyncMock())
    monkeypatch.setattr(worker, 'append_event', AsyncMock())
    monkeypatch.setattr(orch, 'append_event', AsyncMock())
    calls = []
    async def execute(adapter):
        calls.append(adapter.task.task_type)
        if scenario == 'retry' and len(calls) == 1:
            raise RuntimeError('temporary')
        if adapter.task.task_type == 'IMPORT_PAPER' and not adapter.task.blocker_reason:
            return TaskResult(task_id=adapter.task.task_id, status='waiting_user', waiting={
                'options': [{'result_id': 'r1', 'title': 'Real fixture', 'import_available': True}],
                'schema': {'selected_result_ids': {'type': 'array'}}})
        artifact = await adapter.artifact('section_draft', {'fixture': adapter.task.task_type})
        if scenario == 'interrupted' and len(calls) == 1:
            raise asyncio.CancelledError()
        if scenario == 'partial' and len(calls) == 2:
            return TaskResult(task_id=adapter.task.task_id, status='failed', error=TaskError(code='invalid', message='invalid'))
        return adapter.result([adapter.ref('section_draft', artifact.id)], saved=True)
    if not scenario.startswith('adapter_'):
        monkeypatch.setattr(TaskExecutors, 'execute', execute)
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            # Core persistence is real. Snapshot and capability outputs are controlled
            # so no provider secret or user project is required by this integration.
            db.add(User(id='u', username='orch', email='orch@example.invalid', password_hash='unused'))
            await db.commit()
            db.add(ResearchProject(id='p', user_id='u', title='Research', research_topic='research'))
            await db.commit()
            goal_type = 'DISCOVER_AND_IMPORT' if scenario in {'waiting', 'adapter_discover'} else 'READ_PAPERS' if scenario == 'adapter_read' else 'WRITE_SECTION'
            state = snapshot(papers=scenario != 'blocked')
            evidence_ids = []
            if scenario.startswith('adapter_'):
                evidence_ids = await seed_adapters(db, monkeypatch, scenario)
                state.assets.extend(ArtifactRef(artifact_type='evidence', artifact_id=e, project_id='p') for e in evidence_ids)
            monkeypatch.setattr(planning.ProjectStateReader, 'read', AsyncMock(return_value=state))
            execution = AgentExecution(id='e', project_id='p', user_id='u', agent_type='research_goal', goal='write',
                input_payload={'goal_type': goal_type, 'instruction': 'write', 'document_id': 'doc', 'evidence_ids': evidence_ids})
            db.add(execution)
            await db.commit()
            await orch.ResearchOrchestrator(db).initialize(execution)
            original_plan = execution.plan
            if scenario == 'blocked':
                assert execution.status == 'blocked' and not queue
                return
        if scenario == 'recovery':
            queue.clear()  # DB committed but publication was lost
            await worker.recover_tasks()
        first = queue.pop(0)
        if scenario == 'interrupted':
            with pytest.raises(asyncio.CancelledError):
                await worker.run_task(first)
            await worker.run_task(first)
        elif scenario == 'retry':
            with pytest.raises(RuntimeError):
                await worker.run_task(first)
            await worker.run_task(first)  # same WorkerJob after queue retry
        else:
            await worker.run_task(first)
        await worker.run_task(first)  # duplicate cannot generate another artifact
        if scenario == 'cancel':
            async with sessions() as db:
                execution = await db.get(AgentExecution, 'e')
                await orch.ResearchOrchestrator(db).control(execution, 'cancel')
        if scenario == 'pause':
            async with sessions() as db:
                execution = await db.get(AgentExecution, 'e')
                await orch.ResearchOrchestrator(db).control(execution, 'pause')
        while queue:
            await worker.run_task(queue.pop(0))
        if scenario == 'pause':
            assert calls == ['BUILD_EVIDENCE']
            async with sessions() as db:
                execution = await db.get(AgentExecution, 'e')
                await orch.ResearchOrchestrator(db).control(execution, 'resume')
            while queue:
                await worker.run_task(queue.pop(0))
        if scenario in {'waiting', 'adapter_discover'}:
            async with sessions() as db:
                execution = await db.get(AgentExecution, 'e')
                assert execution.status == 'waiting_user'
                with pytest.raises(ValueError):
                    await orch.ResearchOrchestrator(db).control(execution, 'approve', {'selected_result_ids': ['foreign']})
                await orch.ResearchOrchestrator(db).control(execution, 'approve', {'selected_result_ids': [execution.blockers[0]['context']['options'][0]['result_id']]})
            while queue:
                await worker.run_task(queue.pop(0))
        async with sessions() as db:
            execution = await db.get(AgentExecution, 'e')
            tasks = await orch.ResearchOrchestrator(db).tasks('e')
            assert execution.plan == original_plan
            if scenario == 'partial':
                assert execution.status == 'partial'
                assert any(t.output_refs for t in tasks)
                assert calls == ['BUILD_EVIDENCE', 'WRITE_SECTION']
                return
            if scenario == 'cancel':
                assert execution.status == 'cancelled'
                assert calls == ['BUILD_EVIDENCE']
            else:
                assert execution.status == 'completed', [(t.task_type, t.status, t.error_message) for t in tasks]
                assert all(t.status == 'completed' for t in tasks)
                if scenario.startswith('adapter_'):
                    assert all(t.output_refs for t in tasks)
                    if scenario == 'adapter_write':
                        assert execution.result_payload['completion']['passed']
                    return
                assert len(list((await db.scalars(select(WritingArtifact))).all())) == len(tasks)
                assert calls == (['DISCOVER', 'IMPORT_PAPER', 'IMPORT_PAPER'] if scenario == 'waiting' else
                    (['BUILD_EVIDENCE'] if scenario in {'retry', 'interrupted'} else []) + ['BUILD_EVIDENCE', 'WRITE_SECTION', 'AUDIT_DRAFT'])
    finally:
        await test_engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        await admin.dispose()


@pytest.mark.parametrize('scenario', ['normal', 'retry', 'waiting', 'cancel', 'blocked', 'recovery', 'interrupted', 'pause', 'partial', 'adapter_read', 'adapter_write', 'adapter_build', 'adapter_discover'])
def test_real_persistence_worker_loop(monkeypatch, scenario):
    asyncio.run(integration_case(monkeypatch, scenario))


async def seed_adapters(db, monkeypatch, scenario):
    from app.models.paper import Paper, Section
    from app.models.project import ProjectPaper
    from app.models.document import WritingDocument, DocumentRevision
    from app.research.context.schemas import WritingRetrievalContext, ProjectProfileContext, EvidenceCandidateContext
    from app.research.evidence.service import EvidenceService
    from app.application.writing_service import ParagraphGenerator, ParagraphModelOutput, WritingReviewer, WritingReviewDecision
    from app.application.citation_semantic_verifier import SemanticCitationVerifier, SemanticSupportDecision
    from app.research.context.manager import ProjectContextManager
    from app.research.context.paper_profile import PaperProfileService
    claim = 'The method improves retrieval accuracy.'
    db.add(Paper(id='paper', user_id='u', title='Retrieval study', full_text=claim, authors='Researcher'))
    db.add(WritingDocument(id='doc', project_id='p', title='Draft'))
    await db.commit()
    db.add(Section(id='section', paper_id='paper', section_title='Results', order_index=0, content=claim))
    db.add(ProjectPaper(id='pp', project_id='p', paper_id='paper'))
    db.add(DocumentRevision(id='rev', document_id='doc', version=1, content_json={'type': 'doc', 'content': []}))
    await db.commit()
    document = await db.get(WritingDocument, 'doc')
    document.current_revision_id = 'rev'
    await db.commit()
    candidate = EvidenceCandidateContext(project_id='p', paper_id='paper', section_id='section',
        chunk_id='chunk:section:0', snippet=claim, paper_title='Retrieval study')
    context = WritingRetrievalContext(status='ready', project_profile=ProjectProfileContext(project_id='p',
        title='Research', research_topic='research'), instruction='write', document_id='doc', evidence=[candidate])
    monkeypatch.setattr(ProjectContextManager, 'build_writing_context', AsyncMock(return_value=context))
    monkeypatch.setattr(PaperProfileService, 'run_generation', AsyncMock())
    monkeypatch.setattr(ParagraphGenerator, 'generate', AsyncMock(return_value=ParagraphModelOutput(
        content=claim + ' [[CITATION:c1]]', citations=[{'citation_key': 'c1', 'evidence_key': 'E1', 'claim_text': claim}])))
    monkeypatch.setattr(WritingReviewer, 'review', AsyncMock(return_value=WritingReviewDecision(verdict='pass')))
    monkeypatch.setattr(SemanticCitationVerifier, 'verify', AsyncMock(return_value=SemanticSupportDecision(
        status='verified', reason='Fixture source directly supports the claim', confidence=1)))
    monkeypatch.setattr('app.harness.agents.lead_agent.run_lead_agent', AsyncMock(return_value=SimpleNamespace(
        success=True, answer=claim, chunks=[{'source_id': 'S1', 'section_id': 'section', 'content': claim}])))
    if scenario == 'adapter_discover':
        from app.research.discovery.schemas import ProviderCapabilities, ProviderPaperDTO
        from app.research.discovery import workflow
        provider = SimpleNamespace(name='arxiv', capabilities=lambda: ProviderCapabilities(
            supports_year=True, supports_language=False, supports_field=False, supports_publication_type=False,
            returns_abstract=True, returns_pdf_url=True, returns_citation_count=False),
            search=AsyncMock(return_value=[ProviderPaperDTO(source_paper_id='2301.00001', title='write research',
                abstract='write research', pdf_url='https://arxiv.org/pdf/2301.00001', paper_url='https://arxiv.org/abs/2301.00001')]))
        monkeypatch.setattr(workflow, 'build_default_providers', lambda: (provider, ()))
        monkeypatch.setattr('app.worker.download_arxiv_pdf', AsyncMock(return_value=SimpleNamespace(file_path='/tmp/fixture.pdf', file_size=20)))
        async def process(paper_id, file_path, user_id, *args, **kwargs):
            db.add(Paper(id=paper_id, user_id=user_id, title='Imported fixture', full_text='parsed fixture'))
            await db.commit()
        monkeypatch.setattr('app.api.papers._schedule_process_paper', process)
        monkeypatch.setattr('app.worker.schedule_profiles_for_parsed_paper', AsyncMock())
        monkeypatch.setattr('app.worker.update_task', lambda *a, **k: None)
    if scenario == 'adapter_write':
        evidence = await EvidenceService(db).persist_used(candidate=candidate, user_id='u', normalized_claim=claim)
        return [evidence.id]
    return []


def test_existing_redis_queue_retry_recovery_and_dead_letter(monkeypatch):
    async def run():
        from redis.asyncio import Redis
        from app import job_queue as queue
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        prefix = 'orch-test:' + uuid4().hex
        keys = [prefix + ':' + name for name in ('waiting', 'processing', 'retry', 'failed')]
        for name, key in zip(('QUEUE_KEY', 'PROCESSING_KEY', 'RETRY_KEY', 'DEAD_LETTER_KEY'), keys):
            monkeypatch.setattr(queue, name, key)
        monkeypatch.setattr(queue, 'get_async_redis', lambda: client)
        monkeypatch.setattr(queue, 'RETRY_BASE_DELAY', 0)
        try:
            await queue.enqueue_job('research_task', {'execution_id': 'e', 'task_id': 't'}, job_id='t')
            job, raw = await queue.reserve_job()
            assert job.type == 'research_task' and job.payload['task_id'] == 't'
            assert await queue.recover_processing_jobs() == 1
            job, raw = await queue.reserve_job()
            await queue.fail_or_retry_job(job, raw, max_attempts=1)
            assert await queue.drain_retry_queue() == 1
            job, raw = await queue.reserve_job()
            assert job.attempts == 1
            await queue.fail_or_retry_job(job, raw, max_attempts=1)
            assert await client.llen(keys[-1]) == 1
            assert await client.llen(keys[0]) == 0
        finally:
            await client.delete(*keys)
            await client.aclose()
    asyncio.run(run())


def test_additive_migration_preserves_historical_execution():
    async def run():
        import importlib.util
        from pathlib import Path
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        schema = 'orch_migration_' + uuid4().hex
        admin = create_async_engine(settings.DATABASE_URL)
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA {schema}'))
        db_engine = create_async_engine(settings.DATABASE_URL, connect_args={'server_settings': {'search_path': schema}})
        spec = importlib.util.spec_from_file_location('migration', Path(__file__).parents[1] / 'alembic/versions/0007_research_tasks.py')
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        observability_spec = importlib.util.spec_from_file_location(
            'observability_migration',
            Path(__file__).parents[1] / 'alembic/versions/0008_agent_runtime_observability.py',
        )
        observability_migration = importlib.util.module_from_spec(observability_spec)
        observability_spec.loader.exec_module(observability_migration)
        def apply(conn, operation):
            with Operations.context(MigrationContext.configure(conn)):
                operation()
        try:
            async with db_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.run_sync(apply, observability_migration.downgrade)
                await conn.run_sync(apply, migration.downgrade)
                await conn.execute(text("INSERT INTO users (id, username, email, password_hash) VALUES ('u', 'u', 'u@example.invalid', 'x')"))
                await conn.execute(text("INSERT INTO agent_executions (id, user_id, agent_type, goal, input_payload, status, runtime_version, max_tool_calls, max_model_calls, max_tokens, max_seconds, tool_call_count, model_call_count, input_tokens, output_tokens, created_at, updated_at) VALUES ('old', 'u', 'writing_generate', 'old goal', '{}', 'paused', 'v2', 30, 20, 100000, 1800, 0, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
                await conn.run_sync(apply, migration.upgrade)
                await conn.run_sync(apply, observability_migration.upgrade)
                row = (await conn.execute(text("SELECT status, plan_version, plan, input_payload FROM agent_executions WHERE id='old'"))).one()
                assert row.status == 'paused' and row.plan_version == 0 and row.plan is None and row.input_payload == {}
                assert await conn.scalar(text('SELECT count(*) FROM research_tasks')) == 0
                assert await conn.scalar(text('SELECT count(*) FROM model_calls')) == 0
        finally:
            await db_engine.dispose()
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            await admin.dispose()
    asyncio.run(run())
