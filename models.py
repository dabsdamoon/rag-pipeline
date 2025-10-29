from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, LargeBinary, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum
import uuid

Base = declarative_base()

class ProcessingStatus(PyEnum):
    PROCESSING = "processing"
    COMPLETED = "completed" 
    FAILED = "failed"

class Sources(Base):
    __tablename__ = "sources"
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    author = Column(String)
    description = Column(Text)
    page_count = Column(Integer)
    file_size = Column(Integer)
    content_type = Column(String)
    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PROCESSING)
    upload_date = Column(DateTime, default=func.now())
    file_path = Column(String)
    
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=func.now())
    last_activity = Column(DateTime, default=func.now())

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    sources_used = Column(Text)  # JSON string of sources
    tokens_used = Column(Text)  # JSON string of token usage
    timestamp = Column(DateTime, default=func.now())

class SourceMetadata(Base):
    __tablename__ = "source_metadata"

    source_id = Column(String, primary_key=True)  # e.g., "BOOK001"
    name = Column(String, nullable=False)       # e.g., "childbirth_without_fear"
    display_name = Column(String, nullable=False)  # e.g., "두려움없는출산"
    source_type = Column(String, nullable=False)   # e.g., "book", "insurance"
    filepath_raw = Column(String, nullable=False)  # path to original
    purchase_link = Column(String, nullable=False) # URL for purchasing
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ============================================================================
# User Authentication and Profile Models
# ============================================================================

class User(Base):
    """User authentication table."""
    __tablename__ = "users"

    uuid = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False, index=True)  # Login ID
    password_hash = Column(String, nullable=False)  # Hashed password
    user_handle = Column(String, unique=True, nullable=True)  # Optional display name
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime, nullable=True)

    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations = relationship("ConversationHistory", back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
    """User profile information for prompt personalization."""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_uuid = Column(String, ForeignKey("users.uuid"), nullable=False, unique=True)

    # Personal information
    name = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    email = Column(String, nullable=True)

    # Additional profile data (JSON-like key-value pairs)
    preferences = Column(Text, nullable=True)  # JSON string for flexible data

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="profile")


class ConversationHistory(Base):
    """Conversation history between user and chatbot."""
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_uuid = Column(String, default=lambda: str(uuid.uuid4()), unique=True, index=True)
    user_uuid = Column(String, ForeignKey("users.uuid"), nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)  # Optional session grouping

    # Conversation content
    user_message = Column(Text, nullable=False)
    assistant_message = Column(Text, nullable=False)

    # Metadata
    domain = Column(String, nullable=True)  # e.g., "books", "insurance"
    language = Column(String, nullable=True)  # e.g., "English", "Korean"
    sources_used = Column(Text, nullable=True)  # JSON string of source references
    tokens_used = Column(Text, nullable=True)  # JSON string of token usage

    timestamp = Column(DateTime, default=func.now(), index=True)

    # Relationships
    user = relationship("User", back_populates="conversations")

