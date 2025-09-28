from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum

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

