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
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())) # 唯一标识符
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False) # 关联用户
    title = Column(String(500), nullable=False) # 标题
    authors = Column(Text) # 作者
    abstract = Column(Text) # 摘要
    full_text = Column(Text) # 完整文本
    pdf_path = Column(String(500)) # PDF路径
    source_url = Column(String(500)) # 来源URL
    doi = Column(String(100)) # DOI
    keywords = Column(JSON, default=list) # 关键词
    research_area = Column(String(100)) # 研究领域
    publication_year = Column(Integer) # 出版年份
    venue = Column(String(200)) # 出版地点
    citation_count = Column(Integer, default=0) # 引用次数
    reading_status = Column(String(20), default='unread') # 阅读状态
    reading_progress = Column(Float, default=0) # 阅读进度
    is_favorite = Column(Boolean, default=False) # 是否收藏
    uploaded_at = Column(DateTime, default=datetime.utcnow) # 上传时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # 更新时间
    
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


class Table(Base):
    """表格数据模型"""
    __tablename__ = "tables"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id = Column(String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(String(36), ForeignKey("sections.id", ondelete="SET NULL"))
    page_number = Column(Integer)
    table_number = Column(Integer)
    caption = Column(String(500))
    markdown_content = Column(Text)
    csv_content = Column(Text)
    raw_content = Column(JSON, default=list)
    analysis_result = Column(JSON, default=dict)
    markdown_path = Column(String(500))
    csv_path = Column(String(500))
    screenshot_path = Column(String(500))
    is_corrupted = Column(Boolean, default=False)
    extraction_method = Column(String(50), default="pdfplumber")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_tables_paper', paper_id),
        Index('idx_tables_section', section_id),
    )
    
    paper = relationship("Paper")
    section = relationship("Section")


class Image(Base):
    """图片数据模型"""
    __tablename__ = "images"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id = Column(String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(String(36), ForeignKey("sections.id", ondelete="SET NULL"))
    page_number = Column(Integer)
    image_index = Column(Integer)
    file_path = Column(String(500))
    width = Column(Integer)
    height = Column(Integer)
    aspect_ratio = Column(Float)
    image_type = Column(String(50))
    chart_type = Column(String(50))
    analysis_result = Column(JSON, default=dict)
    is_filtered = Column(Boolean, default=False)
    filtered_reason = Column(String(200))
    extraction_method = Column(String(50), default="pymupdf")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_images_paper', paper_id),
        Index('idx_images_section', section_id),
        Index('idx_images_type', image_type),
    )
    
    paper = relationship("Paper")
    section = relationship("Section")
