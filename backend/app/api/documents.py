"""Revisioned formal-writing API. Revisions are append-only."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_id
from app.application.writing_service import generate_edit_proposal
from app.database import get_db
from app.config import settings
from app.models.document import DocumentRevision, WritingDocument
from app.models.project import ResearchProject
from app.models.research import EvidenceItem

def require_writing_v2() -> None:
    if not settings.ENABLE_WRITING_V2: raise HTTPException(status_code=404, detail="Writing V2 未启用")

router = APIRouter(prefix="/api/v1", tags=["writing-documents"], dependencies=[Depends(require_writing_v2)])


def empty_document() -> dict[str, Any]:
    return {"type": "doc", "content": [{"type": "paragraph", "content": []}]}

class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    document_type: str = Field(default="paper", max_length=40)
    content_json: dict[str, Any] = Field(default_factory=empty_document)

class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    status: str | None = Field(default=None, pattern="^(draft|review|ready|archived)$")

class RevisionCreate(BaseModel):
    content_json: dict[str, Any]
    created_by: str = Field(default="user", pattern="^(user|agent|import)$")
    source_execution_id: str | None = None

    @model_validator(mode="after")
    def validate_prosemirror(self):
        if self.content_json.get("type") != "doc" or not isinstance(self.content_json.get("content", []), list):
            raise ValueError("content_json 必须是 ProseMirror doc JSON")
        return self

class AIActionRequest(BaseModel):
    action: str = Field(pattern="^(improve_style|make_concise|clarify_argument|find_evidence|check_claim)$")
    selected_text: str = Field(min_length=1, max_length=20000)
    from_pos: int = Field(ge=0)
    to_pos: int = Field(ge=0)


async def user_id(authorization: str | None, db: AsyncSession) -> str:
    return await get_current_user_id(authorization, db)

async def owned_document(document_id: str, uid: str, db: AsyncSession) -> WritingDocument:
    item = (await db.execute(select(WritingDocument).join(ResearchProject, ResearchProject.id == WritingDocument.project_id)
                             .where(WritingDocument.id == document_id, ResearchProject.user_id == uid))).scalar_one_or_none()
    if item is None: raise HTTPException(status_code=404, detail="写作文档不存在")
    return item

def revision_dict(item: DocumentRevision) -> dict[str, Any]:
    return {"id": item.id, "document_id": item.document_id, "version": item.version,
            "content_json": item.content_json, "created_by": item.created_by,
            "source_execution_id": item.source_execution_id, "created_at": item.created_at.isoformat()}

def citation_nodes(content: Any) -> list[dict[str, Any]]:
    """Collect citation nodes from a ProseMirror tree without trusting its shape."""
    found: list[dict[str, Any]] = []
    if isinstance(content, dict):
        if content.get("type") == "citation":
            found.append(content.get("attrs") if isinstance(content.get("attrs"), dict) else {})
        for child in content.get("content", []):
            found.extend(citation_nodes(child))
    elif isinstance(content, list):
        for child in content:
            found.extend(citation_nodes(child))
    return found

def claim_blocks(content: Any) -> list[dict[str, Any]]:
    """Return substantive ProseMirror paragraphs and their attached citations."""
    blocks: list[dict[str, Any]] = []
    if not isinstance(content, dict):
        return blocks
    for node in content.get("content", []):
        if not isinstance(node, dict) or node.get("type") != "paragraph":
            continue
        children = node.get("content", [])
        text = "".join(str(child.get("text", "")) for child in children if isinstance(child, dict)).strip()
        citations = [child.get("attrs", {}) for child in children
                     if isinstance(child, dict) and child.get("type") == "citation"]
        word_count = len(re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?", text))
        han_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        if text and (word_count >= 8 or han_count >= 15):
            blocks.append({"text": text, "citations": citations})
    return blocks

def evidence_supports_claim(claim: str, evidence: EvidenceItem) -> bool:
    """Conservative lexical gate; passing means only 'plausibly supported', never proven."""
    source = f"{evidence.normalized_claim or ''} {evidence.snippet or ''}".lower()
    claim_words = {word for word in re.findall(r"[a-z0-9]+", claim.lower())
                   if len(word) > 3 and word not in {"have", "with", "from", "that", "this", "were", "been"}}
    source_words = set(re.findall(r"[a-z0-9]+", source))
    latin_supported = len(claim_words & source_words) >= min(2, max(1, len(claim_words)))
    claim_han = set(re.findall(r"[\u4e00-\u9fff]", claim))
    source_han = set(re.findall(r"[\u4e00-\u9fff]", source))
    han_supported = len(claim_han & source_han) >= min(4, max(1, len(claim_han)))
    return latin_supported or han_supported

async def document_dict(item: WritingDocument, db: AsyncSession, include_content: bool = False) -> dict[str, Any]:
    result = {"id": item.id, "project_id": item.project_id, "title": item.title,
              "document_type": item.document_type, "status": item.status,
              "current_revision_id": item.current_revision_id, "created_at": item.created_at.isoformat(),
              "updated_at": item.updated_at.isoformat()}
    if include_content and item.current_revision_id:
        revision = await db.get(DocumentRevision, item.current_revision_id)
        result["current_revision"] = revision_dict(revision) if revision else None
    return result

@router.get("/projects/{project_id}/documents")
async def list_documents(project_id: str, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    uid = await user_id(authorization, db)
    project = await db.get(ResearchProject, project_id)
    if project is None or project.user_id != uid: raise HTTPException(status_code=404, detail="项目不存在")
    rows = (await db.execute(select(WritingDocument).where(WritingDocument.project_id == project_id)
                             .order_by(WritingDocument.updated_at.desc()))).scalars().all()
    return {"items": [await document_dict(row, db) for row in rows]}

@router.post("/projects/{project_id}/documents", status_code=201)
async def create_document(project_id: str, body: DocumentCreate, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    uid = await user_id(authorization, db)
    project = await db.get(ResearchProject, project_id)
    if project is None or project.user_id != uid: raise HTTPException(status_code=404, detail="项目不存在")
    validated = RevisionCreate(content_json=body.content_json)
    item = WritingDocument(project_id=project_id, title=body.title, document_type=body.document_type)
    db.add(item); await db.flush()
    revision = DocumentRevision(document_id=item.id, version=1, content_json=validated.content_json, created_by="user")
    db.add(revision); await db.flush(); item.current_revision_id = revision.id
    await db.commit(); await db.refresh(item)
    return await document_dict(item, db, True)

@router.get("/documents/{document_id}")
async def get_document(document_id: str, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    uid = await user_id(authorization, db); return await document_dict(await owned_document(document_id, uid, db), db, True)

@router.patch("/documents/{document_id}")
async def update_document(document_id: str, body: DocumentUpdate, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    uid = await user_id(authorization, db); document = await owned_document(document_id, uid, db)
    for key, value in body.model_dump(exclude_unset=True).items(): setattr(document, key, value)
    document.updated_at = datetime.utcnow(); await db.commit(); await db.refresh(document)
    return await document_dict(document, db, True)

@router.get("/documents/{document_id}/revisions")
async def list_revisions(document_id: str, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    uid = await user_id(authorization, db); await owned_document(document_id, uid, db)
    rows = (await db.execute(select(DocumentRevision).where(DocumentRevision.document_id == document_id)
                             .order_by(DocumentRevision.version.desc()))).scalars().all()
    return {"items": [revision_dict(row) for row in rows]}

@router.post("/documents/{document_id}/revisions", status_code=201)
async def create_revision(document_id: str, body: RevisionCreate, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    uid = await user_id(authorization, db); document = await owned_document(document_id, uid, db)
    version = int(await db.scalar(select(func.max(DocumentRevision.version)).where(DocumentRevision.document_id == document_id)) or 0) + 1
    revision = DocumentRevision(document_id=document_id, version=version, **body.model_dump())
    db.add(revision); await db.flush(); document.current_revision_id = revision.id; document.updated_at = datetime.utcnow()
    await db.commit(); await db.refresh(revision); return revision_dict(revision)

@router.post("/documents/{document_id}/ai-actions")
async def propose_ai_action(document_id: str, body: AIActionRequest, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    uid = await user_id(authorization, db); document = await owned_document(document_id, uid, db)
    # Proposal only: accepting it must create a new revision. Never overwrite current content.
    try:
        replacement = await generate_edit_proposal(body.action, body.selected_text)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="AI 编辑服务暂时不可用，原文未发生变化。") from exc
    return {"document_id": document.id, "base_revision_id": document.current_revision_id,
            "action": body.action, "range": {"from": body.from_pos, "to": body.to_pos},
            "original": body.selected_text, "replacement": replacement,
            "status": "proposal", "message": "AI 编辑建议已建立；需显式接受后创建新 revision。"}

@router.post("/documents/{document_id}/citation-audit")
async def audit_document_citations(document_id: str, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)):
    uid = await user_id(authorization, db); document = await owned_document(document_id, uid, db)
    revision = await db.get(DocumentRevision, document.current_revision_id) if document.current_revision_id else None
    citations = citation_nodes(revision.content_json if revision else {})
    evidence_ids = {attrs.get("evidence_id") for attrs in citations if attrs.get("evidence_id")}
    evidence_rows = []
    if evidence_ids:
        evidence_rows = (await db.execute(select(EvidenceItem).where(EvidenceItem.id.in_(evidence_ids),
                                                                     EvidenceItem.project_id == document.project_id))).scalars().all()
    valid_evidence = {item.id: item for item in evidence_rows}
    issues: list[dict[str, Any]] = []
    for index, attrs in enumerate(citations):
        evidence_id, paper_id = attrs.get("evidence_id"), attrs.get("paper_id")
        if not paper_id: issues.append({"citation_index": index, "severity": "error", "code": "missing_paper", "message": "引用缺少论文标识。"})
        if not evidence_id: issues.append({"citation_index": index, "severity": "warning", "code": "missing_evidence", "message": "引用尚未绑定研究证据。"})
        elif evidence_id not in valid_evidence: issues.append({"citation_index": index, "severity": "error", "code": "invalid_evidence", "message": "引用的证据不存在或不属于当前项目。"})
        elif paper_id and valid_evidence[evidence_id].paper_id != paper_id: issues.append({"citation_index": index, "severity": "error", "code": "paper_mismatch", "message": "引用论文与证据来源不一致。"})
    for block in claim_blocks(revision.content_json if revision else {}):
        linked = [valid_evidence[attrs.get("evidence_id")] for attrs in block["citations"]
                  if attrs.get("evidence_id") in valid_evidence]
        if not linked or not any(evidence_supports_claim(block["text"], item) for item in linked):
            issues.append({"citation_index": -1, "severity": "error", "code": "unsupported_claim",
                           "message": "Unsupported claim：该主张缺少可匹配的研究证据。",
                           "claim_excerpt": block["text"][:240]})
    return {"document_id": document.id, "revision_id": revision.id if revision else None,
            "citation_count": len(citations), "linked_evidence_count": sum(1 for attrs in citations if attrs.get("evidence_id") in valid_evidence),
            "issue_count": len(issues), "issues": issues,
            "passed": not any(issue["severity"] == "error" for issue in issues)}
