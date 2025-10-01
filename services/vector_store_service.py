"""Vector store service for RAG pipeline."""

from typing import List, Dict, Any, Optional

from databases import VectorStoreBackend, ChunkRecord
from exceptions import VectorStoreError, SearchError, StorageError


class VectorStoreService:
    """Wrapper service for vector store operations."""

    def __init__(self, vector_store: VectorStoreBackend):
        """
        Initialize vector store service.

        Args:
            vector_store: Vector store backend instance
        """
        self.vector_store = vector_store

    def store_document_chunks(
        self,
        source_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
    ) -> None:
        """
        Store document chunks with embeddings.

        Args:
            source_id: Source identifier
            chunks: List of text chunks
            embeddings: List of embedding vectors

        Raises:
            StorageError: If storage fails
        """
        try:
            if len(chunks) != len(embeddings):
                raise ValueError(
                    f"Chunk count ({len(chunks)}) doesn't match embedding count ({len(embeddings)})"
                )

            chunk_records: List[ChunkRecord] = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_records.append({
                    "chunk_id": f"{source_id}_{i}",
                    "chunk_index": i,
                    "content": chunk,
                    "embedding": embedding,
                    "token_count": len(chunk.split()),
                })

            self.vector_store.store_chunks(source_id, chunk_records)

        except Exception as e:
            raise StorageError(
                f"Failed to store chunks for source {source_id}",
                details={
                    "source_id": source_id,
                    "num_chunks": len(chunks),
                    "error": str(e)
                }
            ) from e

    def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        source_ids: Optional[List[str]] = None,
        min_relevance: float = 0.05,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            query_embedding: Query embedding vector
            limit: Maximum number of results
            source_ids: Filter by source IDs
            min_relevance: Minimum relevance threshold

        Returns:
            List of search results

        Raises:
            SearchError: If search fails
        """
        try:
            results = self.vector_store.query(
                query_embedding=query_embedding,
                limit=limit,
                source_ids=source_ids,
                min_relevance=min_relevance,
            )

            return results

        except Exception as e:
            raise SearchError(
                "Vector search failed",
                details={
                    "limit": limit,
                    "source_ids": source_ids,
                    "min_relevance": min_relevance,
                    "error": str(e)
                }
            ) from e

    def delete_source(self, source_id: str) -> None:
        """
        Delete all chunks for a source.

        Args:
            source_id: Source identifier

        Raises:
            StorageError: If deletion fails
        """
        try:
            # Store empty chunks to trigger deletion
            self.vector_store.store_chunks(source_id, [])
        except Exception as e:
            raise StorageError(
                f"Failed to delete source {source_id}",
                details={"source_id": source_id, "error": str(e)}
            ) from e
