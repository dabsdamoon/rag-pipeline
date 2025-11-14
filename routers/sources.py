"""
Sources Router - Source management, upload, and search
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, Dict, List
from pathlib import Path
from supabase import Client, create_client
from storage3.utils import StorageException
import os
import uuid
import shutil
import asyncio
import json

from databases import get_db
from models import Sources, SourceMetadata, ProcessingStatus
from schemas import (
    UploadRawSourcesRequest,
    UploadRawSourcesResponse,
    UploadRawSourcesItem,
    SourceMetadataListResponse,
    SourceMetadataResponse,
    SourceUploadResponse,
    SourceProcessResponse,
    ProcessingStatusEnum,
    SourceResponse,
    SearchRequest,
    SearchResponse,
    SearchResult
)

router = APIRouter(prefix="/sources", tags=["Sources"])

# Upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Dependencies will be injected by main.py
rag_pipeline = None


def set_rag_pipeline(pipeline):
    """Set the RAG pipeline instance"""
    global rag_pipeline
    rag_pipeline = pipeline


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


async def process_source_async(source_id: str, db: Session):
    """Process source in background"""
    try:
        success = rag_pipeline.process_source(source_id)

        # Update source status
        source = db.query(Sources).filter(Sources.source_id == source_id).first()
        if source:
            source.processing_status = ProcessingStatus.COMPLETED if success else ProcessingStatus.FAILED
            db.commit()

    except Exception as e:
        # Update source status to failed
        source = db.query(Sources).filter(Sources.source_id == source_id).first()
        if source:
            source.processing_status = ProcessingStatus.FAILED
            db.commit()


@router.post("/upload_raw", response_model=UploadRawSourcesResponse)
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


@router.get("/", response_model=SourceMetadataListResponse)
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


@router.post("/", response_model=SourceUploadResponse)
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
    source = Sources(
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


@router.post("/{source_id}/process", response_model=SourceProcessResponse)
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


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(source_id: str, db: Session = Depends(get_db)):
    """Get source details"""
    source = db.query(Sources).filter(Sources.source_id == source_id).first()
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


@router.delete("/{source_id}")
def delete_source(source_id: str, db: Session = Depends(get_db)):
    """Delete a source"""
    source = db.query(Sources).filter(Sources.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Delete file if exists
    if source.file_path and os.path.exists(source.file_path):
        os.remove(source.file_path)

    # Delete from database
    db.delete(source)
    db.commit()

    return {"message": "Source deleted successfully"}


@router.post("/search", response_model=SearchResponse)
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


@router.get("/domains/status")
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
