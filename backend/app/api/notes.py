"""笔记管理 API 模块"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.paper import Note
from app.models.user import User
from app.api.auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])


class NoteCreate(BaseModel):
    title: str
    content: str
    paper_id: Optional[str] = None
    folder_id: Optional[str] = None
    note_type: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = False


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    note_type: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None


class NoteResponse(BaseModel):
    id: str
    user_id: str
    paper_id: Optional[str]
    folder_id: Optional[str]
    title: str
    content: str
    note_type: Optional[str]
    tags: Optional[List[str]]
    is_public: bool
    created_at: datetime
    updated_at: datetime


@router.get("/", response_model=List[NoteResponse])
async def get_notes(
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Note).filter(Note.user_id == current_user.id)
    
    if search:
        query = query.filter(Note.title.contains(search) | Note.content.contains(search))
    
    result = await db.execute(query.offset(skip).limit(limit))
    notes = result.scalars().all()
    return [NoteResponse.from_orm(note) for note in notes]


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Note).filter(Note.id == uuid.UUID(note_id)))
    note = result.scalars().first()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return NoteResponse.from_orm(note)


@router.post("/", response_model=NoteResponse)
async def create_note(
    note_data: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_note = Note(
        id=uuid.uuid4(),
        user_id=current_user.id,
        paper_id=uuid.UUID(note_data.paper_id) if note_data.paper_id else None,
        folder_id=uuid.UUID(note_data.folder_id) if note_data.folder_id else None,
        title=note_data.title,
        content=note_data.content,
        note_type=note_data.note_type,
        tags=note_data.tags or [],
        is_public=note_data.is_public or False
    )
    
    db.add(new_note)
    await db.commit()
    await db.refresh(new_note)
    return NoteResponse.from_orm(new_note)


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    note_data: NoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Note).filter(Note.id == uuid.UUID(note_id)))
    note = result.scalars().first()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if note_data.title is not None:
        note.title = note_data.title
    if note_data.content is not None:
        note.content = note_data.content
    if note_data.note_type is not None:
        note.note_type = note_data.note_type
    if note_data.tags is not None:
        note.tags = note_data.tags
    if note_data.is_public is not None:
        note.is_public = note_data.is_public
    
    await db.commit()
    await db.refresh(note)
    return NoteResponse.from_orm(note)


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Note).filter(Note.id == uuid.UUID(note_id)))
    note = result.scalars().first()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.delete(note)
    await db.commit()
    return {"message": "Note deleted successfully"}