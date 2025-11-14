"""
Example usage of SourceController for flexible source uploads.

This demonstrates the improved flexibility for uploading documents.
"""

from modules.rag_pipeline import RAGPipeline


def example_basic_upload():
    """Example: Upload raw text directly."""
    pipeline = RAGPipeline(test_with_chromadb=True)

    # Upload raw text without needing a file or metadata entry
    success = pipeline.upload_text(
        source_id="TEST001",
        text="This is my test document content. It talks about pregnancy and childbirth.",
    )

    print(f"Upload success: {success}")


def example_custom_chunking():
    """Example: Upload with custom chunk settings."""
    pipeline = RAGPipeline(test_with_chromadb=True)

    # Override chunking parameters per upload
    success = pipeline.upload_text(
        source_id="TEST002",
        text="Long document content here...",
        chunk_size=1000,  # Custom chunk size
        chunk_overlap=200,  # Custom overlap
    )

    print(f"Upload with custom chunking: {success}")


def example_file_upload():
    """Example: Upload directly from file path."""
    pipeline = RAGPipeline(test_with_chromadb=True)

    # Upload from file without needing metadata entry
    success = pipeline.upload_file(
        source_id="TEST003",
        filepath="path/to/your/document.txt",
    )

    print(f"File upload success: {success}")


def example_batch_upload():
    """Example: Upload multiple sources in parallel."""
    pipeline = RAGPipeline(test_with_chromadb=True)

    # Batch upload with mixed sources (text and files)
    results = pipeline.upload_batch([
        {
            "source_id": "TEST001",
            "text": "First test document content.",
        },
        {
            "source_id": "TEST002",
            "text": "Second test document content.",
            "chunk_size": 800,  # Per-source custom settings
        },
        {
            "source_id": "TEST003",
            "filepath": "path/to/document.txt",
        },
    ], max_workers=4)

    print(f"Batch upload results: {results}")
    # Output: {"TEST001": True, "TEST002": True, "TEST003": False}


def example_list_sources():
    """Example: List and filter sources."""
    pipeline = RAGPipeline(test_with_chromadb=True)

    # List all sources
    all_sources = pipeline.source_controller.list_sources()
    print(f"Total sources: {len(all_sources)}")

    # Filter by type
    books = pipeline.source_controller.list_sources(source_type="book")
    print(f"Books: {len(books)}")

    # Filter by name pattern
    pregnancy_sources = pipeline.source_controller.list_sources(name_pattern="pregnancy")
    print(f"Pregnancy-related: {len(pregnancy_sources)}")


def example_direct_controller_usage():
    """Example: Use SourceController directly for more control."""
    pipeline = RAGPipeline(test_with_chromadb=True)
    controller = pipeline.source_controller

    # Validate source exists
    if controller.validate_source("BOOK001"):
        # Get source info
        info = controller.get_source_info("BOOK001")
        print(f"Source info: {info}")

        # Process with custom settings
        success = controller.process_source(
            source_id="BOOK001",
            chunk_size=600,
            verbose=True,
        )
        print(f"Processing: {success}")


if __name__ == "__main__":
    print("=== Source Controller Usage Examples ===\n")

    # Run examples
    print("\n1. Basic text upload:")
    example_basic_upload()

    print("\n2. Custom chunking:")
    example_custom_chunking()

    print("\n3. Batch upload:")
    example_batch_upload()

    print("\n4. List sources:")
    example_list_sources()

    print("\n5. Direct controller usage:")
    example_direct_controller_usage()
