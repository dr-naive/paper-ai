"""用户模型"""
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Index
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base


class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    research_field = Column(String(100))
    institution = Column(String(200))
    avatar_url = Column(String(500))
    preferences = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    # Simple RBAC. New registrations always use "user"; only an administrator
    # may grant the "admin" role.
    role = Column(String(20), nullable=False, default="user", server_default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_users_email', email),
    )
    
    papers = relationship("Paper", back_populates="user", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="user", cascade="all, delete-orphan")
    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    summary_caches = relationship("SummaryCache", back_populates="user", cascade="all, delete-orphan")
    interpret_caches = relationship("InterpretCache", back_populates="user", cascade="all, delete-orphan")
    research_projects = relationship(
        "ResearchProject", back_populates="user", cascade="all, delete-orphan"
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "research_field": self.research_field,
            "institution": self.institution,
            "avatar_url": self.avatar_url,
            "preferences": self.preferences,
            "is_active": self.is_active,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
