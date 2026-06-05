"""论文相关模型"""
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON, Boolean, TypeDecorator, Index
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type."""
    impl = String
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value) if isinstance(value, uuid.UUID) else value
    
    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return uuid.UUID(value)


class Paper(Base):
    __tablename__ = "papers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    authors = Column(Text)
    abstract = Column(Text)
    full_text = Column(Text)
    pdf_path = Column(String(500))
    source_url = Column(String(500))
    doi = Column(String(100))
    keywords = Column(JSON, default=list)
    research_area = Column(String(100))
    publication_year = Column(Integer)
    venue = Column(String(200))
    citation_count = Column(Integer, default=0)
    reading_status = Column(String(20), default='unread')
    reading_progress = Column(Float, default=0)
    is_favorite = Column(Boolean, default=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_papers_user', user_id),
        Index('idx_papers_research_area', research_area),
    )
    
    user = relationship("User", back_populates="papers", primaryjoin="Paper.user_id == User.id")
    sections = relationship("Section", back_populates="paper", cascade="all, delete-orphan")
    qa_pairs = relationship("QAPair", back_populates="paper", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="paper")
    chat_sessions = relationship("ChatSession", back_populates="paper", cascade="all, delete-orphan")
    summary_caches = relationship("SummaryCache", back_populates="paper", cascade="all, delete-orphan")
    interpret_caches = relationship("InterpretCache", back_populates="paper", cascade="all, delete-orphan")


class Section(Base):
    __tablename__ = "sections"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id = Column(String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    section_title = Column(String(200), nullable=False)
    order_index = Column(Integer, nullable=False)
    start_page = Column(Integer)
    content = Column(Text)
    summary = Column(Text)
    tables = Column(JSON, default=list)
    figures = Column(JSON, default=list)
    formulas = Column(JSON, default=list)
    key_points = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_sections_paper', paper_id),
    )
    
    paper = relationship("Paper", back_populates="sections")


class QAPair(Base):
    __tablename__ = "qa_pairs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id = Column(String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    chunk_context = Column(Text)
    relevance_score = Column(Float)
    is_bookmarked = Column(Boolean, default=False)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_qa_pairs_paper', paper_id),
    )
    
    paper = relationship("Paper", back_populates="qa_pairs")


class Note(Base):
    __tablename__ = "notes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paper_id = Column(String(36), ForeignKey("papers.id", ondelete="SET NULL"))
    folder_id = Column(String(36), ForeignKey("folders.id", ondelete="SET NULL"))
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    note_type = Column(String(50))
    tags = Column(JSON, default=list)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_notes_user', user_id),
        Index('idx_notes_paper', paper_id),
    )
    
    user = relationship("User", back_populates="notes")
    paper = relationship("Paper", back_populates="notes")
    folder = relationship("Folder", back_populates="notes")


class Folder(Base):
    __tablename__ = "folders"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(String(36), ForeignKey("folders.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    color = Column(String(20))
    icon = Column(String(50))
    order_index = Column(Integer, default=0)
    paper_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_folders_user', user_id),
    )
    
    user = relationship("User", back_populates="folders")
    children = relationship("Folder", back_populates="parent")
    parent = relationship("Folder", remote_side=[id], back_populates="children")
    notes = relationship("Note", back_populates="folder")
