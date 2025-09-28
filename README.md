# Houmy RAG Chatbot

Houmy is a RAG (Retrieval-Augmented Generation) chatbot containing knowledge of Houm identity, built with FastAPI and React.

## Purpose

Houmy provides intelligent chat responses by combining knowledge from curated books with advanced language models. The system uses vector embeddings to find relevant context and generates responses in multiple languages.

## Features

- **RAG-based Architecture**: Retrieval-Augmented Generation for accurate, context-aware responses
- **Multi-language Support**: English, Korean, Japanese, Chinese, Spanish, French, German, Portuguese
- **Real-time Streaming**: Server-sent events for streaming chat responses
- **Book Selection**: Filter responses by specific books
- **Vector Search**: Supabase pgvector for production retrieval (local ChromaDB option for tests)
- **Prompt Management**: Modular prompt system with dynamic language support
- **RESTful API**: FastAPI with comprehensive endpoint documentation
- **React Frontend**: Modern UI with real-time chat interface

---

## Vector Store Architecture

The `RAGPipeline` now treats Supabase (Postgres + pgvector) as the canonical
vector store while keeping ChromaDB available for isolated local tests.

- **Production / default**: Provide `SUPABASE_DB_URL` and instantiate
  `RAGPipeline()` without flags. Document chunks are embedded and written to
  `public.document_chunks`, and semantic search issues SQL similarity queries
  against pgvector.
- **Local testing**: Instantiate with `test_with_chromadb=True` to bypass
  Supabase and use the embedded Chroma client. This keeps the previous behavior
  for unit tests that run entirely offline.
- **Why the change?** The pipeline now delegates persistence/querying to a
  pluggable backend (Supabase or Chroma). This strategy-based design cleanly
  separates embedding, storage, and retrieval so production traffic goes
  through Supabase while tests can opt into the lightweight Chroma path.
- **Endpoint updates**: `POST /sources/{source_id}/process` calls
  `RAGPipeline.process_source`, which clears existing chunks for the source and
  re-ingests them into the selected backend. The `/search` endpoint reads from
  the same backend, so CLI scripts and Cloud Run requests observe identical
  results.

See `rag_pipeline.py` for the implementation and the new backend adapters, and
`testcode/test_supabase_similarity.py` for an example that exercises the
Supabase path.

---

## Database Structure

### Current Architecture

The system uses a **dual-database architecture**:

1. **SQLite Database (`houmy.db`)**: Metadata and chat history
2. **ChromaDB (`chroma_db/`)**: Vector embeddings for semantic search

### SQLite Tables

#### 1. `book_metadata` (Primary Books Table)
```sql
CREATE TABLE book_metadata (
    book_id VARCHAR NOT NULL PRIMARY KEY,    -- e.g., "BOOK001"
    name VARCHAR NOT NULL,                   -- e.g., "childbirth_without_fear"
    display_name VARCHAR NOT NULL,           -- e.g., "두려움없는출산"
    filepath_raw VARCHAR NOT NULL,           -- PDF file path
    purchase_link VARCHAR NOT NULL,          -- Purchase URL
    created_at DATETIME,
    updated_at DATETIME
);
```

#### 2. `books` (Upload Management Table)
```sql
CREATE TABLE books (
    id VARCHAR NOT NULL PRIMARY KEY,         -- UUID
    title VARCHAR NOT NULL,
    author VARCHAR,
    description TEXT,
    page_count INTEGER,
    file_size INTEGER,
    content_type VARCHAR,
    processing_status VARCHAR(10),           -- 'processing', 'completed', 'failed'
    upload_date DATETIME,
    file_path VARCHAR
);
```

#### 3. `chat_sessions`
```sql
CREATE TABLE chat_sessions (
    id VARCHAR NOT NULL PRIMARY KEY,         -- Session UUID
    created_at DATETIME,
    last_activity DATETIME
);
```

#### 4. `chat_messages`
```sql
CREATE TABLE chat_messages (
    id INTEGER NOT NULL PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    message TEXT NOT NULL,                   -- User message
    response TEXT NOT NULL,                  -- Bot response
    sources_used TEXT,                       -- JSON string of sources
    tokens_used TEXT,                        -- OpenAI tokens consumed (JSON)
    timestamp DATETIME
);
```

### ChromaDB Structure

#### Collection: `houmy_books`
- **Vector Model**: OpenAI `text-embedding-3-large` (1536 dimensions)
- **Distance Metric**: Cosine similarity
- **Chunk Size**: 500 characters
- **Chunk Overlap**: 100 characters

#### Document Metadata Schema
```json
{
    "book_id": "BOOK001",
    "page_number": 15,
    "content": "Text chunk content...",
    "chunk_id": "BOOK001_123"
}
```

---

## Migration Guide for Supabase/Firebase

### For Supabase Migration

#### 1. Database Schema Migration
```sql
-- Enable RLS (Row Level Security)
ALTER TABLE book_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE books ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Create indexes for performance
CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_timestamp ON chat_messages(timestamp);
CREATE INDEX idx_book_metadata_book_id ON book_metadata(book_id);

-- Create RLS policies (example for public access)
CREATE POLICY "Allow public read access" ON book_metadata FOR SELECT TO public USING (true);
CREATE POLICY "Allow public read access" ON chat_messages FOR SELECT TO public USING (true);
```

#### 2. Vector Database Options
**Option A: Use Supabase pgvector**
```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create embeddings table
CREATE TABLE book_embeddings (
    id BIGSERIAL PRIMARY KEY,
    book_id VARCHAR NOT NULL,
    page_number INTEGER,
    content TEXT,
    chunk_id VARCHAR UNIQUE,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create vector similarity search index
CREATE INDEX ON book_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**Option B: Keep ChromaDB separately**
- Deploy ChromaDB on separate service (Railway, Render, etc.)
- Update connection strings in environment variables

#### 3. Environment Variables Update
```env
DATABASE_URL=postgresql://user:pass@db.xxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
CHROMA_PERSIST_DIRECTORY=./chroma_db  # or remote ChromaDB URL
```

### For Firebase Migration

#### 1. Firestore Collections Structure
```javascript
// Collection: bookMetadata
{
  bookId: "BOOK001",
  name: "childbirth_without_fear",
  displayName: "두려움없는출산",
  filepathRaw: "gs://bucket/path/to/file.pdf",
  purchaseLink: "https://...",
  createdAt: Timestamp,
  updatedAt: Timestamp
}

// Collection: chatSessions
{
  sessionId: "uuid",
  createdAt: Timestamp,
  lastActivity: Timestamp,
  messages: [  // subcollection
    {
      messageId: "auto-id",
      message: "user message",
      response: "bot response",
      sourcesUsed: [],
      tokensUsed: 150,
      timestamp: Timestamp
    }
  ]
}
```

#### 2. Vector Database Integration
- Use **Pinecone** or **Weaviate** as vector database
- Store embeddings with metadata pointing to Firestore documents
- Update RAG pipeline to query external vector DB

#### 3. Firebase Configuration
```javascript
// firebase-config.js
import { initializeApp } from 'firebase/app';
import { getFirestore } from 'firebase/firestore';

const firebaseConfig = {
  // Your config
};

const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);
```

---

## Environment Variables

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-...
GOOGLE_CLOUD_PROJECT=your-project-id

# Database Configuration
DATABASE_URL=sqlite:///./houmy.db  # Replace with Supabase/Firebase URL
CHROMA_PERSIST_DIRECTORY=./chroma_db

# API Configuration
CORS_ORIGINS=http://localhost:3001,http://localhost:5173
API_HOST=0.0.0.0
API_PORT=8001
```

## Setup Instructions

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   cd frontend && npm install
   ```

2. **Set Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Initialize Database**
   ```bash
   python -c "from databases import create_tables; create_tables()"
   ```

4. **Start Services**
   ```bash
   # Backend
   python main.py

   # Frontend
   cd frontend && npm start
   ```

## API Endpoints

- `GET /books` - List available books
- `POST /chat` - Send chat message
- `POST /chat/stream` - Send chat message with streaming
- `POST /search` - Search documents
- `GET /health` - Health check

See API documentation at `http://localhost:8001/docs` when running.

## Chat Stream Endpoint Callstack

The `/chat/stream` endpoint (main.py:102-145) provides real-time streaming responses using Server-Sent Events (SSE). Here's the complete callstack:

### Request Flow
1. **FastAPI Endpoint** (`main.py:102`) - `chat_stream(request: ChatRequest)`
2. **RAG Pipeline Entry** (`rag_pipeline.py:406`) - `chat()` method
3. **Document Search** (`rag_pipeline.py:197`) - `search_documents()` (for books domain)
4. **Response Generation** (`rag_pipeline.py:240`) - `generate_response()` with `stream=True`
5. **Streaming Handler** (`rag_pipeline.py:371`) - `_generate_streaming_response()`
6. **OpenAI Streaming** - `openai_client.chat.completions.create(stream=True)`

### Key Components

#### 1. FastAPI Stream Handler (main.py:106-130)
```python
def generate():
    response_data = rag_pipeline.chat(stream=True, ...)
    for chunk in response_data["stream"]:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            yield f"data: {content}\n\n"
```

#### 2. RAG Pipeline Chat (rag_pipeline.py:406-478)
- Handles domain routing (books vs insurance)
- Performs document search for relevant context
- Delegates to `generate_response()` with streaming enabled

#### 3. Streaming Response Generator (rag_pipeline.py:371-403)
- Creates OpenAI streaming request with `stream=True`
- Returns raw OpenAI stream with metadata
- Handles error propagation

### Stream Format
- **Protocol**: Server-Sent Events (SSE)
- **Content-Type**: `text/event-stream`
- **Format**: `data: {content}\n\n` for each chunk
- **Error Handling**: JSON error objects in SSE format

### Performance Characteristics
- **No buffering**: `X-Accel-Buffering: no` header
- **Real-time**: Direct chunk forwarding from OpenAI
- **Error resilient**: Exceptions captured and streamed as data
