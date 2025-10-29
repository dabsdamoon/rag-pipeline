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


# ============================================================================
# User Management Schemas (Firebase)
# ============================================================================

class UserCreateRequest(BaseModel):
    user_id: str = Field(..., description="Unique user identifier (no authentication required)")
    name: str = Field(..., description="User's name", min_length=1, max_length=100)
    age: int = Field(..., description="User's age", ge=0, le=150)

class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Updated name", min_length=1, max_length=100)
    age: Optional[int] = Field(None, description="Updated age", ge=0, le=150)

class UserResponse(BaseModel):
    user_id: str
    name: str
    age: int
    created_at: str
    updated_at: str
    firebase_enabled: bool = Field(default=False, description="Whether Firebase is enabled for this user")

class UserProfileResponse(BaseModel):
    user: UserResponse
    conversation_count: int = Field(default=0, description="Total number of conversations")


# ============================================================================
# Conversation History Schemas (Firebase)
# ============================================================================

class ConversationSaveRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier")
    user_message: str = Field(..., description="User's message")
    assistant_message: str = Field(..., description="Assistant's response")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata (sources, tokens, etc.)")

class ConversationResponse(BaseModel):
    id: str = Field(..., description="Conversation ID")
    user_id: str
    session_id: str
    user_message: str
    assistant_message: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str

class ConversationListRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    limit: int = Field(50, description="Maximum number of conversations to retrieve", ge=1, le=100)
    session_id: Optional[str] = Field(None, description="Filter by session ID")

class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    user_id: str
    total_count: int

class ConversationDeleteRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    session_id: Optional[str] = Field(None, description="Delete only this session (optional)")

class ConversationDeleteResponse(BaseModel):
    user_id: str
    deleted_count: int
    message: str


# ============================================================================
# Firebase Status
# ============================================================================

class FirebaseStatusResponse(BaseModel):
    enabled: bool = Field(..., description="Whether Firebase is enabled in config")
    configured: bool = Field(..., description="Whether Firebase is properly configured")
    project_id: Optional[str] = Field(None, description="Firebase project ID")
    database_url: Optional[str] = Field(None, description="Firebase database URL")


# ============================================================================
# Local User Authentication Schemas
# ============================================================================

class UserRegisterRequest(BaseModel):
    username: str = Field(..., description="Unique username for login", min_length=3, max_length=50)
    password: str = Field(..., description="Password", min_length=6, max_length=100)
    user_handle: Optional[str] = Field(None, description="Optional display name/handle", max_length=50)
    name: Optional[str] = Field(None, description="User's real name", max_length=100)
    age: Optional[int] = Field(None, description="User's age", ge=0, le=150)
    email: Optional[str] = Field(None, description="User's email")

class UserLoginRequest(BaseModel):
    username: str = Field(..., description="Username for login")
    password: str = Field(..., description="Password")

class UserAuthResponse(BaseModel):
    uuid: str = Field(..., description="User's unique UUID")
    username: str
    user_handle: Optional[str] = None
    created_at: str
    last_login: Optional[str] = None
    message: str = "Success"

class UserProfileResponse(BaseModel):
    uuid: str
    username: str
    user_handle: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    email: Optional[str] = None
    created_at: str
    conversation_count: int = 0

class UserProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    age: Optional[int] = Field(None, ge=0, le=150)
    email: Optional[str] = None
    user_handle: Optional[str] = Field(None, max_length=50)


# ============================================================================
# Local Conversation History Schemas
# ============================================================================

class ConversationHistoryResponse(BaseModel):
    conversation_uuid: str
    user_uuid: str
    session_id: Optional[str]
    user_message: str
    assistant_message: str
    domain: Optional[str]
    language: Optional[str]
    timestamp: str

class ConversationHistoryListResponse(BaseModel):
    conversations: List[ConversationHistoryResponse]
    total_count: int
    user_uuid: str


# ============================================================================
# Character Creation Schemas
# ============================================================================

class CharacterTags(BaseModel):
    relationship: str = Field(..., description="Type of relationship (e.g., friend, co-worker)")
    tone: str = Field(..., description="Communication tone (e.g., formal, casual)")
    characteristics: str = Field(..., description="Personality characteristic (e.g., humorous, empathetic)")

class CharacterCreateRequest(BaseModel):
    name: str = Field(..., description="Character's name", min_length=1, max_length=100)
    occupation: str = Field(..., description="Character's occupation", min_length=1, max_length=100)
    age: int = Field(..., description="Character's age", ge=1, le=150)
    gender: str = Field(..., description="Character's gender", min_length=1, max_length=50)
    tags: CharacterTags = Field(..., description="Personality and style tags")
    model: str = Field("gpt-4o-mini", description="OpenAI model to use for generation")
    temperature: float = Field(0.7, description="Generation temperature", ge=0.0, le=1.0)

class CharacterResponse(BaseModel):
    name: str
    occupation: str
    age: int
    gender: str
    tags: Dict[str, str]
    speaking_style: str = Field(..., description="Generated speaking style description")
    appearance: str = Field(..., description="Generated appearance description")
    success: bool
    errors: List[str] = []

class AvailableTagsResponse(BaseModel):
    relationship: List[str]
    tone: List[str]
    characteristics: List[str]


# ============================================================================
# Roleplay Schemas
# ============================================================================

class CharacterSaveRequest(BaseModel):
    character: Dict[str, Any] = Field(..., description="Character data to save")

class CharacterSaveResponse(BaseModel):
    character_id: str = Field(..., description="UUID of saved character")
    message: str = "Character saved successfully"

class CharacterListResponse(BaseModel):
    characters: List[Dict[str, Any]] = Field(..., description="List of all characters")
    total_count: int

class RoleplayChatRequest(BaseModel):
    character_id: str = Field(..., description="ID of character to roleplay as")
    message: str = Field(..., description="User's message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_id: Optional[str] = Field("roleplay_user", description="User identifier")
    model: str = Field("gpt-4o-mini", description="LLM model to use")
    temperature: float = Field(0.8, description="Generation temperature", ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, description="Maximum tokens for response")

class RoleplayChatResponse(BaseModel):
    response: str = Field(..., description="Character's response")
    session_id: str
    character_name: str
    tokens_used: Dict[str, int] = {}
