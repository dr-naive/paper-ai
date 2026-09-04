from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api import discovery as discovery_api
from app.models.project import ResearchProject
from app.research.discovery.favorites import (
    FavoriteSourceError,
    favorite_keys,
    list_favorites,
    remove_favorite,
    save_favorite,
)
from app.research.discovery.schemas import (
    DiscoveryFavoriteRequest,
    DiscoveryImportRequest,
    LiteratureSearchResponse,
    PaperSearchResultDTO,
)


class FakeDB:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def _project(project_id: str) -> ResearchProject:
    return ResearchProject(
        id=project_id,
        user_id=f"owner-{project_id}",
        title=f"Project {project_id}",
        research_topic="retrieval",
        preferences={},
    )


def _favorite_request(**overrides: object) -> DiscoveryFavoriteRequest:
    values: dict[str, object] = {
        "result_id": "result-1",
        "source": "ARXIV",
        "source_paper_id": "2401.12345",
        "title": "A Retrieval Study",
        "authors": ["Ada Lovelace"],
        "abstract": "A complete abstract",
        "paper_url": "https://arxiv.org/abs/2401.12345",
        "pdf_url": "https://arxiv.org/pdf/2401.12345.pdf",
        "year": 2024,
    }
    values.update(overrides)
    return DiscoveryFavoriteRequest.model_validate(values)


@pytest.mark.asyncio
async def test_favorite_is_idempotent_and_stores_normalized_metadata_only() -> None:
    project = _project("one")
    db = FakeDB()

    first = await save_favorite(db, project, _favorite_request())
    second = await save_favorite(db, project, _favorite_request(title="Updated title"))

    assert first.favorite_id == second.favorite_id
    assert second.title == "Updated title"
    assert second.source == "arxiv"
    assert second.import_available is True
    assert len(list_favorites(project)) == 1
    assert favorite_keys(project) == {"arxiv:2401.12345"}
    assert db.commits == 2


def test_search_results_reflect_project_favorite_state():
    project = _project("one")
    project.preferences = {
        "discovery_favorites": [{
            "favorite_id": "favorite-1",
            "saved_at": "2026-08-23T00:00:00",
            "result_id": "result-1",
            "source": "arxiv",
            "source_paper_id": "2401.12345",
            "title": "A Retrieval Study",
        }]
    }
    response = LiteratureSearchResponse(
        execution_id="execution-1",
        papers=[PaperSearchResultDTO(
            result_id="result-1",
            source="arxiv",
            source_paper_id="2401.12345",
            title="A Retrieval Study",
        )],
        provider="arxiv",
        result_count=1,
        search_rounds=1,
    )

    updated = discovery_api._with_favorite_state(project, response)

    assert updated.papers[0].is_favorite is True


@pytest.mark.asyncio
async def test_favorites_are_isolated_per_project_and_remove_is_scoped() -> None:
    first_project = _project("one")
    second_project = _project("two")
    db = FakeDB()

    first = await save_favorite(db, first_project, _favorite_request())
    second = await save_favorite(db, second_project, _favorite_request())

    assert first.favorite_id != second.favorite_id
    assert favorite_keys(first_project) == {"arxiv:2401.12345"}
    assert favorite_keys(second_project) == {"arxiv:2401.12345"}
    assert await remove_favorite(db, second_project, first.favorite_id) is False
    assert len(list_favorites(first_project)) == 1
    assert await remove_favorite(db, first_project, first.favorite_id) is True
    assert list_favorites(first_project) == []


@pytest.mark.asyncio
async def test_favorite_rejects_unknown_source_and_oversized_payload():
    with pytest.raises(FavoriteSourceError):
        await save_favorite(FakeDB(), _project("one"), _favorite_request(source="publisher"))

    with pytest.raises(ValidationError):
        _favorite_request(abstract="x" * 20_001)

    with pytest.raises(ValidationError):
        DiscoveryFavoriteRequest.model_validate({**_favorite_request().model_dump(), "raw": "payload"})


def test_import_request_requires_approved_locator_or_normalized_result_id():
    with pytest.raises(ValidationError):
        DiscoveryImportRequest(source="arxiv", source_paper_id="2401.12345")

    request = DiscoveryImportRequest(
        source="arxiv",
        source_paper_id="2401.12345",
        approved_pdf_locator="https://arxiv.org/pdf/2401.12345.pdf",
    )
    assert request.source == "arxiv"


@pytest.mark.asyncio
async def test_import_endpoint_rejects_unapproved_remote_locator(monkeypatch):
    tool_called = False

    async def fake_user_id(authorization, db):
        return "user-1"

    async def fake_owned_project(db, project_id, user_id):
        return _project(project_id)

    monkeypatch.setattr(discovery_api, "get_current_user_id", fake_user_id)
    monkeypatch.setattr(discovery_api, "_owned_project", fake_owned_project)

    class FakeTool:
        name = "project_import_arxiv_paper"

        async def ainvoke(self, payload):
            nonlocal tool_called
            tool_called = True
            return "queued"

    monkeypatch.setattr(
        "app.harness.tools.literature_research.make_project_tools",
        lambda db, project_id, user_id: [FakeTool()],
    )

    with pytest.raises(Exception) as error:
        await discovery_api.import_discovery_paper(
            project_id="project-1",
            body=DiscoveryImportRequest(
                source="arxiv",
                source_paper_id="2401.12345",
                approved_pdf_locator="https://example.com/paper.pdf",
            ),
            authorization="Bearer token",
            db=SimpleNamespace(),
        )

    assert getattr(error.value, "status_code", None) == 422
    assert tool_called is False


@pytest.mark.asyncio
async def test_import_endpoint_preserves_existing_duplicate_import_state(monkeypatch):
    async def fake_user_id(authorization, db):
        return "user-1"

    async def fake_owned_project(db, project_id, user_id):
        return _project(project_id)

    monkeypatch.setattr(discovery_api, "get_current_user_id", fake_user_id)
    monkeypatch.setattr(discovery_api, "_owned_project", fake_owned_project)

    class FakeTool:
        name = "project_import_arxiv_paper"

        async def ainvoke(self, payload):
            assert payload["arxiv_id"] == "2401.12345"
            return "该论文正在导入，task_id=task_2401.12345，请等待解析完成。"

    monkeypatch.setattr(
        "app.harness.tools.literature_research.make_project_tools",
        lambda db, project_id, user_id: [FakeTool()],
    )

    response = await discovery_api.import_discovery_paper(
        project_id="project-1",
        body=DiscoveryImportRequest(
            source="arxiv",
            source_paper_id="https://arxiv.org/abs/2401.12345",
            result_id="result-1",
        ),
        authorization="Bearer token",
        db=SimpleNamespace(),
    )

    assert response.status == "processing"
    assert response.task_id == "task_2401.12345"
