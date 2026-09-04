from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.job_queue import WorkerJob
from app.models.paper import Paper, Section
from app.models.project import ProjectPaper, ResearchProject
from app.research.context.paper_profile import (
    PAPER_PROFILE_VERSION,
    PaperProfile,
    PaperProfileBundle,
    PaperProfileContent,
    PaperProfileNotFoundError,
    PaperProfileNotReadyError,
    PaperProfileService,
    paper_profile_is_stale,
    paper_source_fingerprint,
    read_paper_profile,
    write_paper_profile,
)
from app.research.context.paper_profile_generator import (
    PROFILE_INPUT_MAX_CHARS,
    PaperProfileGenerator,
    build_profile_source,
)


def _bundle() -> PaperProfileBundle:
    project = ResearchProject(
        id="project-1",
        user_id="user-1",
        title="Project",
        research_topic="Reliable retrieval",
        preferences={"research_scope": {"field": "Information Retrieval", "keywords": ["RAG"]}},
    )
    paper = Paper(
        id="paper-1",
        user_id="user-1",
        title="A Retrieval Paper",
        authors="Ada Lovelace",
        abstract="This paper evaluates a retrieval method.",
        full_text="parsed",
        keywords=["retrieval"],
        updated_at=datetime(2026, 8, 23, 2),
    )
    sections = [
        Section(
            id="section-intro",
            paper_id=paper.id,
            section_title="Introduction",
            order_index=0,
            content="The research question is explicit.",
            created_at=datetime(2026, 8, 23, 1),
        ),
        Section(
            id="section-method",
            paper_id=paper.id,
            section_title="Methods",
            order_index=1,
            content="The method uses bounded retrieval.",
            created_at=datetime(2026, 8, 23, 1),
        ),
        Section(
            id="section-result",
            paper_id=paper.id,
            section_title="Results",
            order_index=2,
            content="The reported result is more stable.",
            created_at=datetime(2026, 8, 23, 1),
        ),
    ]
    membership = ProjectPaper(
        id="membership-1",
        project_id=project.id,
        paper_id=paper.id,
        analysis_card={"summary": "legacy reading card", "evidence": [{"source_id": "S1"}]},
    )
    return PaperProfileBundle(project, membership, paper, sections)


def _profile(bundle: PaperProfileBundle, **changes) -> PaperProfile:
    values = {
        "project_id": bundle.project.id,
        "paper_id": bundle.paper.id,
        "status": "ready",
        "source_fingerprint": paper_source_fingerprint(bundle.paper, bundle.sections),
        "topic": "retrieval",
    }
    values.update(changes)
    return PaperProfile(**values)


def test_paper_profile_schema_allows_missing_academic_fields_and_is_versioned():
    bundle = _bundle()
    profile = _profile(bundle, topic="")

    assert profile.profile_version == PAPER_PROFILE_VERSION
    assert profile.methods == []
    assert profile.datasets_or_samples == []
    assert profile.generated_at is None


def test_profile_storage_preserves_existing_analysis_card_fields():
    bundle = _bundle()
    write_paper_profile(bundle.project_paper, _profile(bundle))

    assert bundle.project_paper.analysis_card["summary"] == "legacy reading card"
    assert bundle.project_paper.analysis_card["evidence"] == [{"source_id": "S1"}]
    assert read_paper_profile(bundle.project_paper.analysis_card).topic == "retrieval"


def test_profile_invalidation_detects_parse_and_version_changes():
    bundle = _bundle()
    fingerprint = paper_source_fingerprint(bundle.paper, bundle.sections)
    profile = _profile(bundle)

    assert paper_profile_is_stale(profile, fingerprint) is False
    bundle.sections[0].content += " changed"
    assert paper_profile_is_stale(profile, paper_source_fingerprint(bundle.paper, bundle.sections)) is True
    assert paper_profile_is_stale(profile.model_copy(update={"profile_version": 0}), fingerprint) is True


def test_profile_source_uses_bounded_representative_sections_not_full_text():
    bundle = _bundle()
    bundle.paper.full_text = "SHOULD_NOT_APPEAR" * 10_000
    bundle.sections[1].content = "method " * 10_000

    source = build_profile_source(bundle.paper, bundle.sections)
    combined = source.metadata + source.sections

    assert "Introduction" in source.sections
    assert "Methods" in source.sections
    assert "Results" in source.sections
    assert "SHOULD_NOT_APPEAR" not in combined
    assert len(combined) <= PROFILE_INPUT_MAX_CHARS


@pytest.mark.asyncio
async def test_generator_returns_validated_structured_content(monkeypatch):
    bundle = _bundle()
    response = SimpleNamespace(
        generations=[[SimpleNamespace(text='{"topic":"retrieval","research_questions":[],"research_subjects":[],"methods":["dense retrieval"],"datasets_or_samples":[],"main_results":[],"conclusions":[],"contributions":[],"limitations":[],"keywords":["RAG"],"project_relevance":"relevant"}')]]
    )
    llm = SimpleNamespace(agenerate=AsyncMock(return_value=response))
    monkeypatch.setattr("app.research.context.paper_profile_generator.settings.LLM_PROVIDER", "qwen")
    monkeypatch.setattr("app.research.context.paper_profile_generator.settings.OPENAI_MODEL", "test-model")

    content = await PaperProfileGenerator(llm).generate(bundle.project, bundle.paper, bundle.sections)

    assert content.methods == ["dense retrieval"]
    assert content.keywords == ["RAG"]
    llm.agenerate.assert_awaited_once()


@pytest.mark.asyncio
async def test_generation_request_queues_parsed_project_paper_and_retry(monkeypatch):
    bundle = _bundle()
    db = SimpleNamespace(commit=AsyncMock())
    service = PaperProfileService(db)
    service._load_bundle = AsyncMock(return_value=bundle)
    enqueue = AsyncMock(return_value=SimpleNamespace(id="job-1"))
    monkeypatch.setattr("app.research.context.paper_profile.enqueue_job", enqueue)

    pending = await service.request_generation(
        project_id=bundle.project.id,
        paper_id=bundle.paper.id,
        user_id=bundle.project.user_id,
    )
    failed = pending.model_copy(update={"status": "failed"})
    write_paper_profile(bundle.project_paper, failed)
    retried = await service.request_generation(
        project_id=bundle.project.id,
        paper_id=bundle.paper.id,
        user_id=bundle.project.user_id,
        force=True,
    )

    assert pending.status == "pending"
    assert retried.status == "pending"
    assert retried.retry_count == 1
    assert enqueue.await_count == 2


@pytest.mark.asyncio
async def test_generation_request_rejects_unparsed_paper_without_queueing(monkeypatch):
    bundle = _bundle()
    bundle.sections = []
    bundle.paper.full_text = ""
    db = SimpleNamespace(commit=AsyncMock())
    service = PaperProfileService(db)
    service._load_bundle = AsyncMock(return_value=bundle)
    enqueue = AsyncMock()
    monkeypatch.setattr("app.research.context.paper_profile.enqueue_job", enqueue)

    with pytest.raises(PaperProfileNotReadyError):
        await service.request_generation(
            project_id=bundle.project.id,
            paper_id=bundle.paper.id,
            user_id=bundle.project.user_id,
        )

    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_profile_service_hides_foreign_project():
    project = _bundle().project
    db = SimpleNamespace(get=AsyncMock(return_value=project))

    with pytest.raises(PaperProfileNotFoundError):
        await PaperProfileService(db)._load_bundle(project.id, "paper-1", "other-user")


@pytest.mark.asyncio
async def test_generation_failure_is_persisted_without_removing_reader_assets(monkeypatch):
    bundle = _bundle()
    pending = _profile(bundle, status="pending", topic="")
    write_paper_profile(bundle.project_paper, pending)
    db = SimpleNamespace(commit=AsyncMock())
    service = PaperProfileService(db)
    service._load_bundle = AsyncMock(return_value=bundle)

    class FailingGenerator:
        source_model = "test-model"

        async def generate(self, project, paper, sections):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        "app.research.context.paper_profile_generator.PaperProfileGenerator",
        FailingGenerator,
    )

    result = await service.run_generation(
        project_id=bundle.project.id,
        paper_id=bundle.paper.id,
        expected_fingerprint=pending.source_fingerprint,
    )

    assert result.status == "failed"
    assert result.error_code == "PROFILE_GENERATION_FAILED"
    assert bundle.paper.full_text == "parsed"
    assert bundle.project_paper.analysis_card["summary"] == "legacy reading card"


@pytest.mark.asyncio
async def test_successful_generation_updates_only_profile_subdocument(monkeypatch):
    bundle = _bundle()
    pending = _profile(bundle, status="pending", topic="")
    write_paper_profile(bundle.project_paper, pending)
    db = SimpleNamespace(commit=AsyncMock())
    service = PaperProfileService(db)
    service._load_bundle = AsyncMock(return_value=bundle)

    class SuccessfulGenerator:
        source_model = "test-model"

        async def generate(self, project, paper, sections):
            return PaperProfileContent(topic="bounded retrieval", methods=["retrieval"])

    monkeypatch.setattr(
        "app.research.context.paper_profile_generator.PaperProfileGenerator",
        SuccessfulGenerator,
    )

    result = await service.run_generation(
        project_id=bundle.project.id,
        paper_id=bundle.paper.id,
        expected_fingerprint=pending.source_fingerprint,
    )

    assert result.status == "ready"
    assert result.source_model == "test-model"
    assert result.generated_at
    assert bundle.project_paper.analysis_card["summary"] == "legacy reading card"


@pytest.mark.asyncio
async def test_parse_worker_completion_triggers_profile_scheduling(monkeypatch):
    from app import worker
    from app.api import papers as papers_api

    process = AsyncMock()
    schedule = AsyncMock(return_value=[])
    monkeypatch.setattr(papers_api, "_schedule_process_paper", process)
    monkeypatch.setattr(worker, "schedule_profiles_for_parsed_paper", schedule)

    session = SimpleNamespace()

    class SessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(worker, "AsyncSessionLocal", lambda: SessionContext())
    job = WorkerJob.create(
        "paper_process",
        {"paper_id": "paper-1", "file_path": "/tmp/paper.pdf", "user_id": "user-1"},
    )

    await worker.handle_paper_process(job)

    process.assert_awaited_once()
    schedule.assert_awaited_once_with(session, "paper-1", force=True)


@pytest.mark.asyncio
async def test_profile_schedule_failure_does_not_fail_completed_parse(monkeypatch):
    from app import worker
    from app.api import papers as papers_api

    monkeypatch.setattr(papers_api, "_schedule_process_paper", AsyncMock())
    monkeypatch.setattr(
        worker,
        "schedule_profiles_for_parsed_paper",
        AsyncMock(side_effect=RuntimeError("queue unavailable")),
    )

    class SessionContext:
        async def __aenter__(self):
            return SimpleNamespace()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(worker, "AsyncSessionLocal", lambda: SessionContext())
    job = WorkerJob.create(
        "paper_process",
        {"paper_id": "paper-1", "file_path": "/tmp/paper.pdf", "user_id": "user-1"},
    )

    await worker.handle_paper_process(job)
