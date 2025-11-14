# SourceController Implementation

## Overview

The `SourceController` class centralizes all source-related operations, providing better separation of concerns, improved testability, and greater flexibility for document uploads.

## Architecture Benefits

### Before (Monolithic)
```
RAGPipeline
├── Source metadata management
├── Source text loading
├── Source processing
├── Document search
├── Chat orchestration
└── History management
```

### After (Separated Concerns)
```
RAGPipeline
├── SourceController (delegated)
│   ├── Metadata operations
│   ├── Content loading
│   ├── Processing operations
│   └── Validation
├── Document search
├── Chat orchestration
└── History management
```

## Key Features

### 1. Flexible Upload Methods

#### Direct Text Upload
```python
pipeline = RAGPipeline(test_with_chromadb=True)

# No file or metadata entry needed
pipeline.upload_text(
    source_id="TEST001",
    text="Your document content here...",
)
```

#### File Upload
```python
# Upload from file without metadata registration
pipeline.upload_file(
    source_id="TEST002",
    filepath="path/to/document.txt",
)
```

#### Batch Upload
```python
# Upload multiple sources in parallel
results = pipeline.upload_batch([
    {"source_id": "TEST001", "text": "Content 1"},
    {"source_id": "TEST002", "filepath": "path/to/file.txt"},
    {"source_id": "TEST003", "text": "Content 3", "chunk_size": 800},
], max_workers=4)

# Returns: {"TEST001": True, "TEST002": True, "TEST003": True}
```

### 2. Per-Upload Custom Settings

Override chunking parameters for individual uploads:

```python
pipeline.upload_text(
    source_id="CUSTOM",
    text="Long document...",
    chunk_size=1000,      # Override default
    chunk_overlap=200,    # Override default
)
```

### 3. Source Discovery and Validation

```python
controller = pipeline.source_controller

# List all sources
all_sources = controller.list_sources()

# Filter by type
books = controller.list_sources(source_type="book")

# Search by name
pregnancy_docs = controller.list_sources(name_pattern="pregnancy")

# Validate existence
if controller.validate_source("BOOK001"):
    info = controller.get_source_info("BOOK001")
```

### 4. Direct Controller Access

For advanced use cases, access the controller directly:

```python
controller = pipeline.source_controller

# Process with full control
success = controller.process_source(
    source_id="BOOK001",
    chunk_size=600,
    chunk_overlap=150,
    verbose=True,
)

# Load text from arbitrary file
text = controller.load_from_file("any/path/file.txt")
```

## API Reference

### SourceController Methods

#### Metadata Operations
- `refresh_metadata()` - Reload metadata from database
- `get_source_info(source_id)` - Get metadata for a source
- `list_sources(source_type, name_pattern)` - List and filter sources
- `validate_source(source_id)` - Check if source exists

#### Content Loading
- `get_text_content(source_id)` - Load content by source ID
- `load_from_file(filepath)` - Load content from file path

#### Processing Operations
- `process_source(source_id, **options)` - Process a registered source
- `process_sources(source_ids, max_workers)` - Batch process registered sources
- `upload_text(source_id, text, **options)` - Upload raw text
- `upload_file(source_id, filepath, **options)` - Upload from file
- `upload_batch(sources, max_workers)` - Batch upload mixed sources

### RAGPipeline Delegation

All source operations are delegated to `SourceController`:

```python
# These methods internally call SourceController
pipeline.process_source(source_id)
pipeline.process_sources(source_ids)
pipeline.upload_text(source_id, text)
pipeline.upload_file(source_id, filepath)
pipeline.upload_batch(sources)
pipeline.get_text_content(source_id)
pipeline.refresh_source_metadata()
```

## Usage Examples

### Quick Testing with ChromaDB

```python
from rag_pipeline import RAGPipeline

# Initialize with local ChromaDB
pipeline = RAGPipeline(test_with_chromadb=True)

# Upload test documents
pipeline.upload_text("TEST001", "Test document about pregnancy...")
pipeline.upload_text("TEST002", "Another test document...")

# Search immediately
results = pipeline.search_documents("pregnancy tips", limit=5)
```

### Production Upload to Supabase

```python
from rag_pipeline import RAGPipeline

# Initialize with Supabase
pipeline = RAGPipeline(test_with_chromadb=False)

# Batch upload production documents
sources = [
    {"source_id": "BOOK001", "filepath": "books/childbirth.txt"},
    {"source_id": "BOOK002", "filepath": "books/pregnancy.txt"},
    {"source_id": "BOOK003", "filepath": "books/nutrition.txt"},
]

results = pipeline.upload_batch(sources, max_workers=4)
print(f"Upload results: {results}")
```

### Custom Processing Pipeline

```python
from rag_pipeline import RAGPipeline

pipeline = RAGPipeline(test_with_chromadb=True)
controller = pipeline.source_controller

# List available sources
sources = controller.list_sources(source_type="book")

# Process each with different settings based on content length
for source in sources:
    source_id = source["source_id"]
    text = controller.get_text_content(source_id)

    # Adjust chunking based on content length
    if len(text) > 50000:
        chunk_size = 1000
        chunk_overlap = 200
    else:
        chunk_size = 500
        chunk_overlap = 100

    controller.process_source(
        source_id=source_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
```

## Testing

The `SourceController` can be tested in isolation:

```python
from source_controller import SourceController
from services import DocumentProcessor, VectorStoreService

# Mock dependencies
mock_processor = MockDocumentProcessor()
mock_vector_store = MockVectorStoreService()

# Test controller independently
controller = SourceController(
    doc_processor=mock_processor,
    vector_store_service=mock_vector_store,
)

# Test upload
success = controller.upload_text("TEST", "content")
assert success == True
```

## Migration Guide

### Old Code
```python
pipeline = RAGPipeline()

# Could only process registered sources
pipeline.process_source("BOOK001")
```

### New Code
```python
pipeline = RAGPipeline()

# Still works (backwards compatible)
pipeline.process_source("BOOK001")

# Now also supports:
pipeline.upload_text("TEST", "raw text content")
pipeline.upload_file("TEST", "path/to/file.txt")
pipeline.upload_batch([...])
```

## Design Principles

1. **Single Responsibility** - SourceController only handles sources
2. **Dependency Injection** - Receives dependencies via constructor
3. **Composition over Inheritance** - RAGPipeline composes SourceController
4. **Backward Compatibility** - Existing code continues to work
5. **Testability** - Can be tested independently with mocks
6. **Flexibility** - Supports multiple upload patterns and custom settings

## Future Enhancements

Potential additions to `SourceController`:

- `upload_from_url(source_id, url)` - Fetch and upload from web
- `upload_pdf(source_id, pdf_path)` - Direct PDF support
- `upload_from_s3(source_id, s3_path)` - Cloud storage integration
- `register_source(source_id, metadata)` - Programmatic metadata registration
- `delete_source(source_id)` - Remove source and its embeddings
- `update_source(source_id, text)` - Re-process existing source
