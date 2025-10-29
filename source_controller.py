"""Source Controller for managing all source-related operations."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from tqdm import tqdm

from exceptions import SourceNotFoundError, DocumentProcessingError
from metadata_utils import get_source_metadata_map, seed_metadata_from_json, load_source_text
from services import DocumentProcessor, VectorStoreService


class SourceController:
    """
    Handles all source-related operations including metadata, loading, and processing.

    Separates source management concerns from RAG orchestration logic.
    """

    def __init__(
        self,
        doc_processor: DocumentProcessor,
        vector_store_service: VectorStoreService,
        metadata_path: Optional[str] = None,
    ):
        """
        Initialize SourceController.

        Args:
            doc_processor: Document processor for chunking and embeddings
            vector_store_service: Vector store service for persistence
            metadata_path: Path to source metadata JSON file
        """
        self.doc_processor = doc_processor
        self.vector_store_service = vector_store_service
        self.metadata_path = metadata_path
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Dict[str, str]]:
        """Load source metadata from database, seeding from JSON if needed."""
        metadata = get_source_metadata_map()

        # Seed from JSON if metadata is empty and path is provided
        if not metadata and self.metadata_path:
            seeded = seed_metadata_from_json(self.metadata_path)
            if seeded:
                metadata = get_source_metadata_map()

        return metadata

    def refresh_metadata(self) -> None:
        """Reload source metadata from the database."""
        self.metadata = get_source_metadata_map()

    def get_source_info(self, source_id: str) -> Dict[str, str]:
        """
        Get metadata for a specific source.

        Args:
            source_id: Source identifier

        Returns:
            Source metadata dictionary

        Raises:
            SourceNotFoundError: If source not found
        """
        if source_id not in self.metadata:
            raise SourceNotFoundError(source_id)
        return self.metadata[source_id]

    def list_sources(
        self,
        source_type: Optional[str] = None,
        name_pattern: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List sources with optional filtering.

        Args:
            source_type: Filter by source type (e.g., "book", "insurance")
            name_pattern: Filter by name pattern (case-insensitive substring match)

        Returns:
            List of source dictionaries with source_id included
        """
        results = []
        for source_id, info in self.metadata.items():
            # Apply filters
            if source_type and info.get("source_type") != source_type:
                continue
            if name_pattern and name_pattern.lower() not in info.get("name", "").lower():
                continue

            results.append({
                "source_id": source_id,
                **info,
            })

        return results

    def validate_source(self, source_id: str) -> bool:
        """
        Check if a source exists in metadata.

        Args:
            source_id: Source identifier

        Returns:
            True if source exists, False otherwise
        """
        return source_id in self.metadata

    def get_text_content(self, source_id: str) -> str:
        """
        Get text content from a source.

        Args:
            source_id: Source identifier

        Returns:
            Text content

        Raises:
            SourceNotFoundError: If source not found
        """
        if source_id not in self.metadata:
            raise SourceNotFoundError(source_id)

        filepath = self.metadata[source_id]["filepath_raw"]
        return load_source_text(filepath)

    def load_from_file(self, filepath: str) -> str:
        """
        Load text content directly from a file path.

        Args:
            filepath: Path to text file

        Returns:
            Text content
        """
        return load_source_text(filepath)

    def process_source(
        self,
        source_id: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        verbose: bool = True,
    ) -> bool:
        """
        Process a source file and store embeddings.

        Args:
            source_id: Source identifier
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            verbose: Show progress output

        Returns:
            True if successful

        Raises:
            SourceNotFoundError: If source not found
            DocumentProcessingError: If processing fails
        """
        if source_id not in self.metadata:
            raise SourceNotFoundError(source_id)

        try:
            # Get text content
            text_content = self.get_text_content(source_id)
            if not text_content:
                return False

            # Process with custom or default settings
            return self._process_text(
                source_id=source_id,
                text=text_content,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                verbose=verbose,
            )

        except (SourceNotFoundError, DocumentProcessingError):
            raise
        except Exception as e:
            if verbose:
                print(f"Error processing source {source_id}: {e}")
            return False

    def upload_text(
        self,
        source_id: str,
        text: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        auto_register: bool = False,
        metadata: Optional[Dict[str, str]] = None,
        verbose: bool = True,
    ) -> bool:
        """
        Upload raw text directly without requiring file or metadata entry.

        Args:
            source_id: Source identifier
            text: Raw text content
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            auto_register: Automatically register in metadata if missing
            metadata: Metadata to register (required if auto_register=True and source not exists)
            verbose: Show progress output

        Returns:
            True if successful
        """
        # Check if source exists
        if source_id not in self.metadata:
            if auto_register and metadata:
                # Could implement auto-registration here
                if verbose:
                    print(f"Warning: Source {source_id} not in metadata. Processing anyway (not registered).")
            elif not auto_register:
                if verbose:
                    print(f"Warning: Source {source_id} not in metadata. Processing anyway.")

        return self._process_text(
            source_id=source_id,
            text=text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            verbose=verbose,
        )

    def upload_file(
        self,
        source_id: str,
        filepath: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        verbose: bool = True,
    ) -> bool:
        """
        Upload from file path directly.

        Args:
            source_id: Source identifier
            filepath: Path to file
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            verbose: Show progress output

        Returns:
            True if successful
        """
        try:
            text = self.load_from_file(filepath)
            return self.upload_text(
                source_id=source_id,
                text=text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                verbose=verbose,
            )
        except Exception as e:
            if verbose:
                print(f"Error uploading file {filepath}: {e}")
            return False

    def upload_batch(
        self,
        sources: List[Dict[str, Any]],
        max_workers: int = 4,
        verbose: bool = True,
    ) -> Dict[str, bool]:
        """
        Upload multiple sources in parallel.

        Args:
            sources: List of source dicts with keys: source_id, text (or filepath)
            max_workers: Number of parallel workers
            verbose: Show progress output

        Returns:
            Dictionary mapping source_id to success status

        Example:
            results = controller.upload_batch([
                {"source_id": "TEST001", "text": "Content 1"},
                {"source_id": "TEST002", "filepath": "path/to/file.txt"},
            ])
        """
        results = {}

        def process_item(item: Dict[str, Any]) -> tuple[str, bool]:
            source_id = item["source_id"]
            chunk_size = item.get("chunk_size")
            chunk_overlap = item.get("chunk_overlap")

            if "text" in item:
                success = self.upload_text(
                    source_id=source_id,
                    text=item["text"],
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    verbose=False,
                )
            elif "filepath" in item:
                success = self.upload_file(
                    source_id=source_id,
                    filepath=item["filepath"],
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    verbose=False,
                )
            else:
                if verbose:
                    print(f"Error: Source {source_id} missing 'text' or 'filepath'")
                return source_id, False

            return source_id, success

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_item, item) for item in sources]

            iterator = tqdm(futures, desc="Uploading sources") if verbose else futures

            for future in iterator:
                source_id, success = future.result()
                results[source_id] = success
                if verbose and not success:
                    print(f"  Failed: {source_id}")

        if verbose:
            succeeded = sum(1 for v in results.values() if v)
            failed = len(results) - succeeded
            print(f"\nBatch upload complete: {succeeded} succeeded, {failed} failed")

        return results

    def process_sources(
        self,
        source_ids: List[str],
        max_workers: int = 4,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        verbose: bool = True,
    ) -> Dict[str, bool]:
        """
        Process multiple sources with multi-threading.

        Args:
            source_ids: List of source identifiers
            max_workers: Number of parallel workers
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            verbose: Show progress output

        Returns:
            Dictionary mapping source_id to success status
        """
        results = {}

        def process_single(source_id: str) -> tuple[str, bool]:
            try:
                success = self.process_source(
                    source_id=source_id,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    verbose=False,
                )
                return source_id, success
            except Exception as e:
                if verbose:
                    print(f"Error processing {source_id}: {e}")
                return source_id, False

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_single, sid) for sid in source_ids]

            iterator = tqdm(futures, desc="Processing sources") if verbose else futures

            for future in iterator:
                source_id, success = future.result()
                results[source_id] = success

        if verbose:
            succeeded = sum(1 for v in results.values() if v)
            failed = len(results) - succeeded
            print(f"\nProcessing complete: {succeeded} succeeded, {failed} failed")

        return results

    def _process_text(
        self,
        source_id: str,
        text: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        verbose: bool = True,
    ) -> bool:
        """
        Internal method to process text into chunks and embeddings.

        Args:
            source_id: Source identifier
            text: Text content
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            verbose: Show progress output

        Returns:
            True if successful
        """
        # Temporarily override chunk settings if provided
        original_chunk_size = self.doc_processor.chunk_size
        original_chunk_overlap = self.doc_processor.chunk_overlap

        try:
            if chunk_size is not None:
                self.doc_processor.chunk_size = chunk_size
            if chunk_overlap is not None:
                self.doc_processor.chunk_overlap = chunk_overlap

            # Chunk text
            chunks = self.doc_processor.chunk_text(text)

            if verbose:
                print(f"Processing {len(chunks)} chunks for source {source_id}...")

            # Generate embeddings
            embeddings = []
            iterator = tqdm(chunks, desc="Generating embeddings") if verbose else chunks

            for chunk in iterator:
                embedding = self.doc_processor.generate_single_embedding(chunk)
                embeddings.append(embedding)

            # Store in vector store
            self.vector_store_service.store_document_chunks(
                source_id=source_id,
                chunks=chunks,
                embeddings=embeddings,
            )

            if verbose:
                print(f"Successfully stored {len(chunks)} chunks for {source_id}")

            return True

        finally:
            # Restore original settings
            self.doc_processor.chunk_size = original_chunk_size
            self.doc_processor.chunk_overlap = original_chunk_overlap
