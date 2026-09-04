"""Structured project research notes and source evidence."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text

from app.database import Base


class MemoryItem(Base):
    __tablename__ = "memory_items"
    __table_args__ = (Index("idx_memory_items_project_updated", "project_id", "updated_at"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(30), nullable=False)
    title = Column(String(300), nullable=False, default="")
    content = Column(Text, nullable=False)
    source_type = Column(String(40), nullable=True)
    source_id = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=False, default=1.0)
    tags = Column(JSON, nullable=False, default=list)
    created_by = Column(String(30), nullable=False, default="user")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    superseded_by = Column(String(36), ForeignKey("memory_items.id", ondelete="SET NULL"), nullable=True)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        Index("idx_evidence_items_project_created", "project_id", "created_at"),
        Index("idx_evidence_items_paper", "paper_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    paper_id = Column(String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(String(36), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)
    element_id = Column(String(100), nullable=True)
    chunk_id = Column(String(100), nullable=True)
    page_number = Column(Integer, nullable=True)
    bbox = Column(JSON, nullable=True)
    evidence_type = Column(String(30), nullable=False)
    snippet = Column(Text, nullable=False)
    normalized_claim = Column(Text, nullable=False, default="")
    source_title = Column(String(500), nullable=False)
    source_authors = Column(JSON, nullable=False, default=list)
    source_year = Column(Integer, nullable=True)
    doi = Column(String(200), nullable=True)
    created_by = Column(String(30), nullable=False, default="user")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
