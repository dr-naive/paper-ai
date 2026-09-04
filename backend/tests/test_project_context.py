from __future__ import annotations

from datetime import datetime

import pytest

from app.api.research_items import MEMORY_TYPES
from app.application.project_service import project_profile_dict
from app.models.project import ResearchProject
from app.models.research import MemoryItem
from app.research.context import ProjectContextManager, ProjectContextNotFoundError


class _Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)


class _Result:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return _Scalars(self.values)


class _ContextDB:
    def __init__(self, project, memory_items, project_paper_ids):
        self.project = project
        self.memory_items = memory_items
        self.project_paper_ids = project_paper_ids
        self.execute_count = 0

    async def get(self, model, project_id):
        return self.project if project_id == self.project.id else None

    async def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return _Result(self.memory_items)
        return _Result(self.project_paper_ids)


def _project() -> ResearchProject:
    return ResearchProject(
        id="project-1",
        user_id="user-1",
        title="  Retrieval Study ",
        research_topic="  Evidence-grounded retrieval ",
        abstract="Fallback user notes",
        phase="research",
        status="active",
        memory={"summary": "legacy must not enter discovery context", "notes": [{"text": "raw legacy"}]},
        preferences={
            "research_scope": {
                "field": " Information Retrieval ",
                "research_question": " Which retrieval strategy is most reliable? ",
                "keywords": ["RAG", "RAG", " evidence "],
            },
            "discovery_favorites": [
                {"source_paper_id": "arxiv:2401.1", "title": "raw metadata is not returned"},
            ],
            "paper_imports": [
                {"paper_id": "paper-ready", "status": "ready"},
                {"paper_id": "paper-queued", "status": "queued"},
            ],
        },
        updated_at=datetime(2026, 8, 23, 1, 2, 3),
    )


def test_project_profile_uses_existing_typed_scope_storage():
    profile = project_profile_dict(_project())

    assert profile["project_id"] == "project-1"
    assert profile["title"] == "Retrieval Study"
    assert profile["research_topic"] == "Evidence-grounded retrieval"
    assert profile["field"] == "Information Retrieval"
    assert profile["keywords"] == ["RAG", "evidence"]
    assert profile["user_notes"] == "Fallback user notes"


@pytest.mark.asyncio
async def test_discovery_context_is_typed_bounded_and_excludes_generic_memory():
    project = _project()
    memory = [
        MemoryItem(
            id="intent-1", project_id=project.id, user_id=project.user_id,
            type="literature_intent", title="intent", content="Confirmed intent",
            tags=["keyword:retrieval", "keyword:evidence"],
            updated_at=datetime(2026, 8, 23, 2),
        ),
        MemoryItem(
            id="excluded-1", project_id=project.id, user_id=project.user_id,
            type="literature_exclusion", title="exclude", content="Exclude opinion-only surveys",
            tags=["direction:opinion-only"], updated_at=datetime(2026, 8, 23, 1),
        ),
        MemoryItem(
            id="generic-1", project_id=project.id, user_id=project.user_id,
            type="finding", title="legacy", content="must not be selected",
            updated_at=datetime(2026, 8, 23, 3),
        ),
    ]
    context = await ProjectContextManager(
        _ContextDB(project, memory, ["paper-membership"])
    ).build_discovery_context(project.id, project.user_id)

    assert context.project_profile.research_question == "Which retrieval strategy is most reliable?"
    assert context.literature_memory.search_intent_summary == "Confirmed intent"
    assert context.literature_memory.important_keywords == ["retrieval", "evidence"]
    assert context.literature_memory.excluded_directions == ["opinion-only", "Exclude opinion-only surveys"]
    assert context.literature_memory.favorite_paper_ids == ["arxiv:2401.1"]
    assert context.literature_memory.imported_paper_ids == ["paper-ready", "paper-membership"]
    assert "must not be selected" not in context.model_dump_json()
    assert "raw metadata" not in context.model_dump_json()


@pytest.mark.asyncio
async def test_context_manager_checks_project_ownership():
    project = _project()
    db = _ContextDB(project, [], [])

    with pytest.raises(ProjectContextNotFoundError):
        await ProjectContextManager(db).build_discovery_context(project.id, "other-user")


def test_research_notes_api_keeps_legacy_types_and_accepts_typed_memory_types():
    assert "finding" in MEMORY_TYPES
    assert {"literature_intent", "literature_preference", "literature_exclusion", "project_decision"}.issubset(MEMORY_TYPES)
