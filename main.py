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
from models import Sources, ProcessingStatus, SourceMetadata
from schemas import *
from rag_pipeline import RAGPipeline
from prompts.prompt_manager import PromptManager
from supabase import Client, create_client
from storage3.utils import StorageException
import asyncio
import json


load_dotenv(".env")

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
    print("🚀 Starting Houmy RAG Chatbot API")
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
    title="Houmy RAG Chatbot API",
    description="A RAG-based chatbot API containing knowledge of Houm identity",
    version="1.0.0",
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

# Create upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Static files not needed - using React frontend


@app.get("/")
async def root():
    """Redirect to React app"""
    # Get current server info from request
    return JSONResponse({
        "message": "Houmy RAG Chatbot API",
        "docs": "/docs"
    })

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to the chatbot"""
    try:
        response_data = rag_pipeline.chat(
            message=request.message,
            language=request.language,
            session_id=request.session_id,
            user_id=request.user_id,
            source_ids=request.source_ids,
            domain=request.domain,
            min_relevance_score=request.min_relevance_score,
            layer_config=request.layer_config,
        )

        if request.user_id and response_data.get("response"):
            try:
                rag_pipeline.record_turn_history(
                    user_id=request.user_id,
                    session_id=response_data.get("session_id"),
                    user_message=request.message,
                    assistant_message=response_data["response"],
                )
            except Exception as exc:
                print(f"[API WARNING] Failed to persist chat history: {exc}")
        
        return ChatResponse(**response_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Send a message to the chatbot with streaming response"""
    print(f"📨 Received streaming chat request: message='{request.message[:50]}...', domain={request.domain}, source_ids={request.source_ids}")
    try:
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
                    layer_config=request.layer_config,
                )
                session_id = response_data.get("session_id")
                
                # Stream content from OpenAI chunks in SSE format
                for chunk in response_data["stream"]:
                    # Extract content from chunk (similar to how Node.js would parse OpenAI response)
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        accumulated_chunks.append(content)
                        yield f"data: {content}\n\n"

                if request.user_id:
                    final_response = "".join(accumulated_chunks).strip()
                    if final_response:
                        try:
                            rag_pipeline.record_turn_history(
                                user_id=request.user_id,
                                session_id=session_id,
                                user_message=request.message,
                                assistant_message=final_response,
                            )
                        except Exception as exc:
                            print(f"[API WARNING] Failed to persist streaming chat history: {exc}")
                
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
        version="1.0.0",
        database_status=database_status,
        llm_service_status=llm_status
    )

if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description='Houmy RAG Chatbot API')
    parser.add_argument('--port', type=int, default=8001, help='Port to run the server on (default: 8001)')
    parser.add_argument('--host', type=str, default="0.0.0.0", help='Host to run the server on (default: 0.0.0.0)')
    args = parser.parse_args()

    print(f"🌐 Starting server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
