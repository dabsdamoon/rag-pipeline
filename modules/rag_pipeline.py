"""Refactored RAG Pipeline with dependency injection and service layer."""

import time
from typing import Any, Dict, List, Optional

import openai
from langchain_openai import OpenAIEmbeddings

from config import get_settings
from services import DocumentProcessor, VectorStoreService, ChatService
from services.context_engineer import ContextEngineer
from source_controller import SourceController
from metadata_utils import get_source_metadata_map, seed_metadata_from_json
from databases import (
    ChromaHistoryStore,
    ChromaVectorStore,
    SupabaseHistoryStore,
    SupabaseVectorStore,
    VectorStoreBackend,
)
from history_manager import HistoryManager
from prompts.prompt_manager import PromptManager


class RAGPipeline:
    """
    Orchestrator for RAG pipeline operations.

    Coordinates between document processing, vector store, chat, and history services.
    """

    def __init__(
        self,
        # Dependency injection
        openai_client: Optional[openai.OpenAI] = None,
        embeddings: Optional[OpenAIEmbeddings] = None,
        vector_store: Optional[VectorStoreBackend] = None,
        prompt_manager: Optional[PromptManager] = None,
        history_manager: Optional[HistoryManager] = None,
        # Configuration
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        dict_source_id_path: str = "assets/dict_source_id.json",
        enable_timing: bool = False,
        collection_name: Optional[str] = None,
        history_collection_name: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_dimensions: Optional[int] = None,
        test_with_chromadb: Optional[bool] = None,
        supabase_dsn: Optional[str] = None,
    ):
        """
        Initialize RAG Pipeline with dependency injection.

        Args:
            openai_client: OpenAI client (optional, will create default)
            embeddings: OpenAI embeddings (optional, will create default)
            vector_store: Vector store backend (optional, will create default)
            prompt_manager: Prompt manager (optional, will create default)
            history_manager: History manager (optional, will create default)
            chunk_size: Text chunk size
            chunk_overlap: Chunk overlap size
            dict_source_id_path: Path to source metadata JSON
            enable_timing: Enable timing measurements
            collection_name: Vector store collection name
            history_collection_name: History collection name
            embedding_model: Embedding model name
            embedding_dimensions: Embedding dimensions
            test_with_chromadb: Use ChromaDB instead of Supabase
            supabase_dsn: Supabase database URL
        """
        # Load settings
        self.settings = get_settings()

        # Configuration with fallbacks to settings
        self.chunk_size = chunk_size or self.settings.chunk_size
        self.chunk_overlap = chunk_overlap or self.settings.chunk_overlap
        self.enable_timing = enable_timing
        self.collection_name = collection_name or self.settings.collection_name
        self.history_collection_name = history_collection_name or self.settings.history_collection_name
        self.embedding_model = embedding_model or self.settings.embedding_model
        self.embedding_dimensions = embedding_dimensions or self.settings.embedding_dimensions
        self.test_with_chromadb = test_with_chromadb if test_with_chromadb is not None else self.settings.test_with_chromadb
        self.supabase_dsn = supabase_dsn or self.settings.supabase_db_url
        self.dict_source_id_path = dict_source_id_path

        # Initialize or inject dependencies
        self.openai_client = openai_client or self._create_openai_client()
        self.embeddings = embeddings or self._create_embeddings()
        self.prompt_manager = prompt_manager or PromptManager()

        # Load source metadata
        self.source_metadata = get_source_metadata_map()

        if not self.source_metadata and self.dict_source_id_path:
            seeded = seed_metadata_from_json(self.dict_source_id_path)
            if seeded:
                self.source_metadata = get_source_metadata_map()

        if not self.source_metadata:
            raise RuntimeError(
                "Source metadata not found. Seed the SourceMetadata table before using RAGPipeline."
            )

        # Initialize vector store
        if vector_store:
            self.vector_store_backend = vector_store
        else:
            self.vector_store_backend = self._create_vector_store()

        # Initialize services
        self.doc_processor = DocumentProcessor(
            embeddings=self.embeddings,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        self.vector_store_service = VectorStoreService(
            vector_store=self.vector_store_backend
        )

        # Initialize source controller for all source-related operations
        self.source_controller = SourceController(
            doc_processor=self.doc_processor,
            vector_store_service=self.vector_store_service,
            metadata_path=self.dict_source_id_path,
        )

        self.chat_service = ChatService(
            openai_client=self.openai_client,
            prompt_manager=self.prompt_manager,
            source_metadata=self.source_metadata,
        )

        # Initialize context engineer for optimized context assembly
        self.context_engineer = ContextEngineer(
            max_context_tokens=3000,
            min_relevance_score=self.settings.min_relevance_threshold,
            enable_deduplication=True,
            enable_compression=True,
        )

        # Initialize history manager
        if history_manager:
            self.history_manager = history_manager
        else:
            self.history_manager = self._create_history_manager()

    def _create_openai_client(self) -> openai.OpenAI:
        """Create default OpenAI client."""
        return openai.OpenAI(api_key=self.settings.openai_api_key)

    def _create_embeddings(self) -> OpenAIEmbeddings:
        """Create default OpenAI embeddings."""
        return OpenAIEmbeddings(
            api_key=self.settings.openai_api_key,
            model=self.embedding_model,
            dimensions=self.embedding_dimensions
        )

    def _create_vector_store(self) -> VectorStoreBackend:
        """Create vector store based on configuration."""
        if self.test_with_chromadb:
            print("Using ChromaDB as vector store")
            chroma_dir = self.settings.chroma_persist_directory
            return ChromaVectorStore(self.collection_name, chroma_dir)
        else:
            print(f"Using Supabase as vector store with DSN: {self.supabase_dsn}")
            if not self.supabase_dsn:
                raise RuntimeError(
                    "SUPABASE_DB_URL must be set when test_with_chromadb is False."
                )
            return SupabaseVectorStore(self.supabase_dsn, self.embedding_dimensions)

    def _create_history_manager(self) -> Optional[HistoryManager]:
        """Create history manager based on configuration."""
        try:
            if self.test_with_chromadb:
                chroma_dir = self.settings.chroma_persist_directory
                history_store = ChromaHistoryStore(
                    self.history_collection_name,
                    chroma_dir
                )
            else:
                if not self.supabase_dsn:
                    return None
                history_store = SupabaseHistoryStore(self.supabase_dsn)

            return HistoryManager(
                embeddings=self.embeddings,
                openai_client=self.openai_client,
                history_store=history_store,
            )
        except Exception as exc:
            print(f"[RAG WARNING] Failed to initialize history manager: {exc}")
            return None

    def set_timing_enabled(self, enabled: bool):
        """Toggle timing functionality on/off."""
        self.enable_timing = enabled
        print(f"Timing {'enabled' if enabled else 'disabled'}")

    def is_timing_enabled(self) -> bool:
        """Check if timing is currently enabled."""
        return self.enable_timing

    def refresh_source_metadata(self) -> None:
        """Reload source metadata from the database."""
        self.source_controller.refresh_metadata()
        self.source_metadata = self.source_controller.metadata
        # Update chat service with new metadata
        self.chat_service.source_metadata = self.source_metadata

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
        return self.source_controller.get_text_content(source_id)

    def process_source(self, source_id: str) -> bool:
        """
        Process a source file and store embeddings.

        Args:
            source_id: Source identifier

        Returns:
            True if successful

        Raises:
            SourceNotFoundError: If source not found
            DocumentProcessingError: If processing fails
        """
        return self.source_controller.process_source(source_id)

    def process_sources(self, source_ids: List[str], max_workers: int = 4) -> Dict[str, bool]:
        """
        Process multiple sources with multi-threading.

        Args:
            source_ids: List of source identifiers
            max_workers: Number of parallel workers

        Returns:
            Dictionary mapping source_id to success status
        """
        return self.source_controller.process_sources(source_ids, max_workers=max_workers)

    def upload_text(
        self,
        source_id: str,
        text: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> bool:
        """
        Upload raw text directly without requiring file or metadata entry.

        Args:
            source_id: Source identifier
            text: Raw text content
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap

        Returns:
            True if successful
        """
        return self.source_controller.upload_text(
            source_id=source_id,
            text=text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def upload_file(
        self,
        source_id: str,
        filepath: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> bool:
        """
        Upload from file path directly.

        Args:
            source_id: Source identifier
            filepath: Path to file
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap

        Returns:
            True if successful
        """
        return self.source_controller.upload_file(
            source_id=source_id,
            filepath=filepath,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def upload_batch(
        self,
        sources: List[Dict[str, Any]],
        max_workers: int = 4,
    ) -> Dict[str, bool]:
        """
        Upload multiple sources in parallel.

        Args:
            sources: List of source dicts with keys: source_id, text (or filepath)
            max_workers: Number of parallel workers

        Returns:
            Dictionary mapping source_id to success status

        Example:
            results = pipeline.upload_batch([
                {"source_id": "TEST001", "text": "Content 1"},
                {"source_id": "TEST002", "filepath": "path/to/file.txt"},
            ])
        """
        return self.source_controller.upload_batch(sources, max_workers=max_workers)

    def search_documents(
        self,
        query: str,
        limit: int = 5,
        source_ids: Optional[List[str]] = None,
        min_relevance_score: float = 0.05,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict]:
        """
        Search for relevant documents using semantic similarity.

        Args:
            query: Query text
            limit: Maximum results
            source_ids: Filter by sources
            min_relevance_score: Minimum relevance threshold
            query_embedding: Pre-computed query embedding (optional)

        Returns:
            List of matching documents
        """
        try:
            start_total = time.perf_counter() if self.enable_timing else None

            # Get query embedding
            if query_embedding is None:
                query_embedding = self.doc_processor.generate_single_embedding(query)

            # Search vector store
            results = self.vector_store_service.search(
                query_embedding=query_embedding,
                limit=limit,
                source_ids=source_ids,
                min_relevance=min_relevance_score,
            )

            if self.enable_timing:
                elapsed = time.perf_counter() - start_total
                print(f"Search completed in {elapsed:.4f}s, found {len(results)} results")

            return results

        except Exception as e:
            print(f"Error searching documents: {e}")
            return []

    def chat(
        self,
        message: str,
        language: str = "English",
        source_ids: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        stream: bool = False,
        domain: Optional[str] = None,
        min_relevance_score: Optional[float] = None,
        max_tokens: Optional[int] = None,
        layer_config: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        Main chat interface combining search and generation.

        Args:
            message: User message
            language: Response language
            source_ids: Filter by sources
            session_id: Session identifier
            user_id: User identifier
            stream: Enable streaming
            domain: Domain context
            min_relevance_score: Minimum relevance threshold
            max_tokens: Maximum response tokens
            layer_config: Prompt layer configuration

        Returns:
            Response dictionary or streaming response
        """
        print(f"[RAG DEBUG] chat() called with domain={domain}, source_ids={source_ids}, message={message[:50]}...")

        try:
            query_embedding: Optional[List[float]] = None
            prompt_layers = layer_config

            # Get history context if available
            if self.history_manager and user_id:
                query_embedding, history_records, history_text = self.history_manager.prepare_history_context(
                    message=message,
                    user_id=user_id,
                )
                print(f"[RAG DEBUG] Retrieved {len(history_records)} history records for context")
                prompt_layers = self.history_manager.apply_history_layer(layer_config, history_text)

            if prompt_layers is None:
                prompt_layers = layer_config

            # Search documents
            if source_ids is None or len(source_ids) == 0:
                print(f"[RAG DEBUG] No sources selected - returning empty context")
                relevant_docs = []
            else:
                print(f"[RAG DEBUG] Searching documents with source_ids: {source_ids}")
                relevance_threshold = min_relevance_score if min_relevance_score is not None else self.settings.min_relevance_threshold

                raw_docs = self.search_documents(
                    message,
                    limit=10,
                    source_ids=source_ids,
                    min_relevance_score=relevance_threshold,
                    query_embedding=query_embedding,
                )
                print(f"[RAG DEBUG] Found {len(raw_docs)} raw docs from search")

                # Apply context engineering to optimize the raw results
                engineered_context = self.context_engineer.engineer_context(
                    query=message,
                    raw_documents=raw_docs,
                    query_type=None,  # Auto-detect
                    source_metadata=self.source_metadata,
                )
                relevant_docs = engineered_context["documents"]

                print(f"[RAG DEBUG] Context Engineering: {engineered_context['query_type']} query")
                print(f"[RAG DEBUG] Optimized to {len(relevant_docs)} docs ({engineered_context['context_stats']['estimated_tokens']} tokens)")

            # Generate response
            print(f"[RAG DEBUG] Calling generate_response with {len(relevant_docs)} engineered docs")

            if stream:
                response = self.chat_service.generate_streaming_response(
                    query=message,
                    context_docs=relevant_docs,
                    language=language,
                    domain=domain,
                    session_id=session_id,
                    max_tokens=max_tokens,
                    layer_config=prompt_layers,
                )
            else:
                response = self.chat_service.generate_response(
                    query=message,
                    context_docs=relevant_docs,
                    language=language,
                    domain=domain,
                    session_id=session_id,
                    max_tokens=max_tokens,
                    layer_config=prompt_layers,
                )

            return response

        except Exception as e:
            print(f"[RAG ERROR] Exception in chat(): {e}")
            import traceback
            traceback.print_exc()
            raise

    def record_turn_history(
        self,
        *,
        user_id: Optional[str],
        session_id: Optional[str],
        user_message: str,
        assistant_message: str,
    ) -> Optional[str]:
        """Proxy to HistoryManager for persisting chat turns."""
        if not self.history_manager:
            return None

        return self.history_manager.record_turn_history(
            user_id=user_id,
            session_id=session_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )

    def clear_user_history(self, user_id: str) -> None:
        """Clear history for a user."""
        if not self.history_manager:
            return
        self.history_manager.purge_user_history(user_id)
