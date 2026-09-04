from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app as _application  # noqa: F401 - register all ORM relationship targets
from app.models.paper import DocumentElement, Image, Paper, Section, Table, TableStructure
from app.models.project import ProjectPaper, ResearchProject
from app.models.user import User
from app.rag import hybrid_retrieval
from app.research.context.manager import ProjectContextManager
from app.research.context.paper_profile import PaperProfile, write_paper_profile
from app.research.context.schemas import (
    CandidatePaperContext,
    CandidateSelectionResult,
    EvidenceCandidateContext,
    ProjectProfileContext,
)
from app.research.context.selectors import (
    CandidatePaperSelector,
    CandidateSelectionProjectNotFoundError,
)
from app.research.evidence import retrieval as retrieval_module
from app.research.evidence.retrieval import ProjectEvidenceRetrievalService
from app.research.evidence.service import EvidenceProvenanceError, EvidenceService


class _Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)

    def first(self):
        return self.values[0] if self.values else None


class _Result:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)

    def scalars(self):
        return _Scalars(self.values)


def _project(project_id: str = "project-1", user_id: str = "user-1") -> ResearchProject:
    return ResearchProject(
        id=project_id,
        user_id=user_id,
        title="Evidence Project",
        research_topic="retrieval grounded academic writing",
        abstract="",
        preferences={"research_scope": {"research_question": "Which retrieval evidence is reliable?"}},
        memory={"summary": "must never enter writing context", "notes": [{"text": "raw chat"}]},
        updated_at=datetime(2026, 8, 23),
    )


def _profile(project_id: str, paper_id: str, *, status: str = "ready", keyword: str = "retrieval") -> PaperProfile:
    return PaperProfile(
        project_id=project_id,
        paper_id=paper_id,
        status=status,
        source_fingerprint="a" * 64,
        topic=f"{keyword} evidence",
        methods=[f"{keyword} method"],
        main_results=[f"{keyword} result"],
        keywords=[keyword],
        project_relevance=f"supports {keyword}",
    )


def _paper(paper_id: str, user_id: str = "user-1", title: str | None = None) -> Paper:
    return Paper(
        id=paper_id,
        user_id=user_id,
        title=title or f"Paper {paper_id}",
        authors="Ada, Lin",
        publication_year=2025,
        doi=f"10.1/{paper_id}",
    )


def _membership(project_id: str, paper_id: str, *, status: str = "ready", keyword: str = "retrieval") -> ProjectPaper:
    item = ProjectPaper(
        id=f"membership-{paper_id}",
        project_id=project_id,
        paper_id=paper_id,
        role="related",
        reading_priority=3,
        analysis_card={},
    )
    write_paper_profile(item, _profile(project_id, paper_id, status=status, keyword=keyword))
    return item


class _SelectorDB:
    def __init__(self, project, rows):
        self.project = project
        self.rows = rows

    async def get(self, model, object_id):
        if model is ResearchProject and object_id == self.project.id:
            return self.project
        return None

    async def execute(self, _statement):
        return _Result(self.rows)


@pytest.mark.asyncio
async def test_selector_uses_only_owned_ready_profiles_and_caps_candidates():
    project = _project()
    rows = []
    for index in range(7):
        paper_id = f"paper-{index}"
        rows.append((_membership(project.id, paper_id), _paper(paper_id)))
    rows.append((_membership(project.id, "pending", status="pending"), _paper("pending")))

    result = await CandidatePaperSelector(_SelectorDB(project, rows)).select(
        project_id=project.id,
        user_id=project.user_id,
        project_profile=ProjectProfileContext(
            project_id=project.id,
            title=project.title,
            research_topic=project.research_topic,
        ),
        instruction="retrieval evidence",
        limit=20,
    )

    assert result.imported_paper_count == 8
    assert result.ready_profile_count == 7
    assert len(result.candidates) == 5
    assert "pending" not in {item.paper_id for item in result.candidates}


@pytest.mark.asyncio
async def test_selector_hides_foreign_project():
    project = _project()
    with pytest.raises(CandidateSelectionProjectNotFoundError):
        await CandidatePaperSelector(_SelectorDB(project, [])).select(
            project_id=project.id,
            user_id="other-user",
            project_profile=ProjectProfileContext(
                project_id=project.id,
                title=project.title,
                research_topic=project.research_topic,
            ),
            instruction="evidence",
        )


class _RetrievalDB:
    def __init__(self, papers):
        self.papers = {paper.id: paper for paper in papers}

    async def get(self, model, object_id):
        if model is Paper:
            return self.papers.get(object_id)
        return None


@pytest.mark.asyncio
async def test_retrieval_calls_hybrid_only_for_selected_candidate_papers(monkeypatch):
    project = _project()
    papers = [_paper("paper-a"), _paper("paper-b"), _paper("paper-not-selected")]
    db = _RetrievalDB(papers)
    candidates = [
        CandidatePaperContext(
            project_id=project.id,
            paper_id=paper.id,
            title=paper.title,
            authors=paper.authors,
            publication_year=paper.publication_year,
            doi=paper.doi,
            profile_status="ready",
            profile_version=1,
            topic="retrieval",
            selection_score=0.8,
        )
        for paper in papers[:2]
    ]

    class Selector:
        async def select(self, **_kwargs):
            return CandidateSelectionResult(
                candidates=candidates,
                imported_paper_count=3,
                ready_profile_count=2,
            )

    calls = []

    class Retriever:
        def __init__(self, _db):
            pass

        async def retrieve(self, *, paper_id, **_kwargs):
            calls.append(paper_id)
            return SimpleNamespace(chunks=[{
                "content": f"Evidence from {paper_id}",
                "section": "Results",
                "section_id": f"section-{paper_id}",
                "chunk_index": 2,
                "page": 4,
                "rerank_score": 0.9,
                "retrieval_method": "bm25",
            }])

    monkeypatch.setattr(retrieval_module, "HybridPaperRetriever", Retriever)
    service = ProjectEvidenceRetrievalService(db)
    service.selector = Selector()
    status, selected, evidence = await service.retrieve(
        project_id=project.id,
        user_id=project.user_id,
        project_profile=ProjectProfileContext(
            project_id=project.id,
            title=project.title,
            research_topic=project.research_topic,
        ),
        instruction="retrieval evidence",
        max_candidates=5,
        top_k=4,
    )

    assert status == "ready"
    assert calls == ["paper-a", "paper-b"]
    assert {item.paper_id for item in selected} == {"paper-a", "paper-b"}
    assert {item.paper_id for item in evidence} == {"paper-a", "paper-b"}
    assert all(item.project_id == project.id and item.chunk_id.startswith("chunk:section-") for item in evidence)


@pytest.mark.asyncio
async def test_service_acceptance_retrieves_real_sections_from_candidate_project_papers(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        ResearchProject.__table__,
        Paper.__table__,
        ProjectPaper.__table__,
        Section.__table__,
        Table.__table__,
        TableStructure.__table__,
        Image.__table__,
    ]
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync_connection: User.metadata.create_all(sync_connection, tables=tables))
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    class EmptyKnowledgeBase:
        async def query(self, *_args, **_kwargs):
            return []

    monkeypatch.setattr(hybrid_retrieval, "get_knowledge_base", lambda: EmptyKnowledgeBase())
    async with session_factory() as session:
        user = User(id="user-real", username="real", email="real@example.com", password_hash="hash")
        project = _project("project-real", user.id)
        papers = [_paper("paper-real-a", user.id), _paper("paper-real-b", user.id)]
        memberships = [
            _membership(project.id, papers[0].id, keyword="autonomy"),
            _membership(project.id, papers[1].id, keyword="autonomy"),
        ]
        sections = [
            Section(
                id="section-real-a",
                paper_id=papers[0].id,
                section_title="Results",
                order_index=1,
                start_page=3,
                content="The intervention improved student autonomy and self-regulated learning.",
            ),
            Section(
                id="section-real-b",
                paper_id=papers[1].id,
                section_title="Findings",
                order_index=1,
                start_page=5,
                content="Survey evidence associates generative AI support with learner autonomy.",
            ),
        ]
        session.add_all([user, project, *papers, *memberships, *sections])
        await session.commit()

        context = await ProjectContextManager(session).build_writing_context(
            project_id=project.id,
            user_id=user.id,
            instruction="Summarize evidence about learner autonomy",
            current_section_title="Positive effects",
            max_candidates=5,
            top_k=4,
        )

    await engine.dispose()
    assert context.status == "ready"
    assert {item.paper_id for item in context.candidate_papers} == {"paper-real-a", "paper-real-b"}
    assert {item.paper_id for item in context.evidence} == {"paper-real-a", "paper-real-b"}
    assert {item.section_id for item in context.evidence} == {"section-real-a", "section-real-b"}
    assert all(item.chunk_id.startswith("chunk:section-real-") for item in context.evidence)


@pytest.mark.asyncio
async def test_writing_context_is_bounded_and_never_includes_project_memory(monkeypatch):
    project = _project()

    class DB:
        async def get(self, model, object_id):
            return project if model is ResearchProject and object_id == project.id else None

    async def fake_retrieve(_self, **_kwargs):
        return "no_imported_papers", [], []

    monkeypatch.setattr(
        retrieval_module.ProjectEvidenceRetrievalService,
        "retrieve",
        fake_retrieve,
    )
    context = await ProjectContextManager(DB()).build_writing_context(
        project_id=project.id,
        user_id=project.user_id,
        instruction="Write one grounded paragraph",
        nearby_text="nearby " * 3_000,
    )

    assert context.status == "no_imported_papers"
    assert len(context.nearby_text) == 12_000
    assert "must never enter" not in context.model_dump_json()
    assert "raw chat" not in context.model_dump_json()


class _EvidenceDB:
    def __init__(self, project, paper, membership, section=None, element=None):
        self.objects = {
            (ResearchProject, project.id): project,
            (Paper, paper.id): paper,
        }
        if section:
            self.objects[(Section, section.id)] = section
        if element:
            self.objects[(DocumentElement, element.id)] = element
        self.membership = membership
        self.added = []
        self.execute_count = 0

    async def get(self, model, object_id):
        return self.objects.get((model, object_id))

    async def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return _Result([self.membership] if self.membership else [])
        sections = [
            value
            for (model, _object_id), value in self.objects.items()
            if model is Section
        ]
        return _Result(sections)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        pass

    async def refresh(self, item):
        item.id = item.id or "evidence-1"


@pytest.mark.asyncio
async def test_persisted_evidence_rechecks_membership_and_real_source_locator():
    project = _project()
    paper = _paper("paper-a")
    membership = _membership(project.id, paper.id)
    section = Section(id="section-a", paper_id=paper.id, section_title="Results", order_index=1)
    db = _EvidenceDB(project, paper, membership, section=section)
    candidate = EvidenceCandidateContext(
        project_id=project.id,
        paper_id=paper.id,
        chunk_id="chunk:section-a:bm25-1",
        snippet="The method improves retrieval accuracy.",
        section_id=section.id,
        section_title=section.section_title,
        page_number=3,
        paper_title=paper.title,
        paper_authors=paper.authors,
        publication_year=paper.publication_year,
        doi=paper.doi,
        retrieval_score=0.9,
    )

    item = await EvidenceService(db).persist_used(
        candidate=candidate,
        user_id=project.user_id,
        normalized_claim="The method improves retrieval accuracy",
    )

    assert item.project_id == project.id
    assert item.paper_id == paper.id
    assert item.section_id == section.id
    assert item.chunk_id == candidate.chunk_id
    assert item.created_by == "retrieval"


@pytest.mark.asyncio
async def test_evidence_rejects_removed_paper_and_invalid_chunk_locator():
    project = _project()
    paper = _paper("paper-a")
    service = EvidenceService(_EvidenceDB(project, paper, membership=None))
    with pytest.raises(EvidenceProvenanceError, match="paper_not_in_project"):
        await service._owned_source(
            project_id=project.id,
            paper_id=paper.id,
            user_id=project.user_id,
        )

    service = EvidenceService(_EvidenceDB(project, paper, _membership(project.id, paper.id)))
    with pytest.raises(EvidenceProvenanceError, match="unverifiable_chunk"):
        await service.validate_locator(
            paper_id=paper.id,
            section_id=None,
            element_id=None,
            chunk_id="fabricated-chunk",
        )
    with pytest.raises(EvidenceProvenanceError, match="missing_locator"):
        await service.validate_locator(
            paper_id=paper.id,
            section_id=None,
            element_id=None,
            chunk_id=None,
        )
