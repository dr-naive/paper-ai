"""Revisioned formal writing documents; ProseMirror JSON is authoritative."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from app.database import Base


class WritingDocument(Base):
    __tablename__ = "writing_documents"
    __table_args__ = (Index("idx_writing_documents_project_updated", "project_id", "updated_at"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    document_type = Column(String(40), nullable=False, default="paper")
    status = Column(String(30), nullable=False, default="draft")
    current_revision_id = Column(String(36), ForeignKey("document_revisions.id", ondelete="SET NULL",
                                                         use_alter=True, name="fk_writing_documents_current_revision"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentRevision(Base):
    __tablename__ = "document_revisions"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_revisions_document_version"),
        Index("idx_document_revisions_document_created", "document_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("writing_documents.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    content_json = Column(JSON, nullable=False)
    created_by = Column(String(30), nullable=False, default="user")
    source_execution_id = Column(String(36), ForeignKey("agent_executions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
