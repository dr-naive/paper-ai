from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.application.project_execution_entrypoint import (
    classify_project_entry,
    classify_instant_interaction,
    is_project_goal_execution,
)


def test_project_entrypoint_keeps_goal_and_instant_interaction_boundaries():
    assert classify_project_entry('research_goal') == 'goal'
    assert classify_project_entry('writing_generate') == 'goal'
    assert classify_project_entry('paper_chat', interaction_kind='paper_chat') == 'instant'
    assert classify_project_entry('paper_summary', interaction_kind='paper_summary') == 'instant'
    assert classify_instant_interaction('paper_chat') == 'instant'
    assert classify_instant_interaction('writing_selection_proposal') == 'instant'
    with pytest.raises(ValueError, match='UNSUPPORTED_PROJECT_ENTRY'):
        classify_project_entry('unknown')


def test_historical_writing_execution_is_recognized_without_making_new_worker_lifecycle():
    assert is_project_goal_execution(SimpleNamespace(agent_type='writing_generate', plan_version=0)) is True
    assert is_project_goal_execution(SimpleNamespace(agent_type='research_goal', plan_version=1)) is True
    assert is_project_goal_execution(SimpleNamespace(agent_type='paper_chat', plan_version=0)) is False


def test_goal_execution_stream_stops_at_recoverable_waiting_states():
    from app.api.executions import STREAM_STOP_STATUSES
    from app.models.execution import TERMINAL_EXECUTION_STATUSES

    assert TERMINAL_EXECUTION_STATUSES <= STREAM_STOP_STATUSES
    assert {'waiting_user', 'blocked', 'paused'} <= STREAM_STOP_STATUSES


def test_project_reading_worker_lifecycle_is_not_registered():
    worker_source = (Path(__file__).resolve().parents[1] / 'app' / 'worker.py').read_text(encoding='utf-8')
    reading_service_source = (Path(__file__).resolve().parents[1] / 'app' / 'application' / 'reading_execution_service.py').read_text(encoding='utf-8')

    assert 'handle_project_reading_execution' not in worker_source
    assert 'project_reading_execution' not in worker_source
    assert 'paperai:reading-execution:' not in reading_service_source


def test_historical_agent_execution_message_is_adapted_to_orchestrator(monkeypatch):
    from app import worker
    from app.job_queue import WorkerJob

    execution = SimpleNamespace(id='execution-1', agent_type='writing_generate', status='queued')

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, model, identifier):
            return execution

    initialize = AsyncMock()
    monkeypatch.setattr(worker, 'AsyncSessionLocal', lambda: Session())
    monkeypatch.setattr('app.application.project_execution_entrypoint.initialize_project_goal', initialize)

    awaitable = worker.handle_agent_execution_v2(WorkerJob.create('agent_execution_v2', {'execution_id': execution.id}))

    import asyncio
    asyncio.run(awaitable)
    initialize.assert_awaited_once()
