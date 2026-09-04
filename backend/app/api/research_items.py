"""Project-scoped Research Notes and Evidence APIs."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_id
from app.database import get_db
from app.config import settings
from app.models.paper import Paper
from app.models.project import ProjectPaper, ResearchProject
from app.models.research import EvidenceItem, MemoryItem
from app.research.context.schemas import DISCOVERY_MEMORY_TYPES
from app.research.evidence.service import EvidenceProvenanceError, EvidenceService

def require_memory_v2() -> None:
    if not settings.ENABLE_MEMORY_V2: raise HTTPException(status_code=404, detail="Research Notes V2 未启用")

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["research-notes-evidence"], dependencies=[Depends(require_memory_v2)])
evidence_router = APIRouter(prefix="/api/v1/evidence", tags=["research-notes-evidence"], dependencies=[Depends(require_memory_v2)])
MEMORY_TYPES = {
    "finding", "question", "hypothesis", "decision", "definition", "constraint", "preference", "summary",
    *DISCOVERY_MEMORY_TYPES,
}
EVIDENCE_TYPES = {"quote", "result", "method", "definition", "limitation", "comparison", "background"}


class NoteCreate(BaseModel):
    type: str = "finding"
    title: str = Field(default="", max_length=300)
    content: str = Field(min_length=1, max_length=20000)
    source_type: str | None = Field(default=None, max_length=40)
    source_id: str | None = Field(default=None, max_length=100)
    confidence: float = Field(default=1.0, ge=0, le=1)
    tags: list[str] = Field(default_factory=list, max_length=30)

class NoteUpdate(BaseModel):
    type: str | None = None
    title: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None, min_length=1, max_length=20000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    tags: list[str] | None = Field(default=None, max_length=30)

class EvidenceCreate(BaseModel):
    paper_id: str
    section_id: str | None = None
    element_id: str | None = None
    chunk_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    bbox: dict[str, Any] | list[Any] | None = None
    evidence_type: str = "quote"
    snippet: str = Field(min_length=1, max_length=20000)
    normalized_claim: str = Field(default="", max_length=10000)


async def auth_project(project_id: str, authorization: str | None, db: AsyncSession) -> tuple[str, ResearchProject]:
    user_id = await get_current_user_id(authorization, db)
    project = (await db.execute(select(ResearchProject).where(ResearchProject.id == project_id,
                                                               ResearchProject.user_id == user_id))).scalar_one_or_none()
    if project is None: raise HTTPException(status_code=404, detail="项目不存在")
    return user_id, project

def note_dict(item: MemoryItem, *, legacy: bool = False) -> dict[str, Any]:
    return {"id": item.id, "project_id": item.project_id, "type": item.type, "title": item.title,
            "content": item.content, "source_type": item.source_type, "source_id": item.source_id,
            "confidence": item.confidence, "tags": item.tags or [], "created_by": item.created_by,
            "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(), "legacy": legacy}

def evidence_dict(item: EvidenceItem) -> dict[str, Any]:
    return {column.name: (value.isoformat() if isinstance(value, datetime) else value)
            for column in item.__table__.columns for value in [getattr(item, column.name)]}

def source_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]

@evidence_router.get("/{evidence_id}")
async def get_evidence(evidence_id: str, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    user_id = await get_current_user_id(authorization, db)
    item = (await db.execute(select(EvidenceItem)
                             .join(ResearchProject, ResearchProject.id == EvidenceItem.project_id)
                             .join(ProjectPaper, (ProjectPaper.project_id == EvidenceItem.project_id) &
                                   (ProjectPaper.paper_id == EvidenceItem.paper_id))
                             .where(EvidenceItem.id == evidence_id,
                                    ResearchProject.user_id == user_id))).scalar_one_or_none()
    if item is None: raise HTTPException(status_code=404, detail="研究证据不存在")
    return evidence_dict(item)


@router.get("/notes")
async def list_notes(project_id: str, include_legacy: bool = True, db: AsyncSession = Depends(get_db),
                     authorization: str | None = Header(None)):
    _, project = await auth_project(project_id, authorization, db)
    rows = (await db.execute(select(MemoryItem).where(MemoryItem.project_id == project_id,
                                                      MemoryItem.superseded_by.is_(None))
                             .order_by(MemoryItem.updated_at.desc()))).scalars().all()
    items = [note_dict(row) for row in rows]
    if include_legacy:
        for index, raw in enumerate((project.memory or {}).get("notes", [])):
            items.append({"id": f"legacy-{index}", "project_id": project_id, "type": raw.get("tag") or "finding",
                          "title": "", "content": raw.get("text", ""), "source_type": raw.get("source_type"),
                          "source_id": raw.get("paper_id"), "confidence": 1.0, "tags": [raw["tag"]] if raw.get("tag") else [],
                          "created_by": "legacy", "created_at": raw.get("time"), "updated_at": raw.get("time"), "legacy": True})
    return {"items": items}

@router.post("/notes", status_code=201)
async def create_note(project_id: str, body: NoteCreate, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    user_id, _ = await auth_project(project_id, authorization, db)
    if body.type not in MEMORY_TYPES: raise HTTPException(status_code=422, detail="无效的研究笔记类型")
    item = MemoryItem(project_id=project_id, user_id=user_id, created_by="user", **body.model_dump())
    db.add(item); await db.commit(); await db.refresh(item)
    return note_dict(item)

@router.patch("/notes/{note_id}")
async def update_note(project_id: str, note_id: str, body: NoteUpdate, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    user_id, _ = await auth_project(project_id, authorization, db)
    item = (await db.execute(select(MemoryItem).where(MemoryItem.id == note_id, MemoryItem.project_id == project_id,
                                                       MemoryItem.user_id == user_id))).scalar_one_or_none()
    if item is None: raise HTTPException(status_code=404, detail="研究笔记不存在")
    values = body.model_dump(exclude_unset=True)
    if values.get("type") and values["type"] not in MEMORY_TYPES: raise HTTPException(status_code=422, detail="无效类型")
    for key, value in values.items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item); return note_dict(item)

@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(project_id: str, note_id: str, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    user_id, _ = await auth_project(project_id, authorization, db)
    item = (await db.execute(select(MemoryItem).where(MemoryItem.id == note_id, MemoryItem.project_id == project_id,
                                                       MemoryItem.user_id == user_id))).scalar_one_or_none()
    if item is None: raise HTTPException(status_code=404, detail="研究笔记不存在")
    await db.delete(item); await db.commit()

@router.get("/evidence")
async def list_evidence(project_id: str, paper_id: str | None = Query(None), db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    await auth_project(project_id, authorization, db)
    query = (select(EvidenceItem)
             .join(ProjectPaper, (ProjectPaper.project_id == EvidenceItem.project_id) &
                   (ProjectPaper.paper_id == EvidenceItem.paper_id))
             .where(EvidenceItem.project_id == project_id))
    if paper_id: query = query.where(EvidenceItem.paper_id == paper_id)
    rows = (await db.execute(query.order_by(EvidenceItem.created_at.desc()))).scalars().all()
    return {"items": [evidence_dict(row) for row in rows]}

@router.post("/evidence", status_code=201)
async def create_evidence(project_id: str, body: EvidenceCreate, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    user_id, _ = await auth_project(project_id, authorization, db)
    if body.evidence_type not in EVIDENCE_TYPES: raise HTTPException(status_code=422, detail="无效的证据类型")
    paper = (await db.execute(select(Paper).join(ProjectPaper, ProjectPaper.paper_id == Paper.id)
                              .where(Paper.id == body.paper_id, Paper.user_id == user_id,
                                     ProjectPaper.project_id == project_id))).scalar_one_or_none()
    if paper is None: raise HTTPException(status_code=404, detail="论文不在当前项目文档库")
    try:
        evidence_service = EvidenceService(db)
        _, element = await evidence_service.validate_locator(
            paper_id=body.paper_id,
            section_id=body.section_id,
            element_id=body.element_id,
            chunk_id=body.chunk_id,
        )
    except EvidenceProvenanceError:
        raise HTTPException(status_code=422, detail="证据位置无法在当前论文中验证")
    values = body.model_dump()
    if element:
        values["page_number"] = values["page_number"] or element.page_number
        values["bbox"] = values["bbox"] or element.bbox
    fingerprint = await evidence_service.source_fingerprint(paper)
    item = EvidenceItem(project_id=project_id, created_by="user", source_title=paper.title,
                        source_authors=source_authors(paper.authors), source_year=paper.publication_year, doi=paper.doi,
                        source_type="user_saved", status="active", source_fingerprint=fingerprint,
                        verification_status="unverified",
                        **values)
    db.add(item); await db.commit(); await db.refresh(item); return evidence_dict(item)

@router.delete("/evidence/{evidence_id}", status_code=204)
async def delete_evidence(project_id: str, evidence_id: str, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    user_id, _ = await auth_project(project_id, authorization, db)
    item = (await db.execute(select(EvidenceItem).join(ResearchProject, ResearchProject.id == EvidenceItem.project_id)
                             .where(EvidenceItem.id == evidence_id, EvidenceItem.project_id == project_id,
                                    ResearchProject.user_id == user_id))).scalar_one_or_none()
    if item is None: raise HTTPException(status_code=404, detail="研究证据不存在")
    await db.delete(item); await db.commit()
