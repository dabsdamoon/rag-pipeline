"""Centralized configuration management for RAG Pipeline."""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """Application settings with validation."""

    # API Keys
    openai_api_key: str

    # Database - Supabase
    supabase_db_url: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_db_password: Optional[str] = None

    # Database - ChromaDB
    test_with_chromadb: bool = False
    chroma_persist_directory: str = "./chroma_db"

    # RAG Pipeline
    chunk_size: int = 500
    chunk_overlap: int = 100
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1536

    # LLM Models - GPT-5 variants
    llm_model: str = "gpt-5-mini"  # Options: gpt-5, gpt-5-mini, gpt-5-nano
    llm_model_streaming: str = "gpt-5-mini"  # Use same model for consistency
    summary_model: str = "gpt-5-mini"

    # Vector Store
    default_search_limit: int = 10
    min_relevance_threshold: float = 0.05

    # History
    default_history_limit: int = 5
    history_min_relevance: float = 0.2

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    cors_origins: List[str] = ["*"]

    # Collections
    collection_name: str = "houmy_sources"
    history_collection_name: str = "houmy_history"

    # Feature Flags
    enable_timing: bool = False

    @validator("openai_api_key")
    def validate_openai_key(cls, v):
        """Validate OpenAI API key format."""
        if not v:
            raise ValueError("OPENAI_API_KEY is required")
        if not v.startswith("sk-"):
            raise ValueError("Invalid OpenAI API key format")
        return v

    @validator("llm_model", "llm_model_streaming", "summary_model")
    def validate_model_name(cls, v):
        """Validate model name is a known GPT model."""
        valid_models = [
            "gpt-5", "gpt-5-mini", "gpt-5-nano",
            "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
        ]
        if v not in valid_models:
            raise ValueError(
                f"Model '{v}' not in known models: {valid_models}"
            )
        return v

    @validator("chunk_size")
    def validate_chunk_size(cls, v):
        """Validate chunk size is reasonable."""
        if v < 100 or v > 2000:
            raise ValueError("chunk_size must be between 100 and 2000")
        return v

    @validator("chunk_overlap")
    def validate_chunk_overlap(cls, v, values):
        """Validate chunk overlap is less than chunk size."""
        chunk_size = values.get("chunk_size", 500)
        if v >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        if v < 0:
            raise ValueError("chunk_overlap must be non-negative")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# For backward compatibility
settings = get_settings()
