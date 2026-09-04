"""Project-scoped Literature Discovery workflow and execution-state APIs."""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_id
from app.database import get_db
from app.models.project import ResearchProject
from app.research.discovery.execution import load_execution_state, save_execution_state
from app.research.discovery.favorites import (
    FavoriteSourceError,
    favorite_key,
    favorite_keys,
    list_favorites,
    remove_favorite,
    save_favorite,
)
from app.research.discovery.schemas import (
    DiscoverySearchRequest,
    LiteratureSearchRequest,
    LiteratureSearchResponse,
    DiscoveryFavoriteRequest,
    DiscoveryFavoriteResponse,
    DiscoveryImportRequest,
    DiscoveryImportResponse,
)
from app.research.discovery.workflow import (
    DiscoveryProviderFailure,
    LiteratureDiscoveryWorkflow,
    build_default_providers,
)
from app.services.remote_paper_import import normalize_arxiv_id


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/discovery",
    tags=["literature-discovery"],
)


async def _owned_project(db: AsyncSession, project_id: str, user_id: str) -> ResearchProject:
    project = (
        await db.execute(
            select(ResearchProject).where(
                ResearchProject.id == project_id,
                ResearchProject.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在或无访问权限")
    return project


def _public_execution_state(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if key != "owner_id"}


def _with_favorite_state(project: ResearchProject, response: LiteratureSearchResponse) -> LiteratureSearchResponse:
    keys = favorite_keys(project)
    papers = [
        paper.model_copy(
            update={"is_favorite": favorite_key(paper.source, paper.source_paper_id) in keys}
        )
        for paper in response.papers
    ]
    return response.model_copy(update={"papers": papers})


def _parse_import_message(message: str) -> tuple[str, str | None, str | None]:
    if message.startswith("错误:"):
        return "failed", None, None
    status = "processing" if "正在导入" in message else "imported" if "已在用户论文库" in message else "queued"
    task_match = re.search(r"task_id=([\w.-]+)", message)
    paper_match = re.search(r"paper_id=([\w.-]+)", message)
    return status, task_match.group(1) if task_match else None, paper_match.group(1) if paper_match else None


@router.post("/search", response_model=LiteratureSearchResponse)
async def search_literature(
    project_id: str,
    body: DiscoverySearchRequest,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> LiteratureSearchResponse:
    user_id = await get_current_user_id(authorization, db)
    project = await _owned_project(db, project_id, user_id)
    execution_id = str(uuid4())
    state: dict[str, Any] = {
        "execution_id": execution_id,
        "project_id": project_id,
        "owner_id": user_id,
        "status": "preparing",
        "stage": "preparing",
        "message": "正在准备检索条件",
        "search_rounds": 0,
        "result_count": 0,
        "warnings": [],
        "papers": [],
    }
    await save_execution_state(execution_id, state)

    async def progress(payload: dict[str, Any]) -> None:
        state.update(payload)
        state["owner_id"] = user_id
        state["project_id"] = project_id
        await save_execution_state(execution_id, state)

    primary, fallbacks = build_default_providers()
    workflow = LiteratureDiscoveryWorkflow(
        primary_provider=primary,
        fallback_providers=fallbacks,
        progress=progress,
        execution_id=execution_id,
    )
    request = LiteratureSearchRequest(
        project_id=project_id,
        intent=body.intent,
        filters=body.filters,
        max_results=body.max_results,
    )
    try:
        response = await workflow.run(project_summary=project.research_topic, request=request)
        response = _with_favorite_state(project, response)
        state.update(response.model_dump(mode="json"))
        state["owner_id"] = user_id
        state["project_id"] = project_id
        await save_execution_state(execution_id, state)
        return response
    except DiscoveryProviderFailure as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "DISCOVERY_PROVIDER_UNAVAILABLE",
                "message": "学术检索服务暂时不可用，请稍后重试。",
                "provider": exc.provider_name,
            },
        ) from exc


@router.post("/favorites", response_model=DiscoveryFavoriteResponse, status_code=201)
async def create_discovery_favorite(
    project_id: str,
    body: DiscoveryFavoriteRequest,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryFavoriteResponse:
    user_id = await get_current_user_id(authorization, db)
    project = await _owned_project(db, project_id, user_id)
    try:
        return await save_favorite(db, project, body)
    except FavoriteSourceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/favorites/{favorite_id}")
async def delete_discovery_favorite(
    project_id: str,
    favorite_id: str,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user_id = await get_current_user_id(authorization, db)
    project = await _owned_project(db, project_id, user_id)
    removed = await remove_favorite(db, project, favorite_id)
    if not removed:
        raise HTTPException(status_code=404, detail="收藏不存在或无访问权限")
    return {"favorite_id": favorite_id, "removed": True}


@router.get("/favorites", response_model=list[DiscoveryFavoriteResponse])
async def get_discovery_favorites(
    project_id: str,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryFavoriteResponse]:
    user_id = await get_current_user_id(authorization, db)
    project = await _owned_project(db, project_id, user_id)
    return list_favorites(project)


@router.post("/import", response_model=DiscoveryImportResponse, status_code=202)
async def import_discovery_paper(
    project_id: str,
    body: DiscoveryImportRequest,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryImportResponse:
    user_id = await get_current_user_id(authorization, db)
    await _owned_project(db, project_id, user_id)
    try:
        normalized_source_id = normalize_arxiv_id(body.source_paper_id)
        if body.approved_pdf_locator:
            approved_id = normalize_arxiv_id(body.approved_pdf_locator)
            if approved_id != normalized_source_id:
                raise ValueError("approved_pdf_locator 与 source_paper_id 不匹配")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    from app.harness.tools.literature_research import make_project_tools

    tool = next(
        item for item in make_project_tools(db, project_id, user_id)
        if item.name == "project_import_arxiv_paper"
    )
    message = str(await tool.ainvoke({
        "arxiv_id": normalized_source_id,
        "role": body.role,
        "tags": body.tags,
        "notes": body.notes,
        "reading_priority": body.reading_priority,
    }))
    status, task_id, paper_id = _parse_import_message(message)
    if status == "failed":
        raise HTTPException(
            status_code=502,
            detail={
                "code": "DISCOVERY_IMPORT_FAILED",
                "message": message.removeprefix("错误:"),
                "source": body.source,
                "source_paper_id": normalized_source_id,
            },
        )
    return DiscoveryImportResponse(
        source=body.source,
        source_paper_id=normalized_source_id,
        status=status,
        message=message,
        task_id=task_id,
        paper_id=paper_id,
    )


@router.get("/executions/{execution_id}")
async def get_discovery_execution(
    project_id: str,
    execution_id: str,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user_id = await get_current_user_id(authorization, db)
    await _owned_project(db, project_id, user_id)
    state = await load_execution_state(execution_id)
    if state is None or state.get("project_id") != project_id or state.get("owner_id") != user_id:
        raise HTTPException(status_code=404, detail="检索执行不存在或无访问权限")
    return _public_execution_state(state)
