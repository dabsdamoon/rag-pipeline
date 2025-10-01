"""Custom exception hierarchy for RAG Pipeline."""

from typing import Optional, Dict, Any


class RAGPipelineError(Exception):
    """Base exception for all RAG pipeline errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(RAGPipelineError):
    """Raised when configuration is invalid or missing."""
    pass


class DocumentProcessingError(RAGPipelineError):
    """Raised when document processing fails."""
    pass


class PDFExtractionError(DocumentProcessingError):
    """Raised when PDF text extraction fails."""
    pass


class ChunkingError(DocumentProcessingError):
    """Raised when text chunking fails."""
    pass


class EmbeddingGenerationError(RAGPipelineError):
    """Raised when embedding generation fails."""
    pass


class VectorStoreError(RAGPipelineError):
    """Raised when vector store operations fail."""
    pass


class SearchError(VectorStoreError):
    """Raised when vector search fails."""
    pass


class StorageError(VectorStoreError):
    """Raised when storing embeddings fails."""
    pass


class LLMError(RAGPipelineError):
    """Raised when LLM API calls fail."""
    pass


class StreamingError(LLMError):
    """Raised when streaming response fails."""
    pass


class HistoryError(RAGPipelineError):
    """Raised when history operations fail."""
    pass


class SourceNotFoundError(RAGPipelineError):
    """Raised when source metadata is not found."""

    def __init__(self, source_id: str):
        super().__init__(
            f"Source not found: {source_id}",
            details={"source_id": source_id}
        )
        self.source_id = source_id
