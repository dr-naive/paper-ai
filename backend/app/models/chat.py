"""对话历史和缓存相关模型"""
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON, Index, Boolean
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base


class ChatSession(Base):
    """对话会话 - 每个会话包含一组问答对话"""
    __tablename__ = "chat_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paper_id = Column(String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=True)
    project_id = Column(
        String(36), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=True
    )
    title = Column(String(200), default="新对话")  # 会话标题，默认取第一个问题
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_chat_sessions_user', user_id),
        Index('idx_chat_sessions_paper', paper_id),
        Index('idx_chat_sessions_project', project_id),
    )
    
    user = relationship("User", back_populates="chat_sessions")
    paper = relationship("Paper", back_populates="chat_sessions")
    project = relationship("ResearchProject", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.order_index")


class ChatMessage(Base):
    """对话消息 - 单轮问答"""
    __tablename__ = "chat_messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False)  # 消息在会话中的顺序
    question = Column(Text, nullable=False)
    answer = Column(Text)
    citations = Column(JSON, default=list)  # 引用来源
    follow_up_questions = Column(JSON, default=list)  # 推荐追问
    # 新消息存储 evidence_confidence；历史消息可能仍是旧版 intent confidence。
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_chat_messages_session', session_id),
    )
    
    session = relationship("ChatSession", back_populates="messages")


class SummaryCache(Base):
    """结构化摘要缓存"""
    __tablename__ = "summary_cache"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paper_id = Column(String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True)
    overview = Column(JSON)  # 概览
    methodology = Column(JSON)  # 方法论
    experiments = Column(JSON)  # 实验
    contributions = Column(JSON)  # 贡献
    generated_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_summary_cache_user', user_id),
        Index('idx_summary_cache_paper', paper_id),
    )
    
    user = relationship("User", back_populates="summary_caches")
    paper = relationship("Paper", back_populates="summary_caches")


class InterpretCache(Base):
    """深度解读缓存"""
    __tablename__ = "interpret_cache"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paper_id = Column(String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    interpret_type = Column(String(20), nullable=False)  # concept, compare, key_info
    data = Column(JSON)  # 解读结果
    generated_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_interpret_cache_user', user_id),
        Index('idx_interpret_cache_paper_type', paper_id, interpret_type, unique=True),
    )
    
    user = relationship("User", back_populates="interpret_caches")
    paper = relationship("Paper", back_populates="interpret_caches")


class AnswerTrace(Base):
    """Persistent aggregate-friendly metrics for completed answer jobs."""
    __tablename__ = "answer_traces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id = Column(String(100), unique=True, nullable=False, index=True)
    task_id = Column(String(100), nullable=False)
    user_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(36), nullable=False)
    status = Column(String(20), nullable=False)
    thinking_tokens = Column(Integer, default=0)
    answer_tokens = Column(Integer, default=0)
    total_ms = Column(Float)
    first_token_ms = Column(Float)
    retrieval_ms = Column(Float)
    citation_count = Column(Integer, default=0)
    model_calls = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    used_second_pass = Column(Boolean, default=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_answer_traces_recorded_at", recorded_at),
        Index("idx_answer_traces_status", status),
    )
