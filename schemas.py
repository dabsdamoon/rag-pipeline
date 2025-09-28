from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum

class ProcessingStatusEnum(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DomainEnum(str, Enum):
    BOOKS = "books"
    INSURANCE = "insurance"

class ChatRequest(BaseModel):
    message: str = Field(..., description="User's message to the chatbot")
    language: str = Field(..., description="Language of the user's message")
    domain: DomainEnum = Field(..., description="Domain type: 'books' for RAG-based queries, 'insurance' for claim guidance")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation continuity")
    user_id: Optional[str] = Field(None, description="Identifier for the end user to personalise history retrieval")
    source_ids: Optional[List[str]] = Field(None, description="Optional filter by specific sources (only used for book domain)")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens for response generation (None for unlimited)")
    min_relevance_score: Optional[float] = Field(
        None,
        description="Minimum relevance score threshold for retrieved documents",
        ge=0.0,
        le=1.0,
    )
    layer_config: Optional[Dict[str, Dict[str, Any]]] = Field(
        None,
        description=(
            "Optional configuration for prompt layers. Each key should match a layer id"
            " (e.g., 'user', 'history') and may include 'include', 'id', 'variables', or 'prompt'."
        ),
    )


class Source(BaseModel):
    source_id: str
    page_number: int
    excerpt: str
    relevance_score: float
    display_name: str
    purchase_link: str

class ChatResponse(BaseModel):
    response: str
    session_id: str
    sources: List[Source]
    tokens_used: Dict[str, int]

class SourceUpload(BaseModel):
    title: str
    author: Optional[str] = None
    description: Optional[str] = None

class SourceResponse(BaseModel):
    source_id: str
    title: str
    author: Optional[str]
    description: Optional[str]
    page_count: Optional[int]
    upload_date: datetime
    processing_status: ProcessingStatusEnum
    file_size: Optional[int]
    content_type: Optional[str]

class SourceListResponse(BaseModel):
    sources: List[SourceResponse]
    total_count: int
    limit: int
    offset: int

class SourceUploadResponse(BaseModel):
    source_id: str
    message: str
    processing_status: ProcessingStatusEnum


class SourceProcessResponse(BaseModel):
    source_id: str
    status: ProcessingStatusEnum
    message: str

class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(5, description="Maximum number of results")
    source_ids: Optional[List[str]] = Field(None, description="Optional filter by specific sources")
    min_relevance_score: float = Field(0.2, description="Minimum relevance score threshold")

class SearchResult(BaseModel):
    source_id: str
    name: str
    page_number: int
    content: str
    relevance_score: float

class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    total_results: int

class PromptResponse(BaseModel):
    prompt_id: str
    name: str
    template: str
    description: str
    variables: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class PromptListResponse(BaseModel):
    prompts: List[PromptResponse]

class PromptCreateRequest(BaseModel):
    name: str
    template: str
    description: Optional[str] = ""
    variables: Optional[List[str]] = None

class PromptCreateResponse(BaseModel):
    prompt_id: str
    message: str

class HealthResponse(BaseModel):
    status: str
    version: str
    database_status: str
    llm_service_status: str

class ErrorResponse(BaseModel):
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None

class SourceMetadataResponse(BaseModel):
    source_id: str
    name: str
    display_name: str
    source_type: str
    filepath_raw: str
    purchase_link: str
    created_at: datetime
    updated_at: datetime

class SourceMetadataListResponse(BaseModel):
    sources: List[SourceMetadataResponse]
    total_count: int
    limit: int
    offset: int


class UploadRawSourcesRequest(BaseModel):
    bucket: str
    metadata_path: str = "assets/dict_source_id.json"
    prefix: Optional[str] = ""
    overwrite: bool = False
    create_bucket: bool = False
    public_bucket: bool = False
    dry_run: bool = False


class UploadRawSourcesItem(BaseModel):
    source_id: str
    local_path: str
    remote_path: Optional[str] = None
    status: Literal["uploaded", "dry_run", "missing", "skipped", "error"]
    detail: Optional[str] = None


class UploadRawSourcesResponse(BaseModel):
    bucket: str
    results: List[UploadRawSourcesItem]
