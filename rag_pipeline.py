"""Refactored RAG Pipeline with dependency injection and service layer."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import openai
from langchain_openai import OpenAIEmbeddings
from tqdm import tqdm

from config import get_settings
from exceptions import SourceNotFoundError, DocumentProcessingError
from services import DocumentProcessor, VectorStoreService, ChatService
from metadata_utils import get_source_metadata_map, seed_metadata_from_json, load_source_text
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

        self.chat_service = ChatService(
            openai_client=self.openai_client,
            prompt_manager=self.prompt_manager,
            source_metadata=self.source_metadata,
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
        self.source_metadata = get_source_metadata_map()
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
        if source_id not in self.source_metadata:
            raise SourceNotFoundError(source_id)

        filepath = self.source_metadata[source_id]["filepath_raw"]
        return load_source_text(filepath)

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
        if source_id not in self.source_metadata:
            raise SourceNotFoundError(source_id)

        try:
            # Get text content
            text_content = self.get_text_content(source_id)
            if not text_content:
                return False

            # Chunk text
            chunks = self.doc_processor.chunk_text(text_content)

            # Generate embeddings
            print(f"Processing {len(chunks)} chunks for source {source_id}...")
            embeddings = []
            for chunk in tqdm(chunks, desc="Generating embeddings"):
                embedding = self.doc_processor.generate_single_embedding(chunk)
                embeddings.append(embedding)

            # Store in vector store
            self.vector_store_service.store_document_chunks(
                source_id=source_id,
                chunks=chunks,
                embeddings=embeddings,
            )

            return True

        except (SourceNotFoundError, DocumentProcessingError):
            raise
        except Exception as e:
            print(f"Error processing source {source_id}: {e}")
            return False

    def process_sources(self, source_ids: List[str], max_workers: int = 4) -> bool:
        """Process multiple sources with multi-threading."""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.process_source, source_id) for source_id in source_ids]
            return all(future.result() for future in futures)

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

                relevant_docs = self.search_documents(
                    message,
                    limit=10,
                    source_ids=source_ids,
                    min_relevance_score=relevance_threshold,
                    query_embedding=query_embedding,
                )
                print(f"[RAG DEBUG] Found {len(relevant_docs)} relevant docs")

            # Generate response
            print(f"[RAG DEBUG] Calling generate_response with {len(relevant_docs)} docs")

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
