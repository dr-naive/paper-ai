"""Durable agent execution, event, and tool-call records."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


EXECUTION_STATUSES = {"queued", "running", "waiting_user", "paused", "completed", "failed", "cancelled"}
TERMINAL_EXECUTION_STATUSES = {"completed", "failed", "cancelled"}


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    __table_args__ = (
        Index("idx_agent_executions_user_created", "user_id", "created_at"),
        Index("idx_agent_executions_project_created", "project_id", "created_at"),
        Index("idx_agent_executions_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(String(36), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=True)
    conversation_id = Column(String(36), nullable=True)
    agent_type = Column(String(80), nullable=False)
    goal = Column(Text, nullable=False)
    input_payload = Column(JSON, nullable=False, default=dict)
    result_payload = Column(JSON, nullable=True)
    status = Column(String(30), nullable=False, default="queued")
    current_stage = Column(String(100), nullable=True)
    active_skill = Column(String(120), nullable=True)
    runtime_version = Column(String(40), nullable=False, default="v2")
    max_tool_calls = Column(Integer, nullable=False, default=30)
    max_model_calls = Column(Integer, nullable=False, default=20)
    max_tokens = Column(Integer, nullable=False, default=100000)
    max_seconds = Column(Integer, nullable=False, default=1800)
    tool_call_count = Column(Integer, nullable=False, default=0)
    model_call_count = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)

    events = relationship("AgentEvent", back_populates="execution", cascade="all, delete-orphan")
    tool_calls = relationship("ToolCall", back_populates="execution", cascade="all, delete-orphan")


class AgentEvent(Base):
    __tablename__ = "agent_events"
    __table_args__ = (
        UniqueConstraint("execution_id", "seq", name="uq_agent_events_execution_seq"),
        Index("idx_agent_events_execution_created", "execution_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String(36), ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False)
    seq = Column(Integer, nullable=False)
    event_type = Column(String(80), nullable=False)
    stage = Column(String(100), nullable=True)
    title = Column(String(200), nullable=True)
    message = Column(Text, nullable=False, default="")
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    execution = relationship("AgentExecution", back_populates="events")


class ToolCall(Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        Index("idx_tool_calls_execution_step", "execution_id", "step_index"),
        UniqueConstraint("execution_id", "idempotency_key", name="uq_tool_calls_execution_idempotency"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String(36), ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False)
    step_index = Column(Integer, nullable=False)
    tool_name = Column(String(160), nullable=False)
    tool_version = Column(String(40), nullable=False, default="v1")
    arguments = Column(JSON, nullable=False, default=dict)
    result_summary = Column(Text, nullable=True)
    result_payload = Column(JSON, nullable=True)
    side_effect_level = Column(String(30), nullable=False, default="none")
    status = Column(String(30), nullable=False, default="started")
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    idempotency_key = Column(String(160), nullable=True)

    execution = relationship("AgentExecution", back_populates="tool_calls")
