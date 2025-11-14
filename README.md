# RAG Chatbot Pipeline

A general-purpose RAG (Retrieval-Augmented Generation) chatbot with configurable system prompts, user management, and conversation history tracking.

## Overview

This RAG pipeline demonstrates a flexible architecture that allows you to:
- **Switch between different system prompts** to create different chatbot personalities
- **Manage users without authentication** (demo-friendly)
- **Track conversation history per user** (with optional Firebase integration)
- **Store and retrieve documents** for knowledge-based responses

## Key Features

### 1. Configurable System Prompts

The chatbot supports multiple system prompts that can be switched based on your use case:

- **Generic** (`generic`): A general-purpose AI assistant for Q&A and knowledge retrieval
- **Roleplay** (`roleplay`): An NPC character that engages in interactive storytelling
- **Custom**: Add your own system prompts by creating new files in `prompts/system/`

**Usage Example:**
```python
# In your chat request
layer_config = {
    "system": {
        "id": "roleplay",  # or "generic"
        "variables": {
            "currentDateTime": datetime.now().isoformat()
        }
    }
}
```

### 2. User Management (Firebase - Optional)

Track users and their interactions without requiring authentication:

- Create user profiles with ID, name, and age
- Update user information
- Query user profiles and statistics

**API Endpoints:**
- `POST /users` - Create a new user
- `GET /users/{user_id}` - Get user profile
- `PUT /users/{user_id}` - Update user information

### 3. Conversation History (Firebase - Optional)

Store and retrieve conversation history per user:

- Automatically save conversations via chat endpoints
- Retrieve conversation history by user ID or session
- Delete conversation history

**API Endpoints:**
- `POST /conversations` - Save a conversation turn
- `POST /conversations/list` - List user conversations
- `POST /conversations/delete` - Delete conversation history

### 4. RAG Pipeline

Standard RAG functionality:
- Document upload and processing
- Vector search with configurable relevance thresholds
- Context engineering for optimal prompt construction
- Streaming and non-streaming chat responses

## Architecture

```
rag_pipeline/
├── main.py                      # FastAPI application with all endpoints
├── rag_pipeline.py              # Core RAG orchestration
├── config.py                    # Configuration management
├── schemas.py                   # Pydantic models for API
├── services/                    # Service layer
│   ├── firebase_service.py      # Firebase integration (user & history)
│   ├── chat_service.py          # LLM chat generation
│   ├── document_processor.py    # Document chunking & embeddings
│   ├── vector_store_service.py  # Vector search operations
│   └── context_engineer.py      # Context optimization
├── prompts/                     # Prompt management
│   ├── prompt_manager.py        # Prompt layer composition
│   └── system/                  # System prompt variants
│       ├── houmy.py            # Generic system prompt
│       └── roleplay.py         # Roleplay system prompt
└── databases.py                 # Vector store backends (Chroma/Supabase)
```

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file:

```bash
# Required
OPENAI_API_KEY=sk-...

# Database (choose one)
TEST_WITH_CHROMADB=true          # For local development
# OR
SUPABASE_DB_URL=postgresql://... # For production

# Firebase (optional - for user management)
USE_FIREBASE=false                # Set to true when ready
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_PATH=path/to/credentials.json
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
```

### 3. Run the Server

```bash
python main.py --port 8001
```

Visit `http://localhost:8001/docs` for the interactive API documentation.

## Usage Examples

### Chat with Different System Prompts

**Generic Assistant:**
```bash
curl -X POST "http://localhost:8001/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is machine learning?",
    "language": "English",
    "domain": "books",
    "source_ids": [],
    "layer_config": {
      "system": {"id": "generic"}
    }
  }'
```

**Roleplay Character:**
```bash
curl -X POST "http://localhost:8001/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, who are you?",
    "language": "English",
    "domain": "books",
    "source_ids": [],
    "layer_config": {
      "system": {"id": "roleplay"}
    }
  }'
```

### User Management

**Create a User:**
```bash
curl -X POST "http://localhost:8001/users" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "name": "Alice",
    "age": 25
  }'
```

**Get User Profile:**
```bash
curl "http://localhost:8001/users/user123"
```

### Conversation History

**List User Conversations:**
```bash
curl -X POST "http://localhost:8001/conversations/list" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "limit": 10
  }'
```

## Firebase Setup (Optional)

To enable user management and conversation history with Firebase:

1. **Create a Firebase Project**
   - Go to [Firebase Console](https://console.firebase.google.com/)
   - Create a new project
   - Enable Firestore Database

2. **Download Service Account Credentials**
   - Go to Project Settings → Service Accounts
   - Click "Generate New Private Key"
   - Save the JSON file to your project

3. **Configure Environment Variables**
   ```bash
   USE_FIREBASE=true
   FIREBASE_PROJECT_ID=your-project-id
   FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
   FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
   ```

4. **Uncomment Firebase Code**
   - Edit `services/firebase_service.py`
   - Uncomment the Firebase initialization and method implementations
   - Install: `pip install firebase-admin`

5. **Firestore Structure**
   ```
   users/{user_id}
     - user_id: string
     - name: string
     - age: number
     - created_at: timestamp
     - updated_at: timestamp

   conversations/{user_id}/messages/{message_id}
     - user_id: string
     - session_id: string
     - user_message: string
     - assistant_message: string
     - metadata: object
     - timestamp: timestamp
   ```

## Adding Custom System Prompts

1. Create a new file in `prompts/system/`, e.g., `prompts/system/customer_support.py`:

```python
SYSTEM_CUSTOMER_SUPPORT_PROMPT = """
You are a friendly customer support assistant.

The current date is {currentDateTime}.

You help customers with their questions and issues in a professional,
empathetic, and solution-oriented manner.
"""
```

2. Update `prompts/system/__init__.py`:

```python
from .customer_support import SYSTEM_CUSTOMER_SUPPORT_PROMPT

DICT_SYSTEM_PROMPTS = {
    "generic": SYSTEM_GENERIC_PROMPT,
    "roleplay": SYSTEM_ROLEPLAY_PROMPT,
    "customer_support": SYSTEM_CUSTOMER_SUPPORT_PROMPT,  # Add this
}
```

3. Use it in your chat requests:

```python
layer_config = {
    "system": {
        "id": "customer_support",
        "variables": {"currentDateTime": datetime.now().isoformat()}
    }
}
```

## API Endpoints

### Chat
- `POST /chat` - Chat with the assistant
- `POST /chat/stream` - Streaming chat response

### Users (Firebase)
- `POST /users` - Create user
- `GET /users/{user_id}` - Get user profile
- `PUT /users/{user_id}` - Update user

### Conversations (Firebase)
- `POST /conversations` - Save conversation
- `POST /conversations/list` - List conversations
- `POST /conversations/delete` - Delete conversations

### Sources
- `GET /sources` - List available sources
- `POST /sources` - Upload new source
- `POST /sources/{source_id}/process` - Process source
- `POST /search` - Search documents

### System
- `GET /health` - Health check
- `GET /firebase/status` - Firebase status
- `GET /domains/status` - Domain status

## Configuration Options

See `config.py` for all available settings:

- **LLM Models**: Configure GPT models for chat and streaming
- **Embeddings**: Set embedding model and dimensions
- **Vector Store**: Choose between ChromaDB (local) or Supabase (cloud)
- **Firebase**: Enable/disable user management
- **RAG Parameters**: Chunk size, overlap, relevance thresholds

## Vector Store Architecture

The `RAGPipeline` supports two vector store backends:

### Supabase (Production)
- Uses PostgreSQL with pgvector extension
- Persistent, cloud-hosted vector database
- Configure via `SUPABASE_DB_URL` environment variable
- Default when `TEST_WITH_CHROMADB=false`

### ChromaDB (Local Development)
- Lightweight, embedded vector database
- Useful for testing and development
- Enable with `TEST_WITH_CHROMADB=true`
- Persists to `./chroma_db` directory

## Development

### Running Tests
```bash
pytest testcode/
```

### Code Structure
- **Services**: Business logic isolated in service layer
- **Schemas**: Pydantic models for type safety
- **Dependency Injection**: Easy to test and swap implementations
- **Prompt Management**: Layered prompt composition system

## Migration from Houmy

This codebase was originally built for Houmy, a maternity care chatbot. It has been refactored to be a general-purpose RAG pipeline. Key changes:

- **System prompts**: Generalized from Houmy-specific to configurable prompts
- **Branding**: Removed Houmy-specific terminology
- **Collection names**: Changed from `houmy_sources` to `rag_sources`
- **Firebase integration**: Added for user management and conversation history
- **Flexibility**: Designed to support multiple use cases via prompt configuration

## License

MIT

## Contributing

Contributions welcome! This is a demo project showcasing RAG architecture with flexible prompt management and user tracking.
