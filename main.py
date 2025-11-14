from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from exceptions import RAGPipelineError
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

from databases import create_tables
from metadata_utils import get_source_metadata_map, seed_metadata_from_json

# Import routers
from routers import auth, chat, sources, characters, roleplay, users, history, prompts

load_dotenv(".env")


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


# ============================================================================
# Lifespan & Application Setup
# ============================================================================

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


# ============================================================================
# Initialize Services
# ============================================================================

from services.factory import ServiceFactory

# Initialize all services using the factory
services = ServiceFactory.initialize_services()

# Extract individual service instances for convenience
rag_pipeline = services["rag_pipeline"]
prompt_manager_instance = services["prompt_manager"]
firebase_service_instance = services["firebase_service"]
character_pipeline_instance = services["character_creation_pipeline"]
character_storage_instance = services["character_storage_service"]
roleplay_manager_instance = services["roleplay_manager"]


# ============================================================================
# Inject Dependencies into Routers
# ============================================================================

chat.set_rag_pipeline(rag_pipeline)
sources.set_rag_pipeline(rag_pipeline)
characters.set_character_services(character_pipeline_instance, character_storage_instance)
roleplay.set_roleplay_services(character_storage_instance, roleplay_manager_instance)
users.set_firebase_service(firebase_service_instance)
history.set_firebase_service(firebase_service_instance)
prompts.set_prompt_manager(prompt_manager_instance)


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(sources.router)
app.include_router(characters.router)
app.include_router(roleplay.router)
app.include_router(users.router)
app.include_router(history.router)
app.include_router(prompts.router)


# ============================================================================
# Root & Health Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API root endpoint"""
    return JSONResponse({
        "message": "RAG Chatbot API - A general-purpose RAG pipeline with configurable system prompts",
        "version": "2.0.0",
        "docs": "/docs"
    })


@app.get("/health")
def health_check():
    """Health check"""
    # Check database connection
    from databases import get_db
    try:
        db = next(get_db())
        db.execute("SELECT 1")
        database_status = "connected"
    except:
        database_status = "disconnected"

    # Check OpenAI API
    llm_status = "available" if os.getenv("OPENAI_API_KEY") else "not_configured"

    return {
        "status": "healthy",
        "version": "2.0.0",
        "database_status": database_status,
        "llm_service_status": llm_status
    }


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description='RAG Chatbot API')
    parser.add_argument('--port', type=int, default=8001, help='Port to run the server on (default: 8001)')
    parser.add_argument('--host', type=str, default="0.0.0.0", help='Host to run the server on (default: 0.0.0.0)')
    args = parser.parse_args()

    print(f"🌐 Starting server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
