"""管理员评测运行记录。

评测运行不是 AgentExecution，也不是 WorkerJob：它只记录一次管理员发起的
评测及其报告引用，实际执行仍复用既有 Redis Queue/Worker 和评测脚本。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, text

from app.database import Base


EVALUATION_TYPES = {"runtime", "retrieval", "e2e"}
EVALUATION_STATUSES = {"queued", "running", "retrying", "completed", "failed", "cancelled"}
ACTIVE_EVALUATION_STATUSES = {"queued", "running", "retrying"}
TERMINAL_EVALUATION_STATUSES = {"completed", "failed", "cancelled"}


class EvaluationRun(Base):
    """一轮管理员评测的持久化生命周期。"""

    __tablename__ = "evaluation_runs"
    __table_args__ = (
        Index("idx_evaluation_runs_created", "created_at"),
        Index("idx_evaluation_runs_status", "status"),
        Index("idx_evaluation_runs_type_created", "evaluation_type", "created_at"),
        Index(
            "uq_evaluation_runs_active_type",
            "evaluation_type",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'retrying')"),
            sqlite_where=text("status IN ('queued', 'running', 'retrying')"),
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    requested_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    evaluation_type = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, default="queued")
    config = Column(JSON, nullable=False, default=dict)
    summary = Column(JSON, nullable=True)
    report_path = Column(String(500), nullable=True)
    markdown_path = Column(String(500), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=4)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
