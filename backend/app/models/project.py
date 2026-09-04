"""研究项目、项目文档库关联、写作产物等模型。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------- phase / status 常量 ----------
PROJECT_PHASE_RESEARCH = "research"       # 选题调研
PROJECT_PHASE_READING = "reading"         # 深度阅读
PROJECT_PHASE_WRITING = "writing"         # 写作
PROJECT_PHASE_REFINEMENT = "refinement"   # 润色/评审/投稿
PROJECT_PHASE_ARCHIVED = "archived"       # 归档

PROJECT_STATUS_ACTIVE = "active"
PROJECT_STATUS_PAUSED = "paused"
PROJECT_STATUS_COMPLETED = "completed"

PAPER_ROLE_CORE = "core"              # 核心文献
PAPER_ROLE_RELATED = "related"        # 相关工作
PAPER_ROLE_BACKGROUND = "background"  # 背景知识

ARTIFACT_TYPE_OUTLINE = "outline"
ARTIFACT_TYPE_LITERATURE_REVIEW = "literature_review"
ARTIFACT_TYPE_REFERENCE_LIST = "reference_list"
ARTIFACT_TYPE_SECTION_DRAFT = "section_draft"
ARTIFACT_TYPE_FULL_DRAFT = "full_draft"
ARTIFACT_TYPE_REVIEW_REPORT = "review_report"
ARTIFACT_TYPE_SUBMISSION_SUGGESTION = "submission_suggestion"
ARTIFACT_TYPE_RESEARCH_MAP = "research_map"
ARTIFACT_TYPE_READING_PLAN = "reading_plan"
ARTIFACT_TYPE_EVIDENCE_MATRIX = "evidence_matrix"
ARTIFACT_TYPE_EXPERIMENT_DESIGN = "experiment_design"
ARTIFACT_TYPE_PAPER_BLUEPRINT = "paper_blueprint"
ARTIFACT_TYPE_FINAL_MANUSCRIPT = "final_manuscript"

ARTIFACT_STATUS_DRAFT = "draft"
ARTIFACT_STATUS_IN_PROGRESS = "in_progress"
ARTIFACT_STATUS_READY = "ready"


class ResearchProject(Base):
    """研究项目:一个写作主题下的所有上下文(文档库、记忆、写作产物)。"""

    __tablename__ = "research_projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title = Column(String(300), nullable=False, index=True)
    research_topic = Column(String(300), nullable=False)
    abstract = Column(Text, default="")

    # research -> reading -> writing -> refinement -> archived
    phase = Column(String(30), nullable=False, default=PROJECT_PHASE_RESEARCH)
    status = Column(String(30), nullable=False, default=PROJECT_STATUS_ACTIVE)

    # 长期记忆:summary + notes[] 分层结构,便于 prompt 截断
    # {"summary": str, "notes": [{"time": iso, "text": str, "tag": str?}]}
    memory = Column(JSON, default=lambda: {"summary": "", "notes": []})

    # 项目级偏好:如目标期刊、写作风格(中文/英文)、引用格式等
    preferences = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="research_projects")
    project_papers = relationship(
        "ProjectPaper",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    writing_artifacts = relationship(
        "WritingArtifact",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    chat_sessions = relationship(
        "ChatSession",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "research_topic": self.research_topic,
            "abstract": self.abstract,
            "phase": self.phase,
            "status": self.status,
            "memory": self.memory or {"summary": "", "notes": []},
            "preferences": self.preferences or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProjectPaper(Base):
    """项目-论文关联表:一篇论文可属多个项目,一个项目包含多篇论文。"""

    __tablename__ = "project_papers"
    __table_args__ = (
        UniqueConstraint("project_id", "paper_id", name="uq_project_paper"),
        Index("idx_project_papers_project", "project_id"),
        Index("idx_project_papers_paper", "paper_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(
        String(36), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    paper_id = Column(
        String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )

    # 论文在项目中的角色:核心/相关工作/背景
    role = Column(String(30), nullable=False, default=PAPER_ROLE_RELATED)
    # 用户自定义标签
    tags = Column(JSON, default=list)
    # 用户对这篇论文在本项目中的备注
    notes = Column(Text, default="")
    # 项目语境下的结构化论文卡片，而不是论文的全局属性。
    analysis_card = Column(JSON, default=dict)
    # 项目语境下的阅读任务:{order,status,reason,focus[],questions[],updated_at}
    reading_plan = Column(JSON, default=dict)
    # 1-5 档,越高越先看
    reading_priority = Column(Integer, default=3)

    added_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("ResearchProject", back_populates="project_papers")
    paper = relationship("Paper", back_populates="project_papers")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "paper_id": self.paper_id,
            "role": self.role,
            "tags": self.tags or [],
            "notes": self.notes or "",
            "analysis_card": self.analysis_card or {},
            "reading_plan": self.reading_plan or {},
            "reading_priority": self.reading_priority,
            "added_at": self.added_at.isoformat() if self.added_at else None,
        }


class WritingArtifact(Base):
    """写作产物:大纲/文献综述/章节草稿/参考文献列表/评审报告/投稿建议 等。

    单一多态表,artifact_type 区分类型。内容提供三档:
    - content(JSON):结构化数据,供 UI 分段渲染(如大纲树)
    - markdown_text(Text):人类可读的 Markdown 全文,可直接导出 .md
    - html_text(Text):可选,渲染后的 HTML 供预览/下载 PDF 时用
    """

    __tablename__ = "writing_artifacts"
    __table_args__ = (
        Index("idx_writing_artifacts_project_type", "project_id", "artifact_type"),
        Index("idx_writing_artifacts_updated_at", "updated_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(
        String(36), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    author_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    artifact_type = Column(String(40), nullable=False, index=True)
    title = Column(String(400), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    # 可选父产物 id,用于章节草稿隶属于一份大纲、最终全文由多段草稿合成等场景
    parent_id = Column(
        String(36), ForeignKey("writing_artifacts.id", ondelete="SET NULL"), nullable=True
    )

    # 三档内容存储
    content = Column(JSON, default=dict)
    markdown_text = Column(Text, default="")
    html_text = Column(Text, default="")

    status = Column(String(30), nullable=False, default=ARTIFACT_STATUS_DRAFT)

    # 元数据:如 section_name / target_venue / generated_by(agent/manual) / citations[]
    meta = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("ResearchProject", back_populates="writing_artifacts")
    author = relationship("User")

    # 自引用父产物不建立反向关系(避免循环加载复杂性)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "author_id": self.author_id,
            "artifact_type": self.artifact_type,
            "title": self.title,
            "version": self.version,
            "parent_id": self.parent_id,
            "content": self.content or {},
            "markdown_text": self.markdown_text or "",
            "html_text": self.html_text or "",
            "status": self.status,
            "meta": self.meta or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
