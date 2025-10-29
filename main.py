from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from exceptions import RAGPipelineError
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import uuid
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict

from databases import get_db, create_tables
from metadata_utils import get_source_metadata_map, seed_metadata_from_json
from models import Sources, ProcessingStatus, SourceMetadata, User, UserProfile, ConversationHistory
from schemas import *
from modules.rag_pipeline import RAGPipeline
from modules.character_creation_pipeline import CharacterCreationPipeline
from prompts.prompt_manager import PromptManager
from services import get_firebase_service
from supabase import Client, create_client
from storage3.utils import StorageException
import asyncio
import json
import hashlib
import secrets
from datetime import datetime as dt


load_dotenv(".env")

# ============================================================================
# Password Hashing Utilities
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    try:
        salt, pwd_hash = hashed.split('$')
        return hashlib.sha256((password + salt).encode()).hexdigest() == pwd_hash
    except:
        return False

# ============================================================================
# Helper Functions
# ============================================================================

def populate_source_metadata():
    """Ensure SourceMetadata records exist, seeding from JSON when necessary."""
    existing = get_source_metadata_map()
    if existing:
        print(f"SourceMetadata table already has {len(existing)} entries. Skipping population.")
        return

    dict_source_id_path = "assets/dict_source_id.json"
    inserted = seed_metadata_from_json(dict_source_id_path)
    if inserted:
        print(f"Seeded SourceMetadata table with {inserted} entries from {dict_source_id_path}.")
    else:
        print("No source metadata found to seed. Please insert records via admin tooling.")


def _create_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials are not configured.")
    return create_client(url, key)


def _build_remote_path(prefix: str, source_id: str, filename: str) -> str:
    clean_segments = [segment.strip("/\\") for segment in (prefix, source_id) if segment]
    clean_segments.append(filename)
    return "/".join(clean_segments)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("=" * 60)
    print("🚀 Starting RAG Chatbot API")
    print("=" * 60)
    try:
        print("📊 Creating database tables...")
        create_tables()
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        import traceback
        traceback.print_exc()
        raise

    try:
        print("📝 Populating source metadata...")
        populate_source_metadata()
        print("✅ Source metadata populated successfully")
    except Exception as e:
        print(f"❌ Failed to populate metadata: {e}")
        import traceback
        traceback.print_exc()
        raise

    print("=" * 60)
    print("✅ API startup complete")
    print("=" * 60)
    yield
    # Shutdown (if needed)
    print("🛑 Shutting down API...")

app = FastAPI(
    title="RAG Chatbot API",
    description="A general-purpose RAG-based chatbot API with configurable system prompts",
    version="2.0.0",
    lifespan=lifespan
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handlers
@app.exception_handler(RAGPipelineError)
async def rag_exception_handler(request: Request, exc: RAGPipelineError):
    """Handle RAG pipeline exceptions."""
    print(f"[API ERROR] {exc.__class__.__name__}: {exc.message}")
    return JSONResponse(
        status_code=500,
        content=exc.to_dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    print(f"[API ERROR] Unexpected error: {str(exc)}")
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "error_type": "InternalServerError",
            "message": "An unexpected error occurred",
            "details": {"error": str(exc)}
        }
    )

# Initialize RAG pipeline and prompt manager
USE_CHROMADB = os.getenv("TEST_WITH_CHROMADB", "false").lower() == "true"
print(f"🔧 Initializing RAG Pipeline (ChromaDB mode: {USE_CHROMADB})...")
try:
    rag_pipeline = RAGPipeline(test_with_chromadb=USE_CHROMADB)
    print("✅ RAG Pipeline initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize RAG Pipeline: {e}")
    import traceback
    traceback.print_exc()
    raise

print("🔧 Initializing Prompt Manager...")
try:
    prompt_manager = PromptManager()
    print("✅ Prompt Manager initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Prompt Manager: {e}")
    import traceback
    traceback.print_exc()
    raise

print("🔧 Initializing Firebase Service...")
try:
    firebase_service = get_firebase_service()
    print("✅ Firebase Service initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Firebase Service: {e}")
    import traceback
    traceback.print_exc()
    raise

print("🔧 Initializing Character Creation Pipeline...")
try:
    character_pipeline = CharacterCreationPipeline()
    print("✅ Character Creation Pipeline initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Character Creation Pipeline: {e}")
    import traceback
    traceback.print_exc()
    raise

print("🔧 Initializing Character Storage Service...")
try:
    from services.character_storage import CharacterStorageService
    character_storage = CharacterStorageService()
    print("✅ Character Storage Service initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Character Storage Service: {e}")
    import traceback
    traceback.print_exc()
    raise

print("🔧 Initializing Roleplay Manager...")
try:
    from services.roleplay_manager import RoleplayManager
    roleplay_manager = RoleplayManager()
    print("✅ Roleplay Manager initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Roleplay Manager: {e}")
    import traceback
    traceback.print_exc()
    raise

# Create upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Static files not needed - using React frontend


@app.get("/")
async def root():
    """API root endpoint"""
    return JSONResponse({
        "message": "RAG Chatbot API - A general-purpose RAG pipeline with configurable system prompts",
        "version": "2.0.0",
        "docs": "/docs"
    })

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """Send a message to the chatbot"""
    try:
        # Enrich layer_config with user profile if user_id is provided
        enriched_layer_config = request.layer_config or {}
        if request.user_id:
            try:
                # Try to parse as UUID (local auth)
                user = db.query(User).filter(User.uuid == request.user_id).first()
                if user:
                    profile = db.query(UserProfile).filter(UserProfile.user_uuid == request.user_id).first()
                    if profile:
                        # Add user layer to prompt with profile info
                        enriched_layer_config["user"] = {
                            "include": True,
                            "id": "default",
                            "variables": {
                                "name": profile.name or "User",
                                "age": str(profile.age) if profile.age else "Not specified",
                            }
                        }
                        print(f"[CHAT] Using user profile for {user.username}")
            except Exception as e:
                print(f"[CHAT WARNING] Could not fetch user profile: {e}")

        response_data = rag_pipeline.chat(
            message=request.message,
            language=request.language,
            session_id=request.session_id,
            user_id=request.user_id,
            source_ids=request.source_ids,
            domain=request.domain,
            min_relevance_score=request.min_relevance_score,
            layer_config=enriched_layer_config,
        )

        # Save conversation to database if user_id is provided
        if request.user_id and response_data.get("response"):
            try:
                conversation = ConversationHistory(
                    user_uuid=request.user_id,
                    session_id=response_data.get("session_id"),
                    user_message=request.message,
                    assistant_message=response_data["response"],
                    domain=request.domain.value if hasattr(request.domain, 'value') else str(request.domain),
                    language=request.language,
                    sources_used=json.dumps([s.dict() for s in response_data.get("sources", [])]),
                    tokens_used=json.dumps(response_data.get("tokens_used", {}))
                )
                db.add(conversation)
                db.commit()
                print(f"[CHAT] Saved conversation to database")
            except Exception as exc:
                db.rollback()
                print(f"[API WARNING] Failed to persist chat history: {exc}")

        # Also use legacy history manager
        if request.user_id and response_data.get("response"):
            try:
                rag_pipeline.record_turn_history(
                    user_id=request.user_id,
                    session_id=response_data.get("session_id"),
                    user_message=request.message,
                    assistant_message=response_data["response"],
                )
            except Exception as exc:
                print(f"[API WARNING] Failed to persist legacy history: {exc}")

        return ChatResponse(**response_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """Send a message to the chatbot with streaming response"""
    print(f"📨 Received streaming chat request: message='{request.message[:50]}...', domain={request.domain}, source_ids={request.source_ids}")
    try:
        # Enrich layer_config with user profile if user_id is provided
        enriched_layer_config = request.layer_config or {}
        if request.user_id:
            try:
                user = db.query(User).filter(User.uuid == request.user_id).first()
                if user:
                    profile = db.query(UserProfile).filter(UserProfile.user_uuid == request.user_id).first()
                    if profile:
                        enriched_layer_config["user"] = {
                            "include": True,
                            "id": "default",
                            "variables": {
                                "name": profile.name or "User",
                                "age": str(profile.age) if profile.age else "Not specified",
                            }
                        }
                        print(f"[CHAT STREAM] Using user profile for {user.username}")
            except Exception as e:
                print(f"[CHAT STREAM WARNING] Could not fetch user profile: {e}")

        def generate():
            try:
                accumulated_chunks: List[str] = []
                # Call RAGPipeline directly with streaming
                response_data = rag_pipeline.chat(
                    message=request.message,
                    language=request.language,
                    session_id=request.session_id,
                    user_id=request.user_id,
                    source_ids=request.source_ids,
                    stream=True,
                    domain=request.domain,
                    max_tokens=request.max_tokens,
                    min_relevance_score=request.min_relevance_score,
                    layer_config=enriched_layer_config,
                )
                session_id = response_data.get("session_id")

                # Stream content from OpenAI chunks in SSE format
                for chunk in response_data["stream"]:
                    # Extract content from chunk (similar to how Node.js would parse OpenAI response)
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        accumulated_chunks.append(content)
                        yield f"data: {content}\n\n"

                # Save conversation after streaming completes
                if request.user_id:
                    final_response = "".join(accumulated_chunks).strip()
                    if final_response:
                        try:
                            conversation = ConversationHistory(
                                user_uuid=request.user_id,
                                session_id=session_id,
                                user_message=request.message,
                                assistant_message=final_response,
                                domain=request.domain.value if hasattr(request.domain, 'value') else str(request.domain),
                                language=request.language
                            )
                            db.add(conversation)
                            db.commit()
                            print(f"[CHAT STREAM] Saved conversation to database")
                        except Exception as exc:
                            db.rollback()
                            print(f"[API WARNING] Failed to persist streaming chat history to DB: {exc}")

                        # Also use legacy history manager
                        try:
                            rag_pipeline.record_turn_history(
                                user_id=request.user_id,
                                session_id=session_id,
                                user_message=request.message,
                                assistant_message=final_response,
                            )
                        except Exception as exc:
                            print(f"[API WARNING] Failed to persist legacy history: {exc}")
                
            except Exception as e:
                import traceback
                error_msg = f"Stream generation error: {str(e)}"
                print(error_msg)
                print(traceback.format_exc())
                # Even errors should be in raw format
                error_data = f"data: {json.dumps({'error': str(e)})}\n\n"
                yield error_data
        
        return StreamingResponse(
            generate(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        print(f"❌ Chat stream error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sources/upload_raw", response_model=UploadRawSourcesResponse)
async def upload_raw_sources(
    payload: UploadRawSourcesRequest,
    db: Session = Depends(get_db),
) -> UploadRawSourcesResponse:
    metadata_path = Path(payload.metadata_path)
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail=f"Metadata file not found at {metadata_path}.")

    try:
        metadata: Dict[str, Dict[str, str]]
        with metadata_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in {metadata_path}: {exc}") from exc

    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="Metadata JSON must be an object keyed by source_id.")

    try:
        supabase_client = _create_supabase_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    storage_api = supabase_client.storage
    try:
        existing_buckets = {bucket.name for bucket in storage_api.list_buckets()}
    except StorageException as exc:
        raise HTTPException(status_code=502, detail=f"Failed to list buckets: {exc}") from exc

    if payload.bucket not in existing_buckets:
        if not payload.create_bucket:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Bucket '{payload.bucket}' not found. Enable create_bucket to create it automatically."
                ),
            )
        try:
            storage_api.create_bucket(payload.bucket, options={"public": payload.public_bucket})
        except StorageException as exc:
            raise HTTPException(status_code=502, detail=f"Failed to create bucket: {exc}") from exc

    bucket_client = storage_api.from_(payload.bucket)
    results: List[UploadRawSourcesItem] = []
    uploaded_any = False

    for source_id, info in metadata.items():
        local_path_value = info.get("filepath_raw")
        if not local_path_value:
            results.append(
                UploadRawSourcesItem(
                    source_id=source_id,
                    local_path="",
                    status="skipped",
                    detail="No 'filepath_raw' found in metadata entry.",
                )
            )
            continue

        local_path = Path(local_path_value)
        remote_path = _build_remote_path(payload.prefix or "", source_id, local_path.name)

        if not local_path.is_file():
            results.append(
                UploadRawSourcesItem(
                    source_id=source_id,
                    local_path=str(local_path),
                    remote_path=remote_path,
                    status="missing",
                    detail="Local file does not exist.",
                )
            )
            continue

        if payload.dry_run:
            results.append(
                UploadRawSourcesItem(
                    source_id=source_id,
                    local_path=str(local_path),
                    remote_path=remote_path,
                    status="dry_run",
                    detail="Dry run enabled; no upload attempted.",
                )
            )
            continue

        options = {"content-type": "text/plain"}
        if payload.overwrite:
            options["upsert"] = "true"

        try:
            bucket_client.upload(remote_path, local_path.read_bytes(), options)
        except StorageException as exc:
            results.append(
                UploadRawSourcesItem(
                    source_id=source_id,
                    local_path=str(local_path),
                    remote_path=remote_path,
                    status="error",
                    detail=str(exc),
                )
            )
            continue

        record = (
            db.query(SourceMetadata)
            .filter(SourceMetadata.source_id == source_id)
            .one_or_none()
        )
        detail = None
        if record is not None:
            record.filepath_raw = remote_path
            uploaded_any = True
        else:
            detail = "SourceMetadata record not found; storage uploaded but DB unchanged."

        results.append(
            UploadRawSourcesItem(
                source_id=source_id,
                local_path=str(local_path),
                remote_path=remote_path,
                status="uploaded",
                detail=detail,
            )
        )

    if payload.dry_run:
        db.rollback()
    elif uploaded_any:
        db.commit()
    else:
        db.rollback()

    return UploadRawSourcesResponse(bucket=payload.bucket, results=results)

@app.get("/domains/status")
async def domain_status():
    """Check status of API keys"""
    openai_key = os.getenv("OPENAI_API_KEY")
    return {
        "domains": {
            "books": {
                "name": "Books Domain", 
                "api_key_configured": bool(openai_key),
                "model": "gpt-4o-mini",
                "provider": "openai"
            },
            "insurance": {
                "name": "Insurance Domain",
                "api_key_configured": bool(openai_key), 
                "model": "gpt-4o-mini",
                "provider": "openai"
            }
        },
        "all_configured": bool(openai_key)
    }

@app.get("/sources", response_model=SourceMetadataListResponse)
def list_sources(limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
    """List all available sources from metadata"""
    sources = db.query(SourceMetadata).offset(offset).limit(limit).all()
    total_count = db.query(SourceMetadata).count()
    
    source_responses = [
        SourceMetadataResponse(
            source_id=source.source_id,
            name=source.name,
            display_name=source.display_name,
            source_type=source.source_type,
            filepath_raw=source.filepath_raw,
            purchase_link=source.purchase_link,
            created_at=source.created_at,
            updated_at=source.updated_at
        )
        for source in sources
    ]
    
    return SourceMetadataListResponse(
        sources=source_responses,
        total_count=total_count,
        limit=limit,
        offset=offset
    )

@app.post("/sources", response_model=SourceUploadResponse)
async def upload_source(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a new source"""
    # Generate unique source ID
    source_id = str(uuid.uuid4())
    
    # Save uploaded file
    file_path = UPLOAD_DIR / f"{source_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create source record
    source = Source(
        id=source_id,
        title=title,
        author=author,
        description=description,
        file_size=os.path.getsize(file_path),
        content_type=file.content_type,
        processing_status=ProcessingStatus.PROCESSING,
        file_path=str(file_path)
    )
    
    db.add(source)
    db.commit()
    
    # Process source in background
    asyncio.create_task(process_source_async(source_id, db))
    
    return SourceUploadResponse(
        source_id=source_id,
        message="Source uploaded successfully",
        processing_status=ProcessingStatus.PROCESSING
    )


@app.post("/sources/{source_id}/process", response_model=SourceProcessResponse)
def process_source_endpoint(source_id: str):
    """Process a known source and persist its embeddings to the vector store."""
    rag_pipeline.refresh_source_metadata()

    if source_id not in rag_pipeline.source_metadata:
        raise HTTPException(status_code=404, detail=f"Source metadata not found for {source_id}")

    try:
        success = rag_pipeline.process_source(source_id)
    except AssertionError as exc:  # Defensive guard against missing metadata
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process source {source_id}: {exc}") from exc

    if not success:
        raise HTTPException(status_code=500, detail=f"Processing pipeline returned False for {source_id}")

    return SourceProcessResponse(
        source_id=source_id,
        status=ProcessingStatusEnum.COMPLETED,
        message="Source processed and embeddings stored successfully."
    )

async def process_source_async(source_id: str, db: Session):
    """Process source in background"""
    try:
        success = rag_pipeline.process_source(source_id)
        
        # Update source status
        source = db.query(Source).filter(Source.source_id == source_id).first()
        if source:
            source.processing_status = ProcessingStatus.COMPLETED if success else ProcessingStatus.FAILED
            db.commit()
            
    except Exception as e:
        # Update source status to failed
        source = db.query(Source).filter(Source.source_id == source_id).first()
        if source:
            source.processing_status = ProcessingStatus.FAILED
            db.commit()

@app.get("/sources/{source_id}", response_model=SourceResponse)
def get_source(source_id: str, db: Session = Depends(get_db)):
    """Get source details"""
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return SourceResponse(
        source_id=source.source_id,
        title=source.title,
        author=source.author,
        description=source.description,
        page_count=source.page_count,
        upload_date=source.upload_date,
        processing_status=source.processing_status,
        file_size=source.file_size,
        content_type=source.content_type
    )

@app.delete("/sources/{source_id}")
def delete_source(source_id: str, db: Session = Depends(get_db)):
    """Delete a source"""
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Delete file if exists
    if source.file_path and os.path.exists(source.file_path):
        os.remove(source.file_path)
    
    # Delete from database
    db.delete(source)
    db.commit()
    
    return JSONResponse(status_code=204, content={})

@app.post("/search", response_model=SearchResponse)
def search_sources(request: SearchRequest, db: Session = Depends(get_db)):
    """Search through knowledge base"""
    results = rag_pipeline.search_documents(
        query=request.query,
        limit=request.limit,
        source_ids=request.source_ids,
        min_relevance_score=request.min_relevance_score
    )
    
    # Enhance results with source titles
    search_results = []
    for result in results:
        source = db.query(SourceMetadata).filter(SourceMetadata.source_id == result["source_id"]).first()
        search_results.append(
            SearchResult(
                source_id=result["source_id"],
                name=source.name if source else "Unknown",
                page_number=result["page_number"],
                content=result["content"],
                relevance_score=result["relevance_score"]
            )
        )
    
    return SearchResponse(
        results=search_results,
        query=request.query,
        total_results=len(search_results)
    )

@app.get("/prompts", response_model=PromptListResponse)
def list_prompts():
    """List available prompts"""
    prompts_data = prompt_manager.list_prompts()
    prompts = [PromptResponse(**prompt) for prompt in prompts_data]
    return PromptListResponse(prompts=prompts)

@app.post("/prompts", response_model=PromptCreateResponse)
def create_prompt(request: PromptCreateRequest):
    """Create or update a prompt"""
    prompt_id = request.name.lower().replace(" ", "_")
    prompt_manager.add_prompt(prompt_id, request.template, request.description)
    
    return PromptCreateResponse(
        prompt_id=prompt_id,
        message="Prompt created successfully"
    )

@app.get("/prompts/{prompt_id}", response_model=PromptResponse)
def get_prompt(prompt_id: str):
    """Get specific prompt"""
    template = prompt_manager.get_prompt(prompt_id)
    if not template:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    return PromptResponse(
        prompt_id=prompt_id,
        name=prompt_id.replace("_", " ").title(),
        template=template,
        description=f"Prompt {prompt_id}"
    )

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check"""
    # Check database connection
    try:
        db = next(get_db())
        db.execute("SELECT 1")
        database_status = "connected"
    except:
        database_status = "disconnected"

    # Check OpenAI API
    llm_status = "available" if os.getenv("OPENAI_API_KEY") else "not_configured"

    return HealthResponse(
        status="healthy",
        version="2.0.0",
        database_status=database_status,
        llm_service_status=llm_status
    )


# ============================================================================
# User Management Endpoints (Firebase)
# ============================================================================

@app.post("/users", response_model=UserResponse)
async def create_user(request: UserCreateRequest):
    """Create a new user profile (no authentication required for demo)"""
    try:
        user_data = firebase_service.create_user(
            user_id=request.user_id,
            name=request.name,
            age=request.age
        )
        return UserResponse(**user_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


@app.get("/users/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(user_id: str):
    """Get user profile and conversation statistics"""
    try:
        user_data = firebase_service.get_user(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Get conversation count
        conversations = firebase_service.get_user_conversations(user_id, limit=1000)

        return UserProfileResponse(
            user=UserResponse(**user_data),
            conversation_count=len(conversations)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user profile: {str(e)}")


@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user_profile(user_id: str, request: UserUpdateRequest):
    """Update user profile information"""
    try:
        # First check if user exists
        user_data = firebase_service.get_user(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user
        success = firebase_service.update_user(
            user_id=user_id,
            name=request.name,
            age=request.age
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update user")

        # Get updated user data
        updated_user = firebase_service.get_user(user_id)
        return UserResponse(**updated_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")


# ============================================================================
# Conversation History Endpoints (Firebase)
# ============================================================================

@app.post("/conversations", response_model=Dict[str, str])
async def save_conversation(request: ConversationSaveRequest):
    """Save a conversation turn (normally called automatically by /chat endpoint)"""
    try:
        conversation_id = firebase_service.save_conversation(
            user_id=request.user_id,
            session_id=request.session_id,
            user_message=request.user_message,
            assistant_message=request.assistant_message,
            metadata=request.metadata
        )
        return {"conversation_id": conversation_id, "message": "Conversation saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save conversation: {str(e)}")


@app.post("/conversations/list", response_model=ConversationListResponse)
async def list_conversations(request: ConversationListRequest):
    """Get conversation history for a user"""
    try:
        conversations = firebase_service.get_user_conversations(
            user_id=request.user_id,
            limit=request.limit,
            session_id=request.session_id
        )

        conversation_responses = [
            ConversationResponse(
                id=conv.get("id", ""),
                user_id=conv["user_id"],
                session_id=conv["session_id"],
                user_message=conv["user_message"],
                assistant_message=conv["assistant_message"],
                metadata=conv.get("metadata"),
                timestamp=str(conv.get("timestamp", ""))
            )
            for conv in conversations
        ]

        return ConversationListResponse(
            conversations=conversation_responses,
            user_id=request.user_id,
            total_count=len(conversation_responses)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@app.post("/conversations/delete", response_model=ConversationDeleteResponse)
async def delete_conversations(request: ConversationDeleteRequest):
    """Delete conversation history for a user"""
    try:
        deleted_count = firebase_service.delete_user_conversations(
            user_id=request.user_id,
            session_id=request.session_id
        )

        message = f"Deleted {deleted_count} conversation(s)"
        if request.session_id:
            message += f" for session {request.session_id}"

        return ConversationDeleteResponse(
            user_id=request.user_id,
            deleted_count=deleted_count,
            message=message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete conversations: {str(e)}")


@app.get("/firebase/status", response_model=FirebaseStatusResponse)
async def firebase_status():
    """Check Firebase service status"""
    try:
        status = firebase_service.get_status()
        return FirebaseStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Firebase status: {str(e)}")


# ============================================================================
# Local User Authentication Endpoints
# ============================================================================

@app.post("/auth/register", response_model=UserAuthResponse)
async def register_user(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user with username and password (local SQLite)."""
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == request.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail=f"Username '{request.username}' already exists")

        # Check if user_handle already exists (if provided)
        if request.user_handle:
            existing_handle = db.query(User).filter(User.user_handle == request.user_handle).first()
            if existing_handle:
                raise HTTPException(status_code=400, detail=f"User handle '{request.user_handle}' already exists")

        # Create new user
        user_uuid = str(uuid.uuid4())
        hashed_pwd = hash_password(request.password)

        new_user = User(
            uuid=user_uuid,
            username=request.username,
            password_hash=hashed_pwd,
            user_handle=request.user_handle,
            created_at=dt.utcnow()
        )
        db.add(new_user)

        # Create user profile
        new_profile = UserProfile(
            user_uuid=user_uuid,
            name=request.name,
            age=request.age,
            email=request.email
        )
        db.add(new_profile)

        db.commit()
        db.refresh(new_user)

        return UserAuthResponse(
            uuid=new_user.uuid,
            username=new_user.username,
            user_handle=new_user.user_handle,
            created_at=new_user.created_at.isoformat(),
            last_login=None,
            message="User registered successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to register user: {str(e)}")


@app.post("/auth/login", response_model=UserAuthResponse)
async def login_user(request: UserLoginRequest, db: Session = Depends(get_db)):
    """Login with username and password (local SQLite)."""
    try:
        # Find user by username
        user = db.query(User).filter(User.username == request.username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Update last login
        user.last_login = dt.utcnow()
        db.commit()
        db.refresh(user)

        return UserAuthResponse(
            uuid=user.uuid,
            username=user.username,
            user_handle=user.user_handle,
            created_at=user.created_at.isoformat(),
            last_login=user.last_login.isoformat() if user.last_login else None,
            message="Login successful"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@app.get("/auth/profile/{user_uuid}", response_model=UserProfileResponse)
async def get_user_profile(user_uuid: str, db: Session = Depends(get_db)):
    """Get user profile with conversation count."""
    try:
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        profile = db.query(UserProfile).filter(UserProfile.user_uuid == user_uuid).first()
        conversation_count = db.query(ConversationHistory).filter(
            ConversationHistory.user_uuid == user_uuid
        ).count()

        return UserProfileResponse(
            uuid=user.uuid,
            username=user.username,
            user_handle=user.user_handle,
            name=profile.name if profile else None,
            age=profile.age if profile else None,
            email=profile.email if profile else None,
            created_at=user.created_at.isoformat(),
            conversation_count=conversation_count
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}")


@app.put("/auth/profile/{user_uuid}", response_model=UserProfileResponse)
async def update_user_profile(
    user_uuid: str,
    request: UserProfileUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update user profile information."""
    try:
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        profile = db.query(UserProfile).filter(UserProfile.user_uuid == user_uuid).first()
        if not profile:
            # Create profile if it doesn't exist
            profile = UserProfile(user_uuid=user_uuid)
            db.add(profile)

        # Update profile fields
        if request.name is not None:
            profile.name = request.name
        if request.age is not None:
            profile.age = request.age
        if request.email is not None:
            profile.email = request.email
        if request.user_handle is not None:
            # Check if handle is already taken
            existing_handle = db.query(User).filter(
                User.user_handle == request.user_handle,
                User.uuid != user_uuid
            ).first()
            if existing_handle:
                raise HTTPException(status_code=400, detail=f"User handle '{request.user_handle}' already exists")
            user.user_handle = request.user_handle

        profile.updated_at = dt.utcnow()
        db.commit()
        db.refresh(user)
        db.refresh(profile)

        conversation_count = db.query(ConversationHistory).filter(
            ConversationHistory.user_uuid == user_uuid
        ).count()

        return UserProfileResponse(
            uuid=user.uuid,
            username=user.username,
            user_handle=user.user_handle,
            name=profile.name,
            age=profile.age,
            email=profile.email,
            created_at=user.created_at.isoformat(),
            conversation_count=conversation_count
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


# ============================================================================
# Local Conversation History Endpoints
# ============================================================================

@app.get("/auth/history/{user_uuid}", response_model=ConversationHistoryListResponse)
async def get_user_conversation_history(
    user_uuid: str,
    limit: int = 50,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get conversation history for a user."""
    try:
        # Verify user exists
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Query conversations
        query = db.query(ConversationHistory).filter(ConversationHistory.user_uuid == user_uuid)

        if session_id:
            query = query.filter(ConversationHistory.session_id == session_id)

        query = query.order_by(ConversationHistory.timestamp.desc()).limit(limit)
        conversations = query.all()

        conversation_responses = [
            ConversationHistoryResponse(
                conversation_uuid=conv.conversation_uuid,
                user_uuid=conv.user_uuid,
                session_id=conv.session_id,
                user_message=conv.user_message,
                assistant_message=conv.assistant_message,
                domain=conv.domain,
                language=conv.language,
                timestamp=conv.timestamp.isoformat()
            )
            for conv in conversations
        ]

        return ConversationHistoryListResponse(
            conversations=conversation_responses,
            total_count=len(conversation_responses),
            user_uuid=user_uuid
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")


@app.delete("/auth/history/{user_uuid}")
async def delete_user_conversation_history(
    user_uuid: str,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Delete conversation history for a user."""
    try:
        # Verify user exists
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Delete conversations
        query = db.query(ConversationHistory).filter(ConversationHistory.user_uuid == user_uuid)

        if session_id:
            query = query.filter(ConversationHistory.session_id == session_id)

        deleted_count = query.delete()
        db.commit()

        message = f"Deleted {deleted_count} conversation(s)"
        if session_id:
            message += f" for session {session_id}"

        return {"message": message, "deleted_count": deleted_count}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation history: {str(e)}")


# ============================================================================
# Character Creation Endpoints
# ============================================================================

@app.get("/character/tags", response_model=AvailableTagsResponse)
async def get_available_tags():
    """Get all available character tags."""
    try:
        tags = character_pipeline.get_available_tags()
        return AvailableTagsResponse(**tags)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available tags: {str(e)}")


@app.post("/character/create", response_model=CharacterResponse)
async def create_character(request: CharacterCreateRequest):
    """
    Create a character with AI-generated speaking style and appearance.

    This endpoint uses LLM to generate detailed character descriptions based on
    the provided attributes (name, occupation, age, gender) and personality tags.

    Speaking style and appearance are generated in parallel for better performance.
    """
    try:
        character = await character_pipeline.create_character(
            name=request.name,
            occupation=request.occupation,
            age=request.age,
            gender=request.gender,
            tags=request.tags.model_dump(),
            model=request.model,
            temperature=request.temperature
        )

        return CharacterResponse(**character)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create character: {str(e)}")


@app.post("/character/save", response_model=CharacterSaveResponse)
async def save_character(request: CharacterSaveRequest):
    """
    Save a character profile to ChromaDB storage.

    This endpoint persists a character profile (typically created via /character/create)
    to ChromaDB for later retrieval and use in roleplay scenarios.
    """
    try:
        character_id = character_storage.save_character(request.character)
        return CharacterSaveResponse(
            character_id=character_id,
            message=f"Character '{request.character.get('name')}' saved successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save character: {str(e)}")


@app.get("/character/{character_id}")
async def get_character(character_id: str):
    """
    Retrieve a character profile by ID from ChromaDB.
    """
    try:
        character = character_storage.get_character(character_id)
        if not character:
            raise HTTPException(status_code=404, detail=f"Character not found: {character_id}")
        return character
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve character: {str(e)}")


@app.get("/character/list/all", response_model=CharacterListResponse)
async def list_characters(limit: int = 100):
    """
    List all saved characters from ChromaDB.
    """
    try:
        characters = character_storage.list_characters(limit=limit)
        return CharacterListResponse(
            characters=characters,
            total_count=len(characters)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list characters: {str(e)}")


@app.delete("/character/{character_id}")
async def delete_character(character_id: str):
    """
    Delete a character profile from ChromaDB.
    """
    try:
        success = character_storage.delete_character(character_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Character not found: {character_id}")
        return {"message": f"Character {character_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete character: {str(e)}")


# ============================================================================
# Roleplay Chat Endpoints
# ============================================================================

@app.post("/roleplay/chat", response_model=RoleplayChatResponse)
async def roleplay_chat(request: RoleplayChatRequest):
    """
    Chat with a character in roleplay mode (non-streaming).

    This endpoint:
    1. Retrieves the character from ChromaDB
    2. Formats the roleplay prompt with character data and conversation history
    3. Aggregates with system roleplay prompt
    4. Sends to LLM and returns response
    5. Saves the conversation turn
    """
    try:
        # Get character from storage
        character = character_storage.get_character(request.character_id)
        if not character:
            raise HTTPException(status_code=404, detail=f"Character not found: {request.character_id}")

        # Generate or use existing session ID
        session_id = request.session_id or f"roleplay_{uuid.uuid4()}"

        # Chat with character
        response_data = await roleplay_manager.chat(
            character=character,
            message=request.message,
            session_id=session_id,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False
        )

        return RoleplayChatResponse(
            response=response_data["response"],
            session_id=response_data["session_id"],
            character_name=response_data["character_name"],
            tokens_used=response_data.get("tokens_used", {})
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ROLEPLAY ERROR] Chat failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Roleplay chat failed: {str(e)}")


@app.post("/roleplay/chat/stream")
async def roleplay_chat_stream(request: RoleplayChatRequest):
    """
    Chat with a character in roleplay mode with streaming response.

    This endpoint:
    1. Retrieves the character from ChromaDB
    2. Formats the roleplay prompt with character data and conversation history
    3. Aggregates with system roleplay prompt
    4. Streams LLM response in real-time (SSE format)
    5. Saves the conversation turn after streaming completes
    """
    print(f"📨 Received roleplay streaming chat request for character: {request.character_id}")

    try:
        # Get character from storage
        character = character_storage.get_character(request.character_id)
        if not character:
            raise HTTPException(status_code=404, detail=f"Character not found: {request.character_id}")

        # Generate or use existing session ID
        session_id = request.session_id or f"roleplay_{uuid.uuid4()}"

        # Get stream from roleplay manager
        response_data = await roleplay_manager.chat(
            character=character,
            message=request.message,
            session_id=session_id,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True
        )

        async def generate():
            try:
                accumulated_chunks: List[str] = []

                # Stream content from OpenAI chunks in SSE format
                async for chunk in response_data["stream"]:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        accumulated_chunks.append(content)
                        yield f"data: {content}\n\n"

                # Save conversation after streaming completes
                final_response = "".join(accumulated_chunks).strip()
                if final_response:
                    roleplay_manager.save_turn_external(
                        session_id=session_id,
                        user_message=request.message,
                        assistant_message=final_response,
                        character_name=character.get("name", "Character")
                    )
                    print(f"[ROLEPLAY] Saved streaming conversation turn for session: {session_id}")

            except Exception as e:
                import traceback
                error_msg = f"Stream generation error: {str(e)}"
                print(error_msg)
                print(traceback.format_exc())
                error_data = f"data: {json.dumps({'error': str(e)})}\n\n"
                yield error_data

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Roleplay chat stream error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/roleplay/history/{session_id}")
async def get_roleplay_history(session_id: str, limit: Optional[int] = None):
    """
    Get conversation history for a roleplay session.
    """
    try:
        history = roleplay_manager.get_conversation_history(session_id, limit)
        return {
            "session_id": session_id,
            "history": history,
            "turn_count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@app.delete("/roleplay/history/{session_id}")
async def clear_roleplay_history(session_id: str):
    """
    Clear conversation history for a roleplay session.
    """
    try:
        success = roleplay_manager.clear_conversation(session_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return {"message": f"Cleared history for session: {session_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear history: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description='RAG Chatbot API')
    parser.add_argument('--port', type=int, default=8001, help='Port to run the server on (default: 8001)')
    parser.add_argument('--host', type=str, default="0.0.0.0", help='Host to run the server on (default: 0.0.0.0)')
    args = parser.parse_args()

    print(f"🌐 Starting server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
