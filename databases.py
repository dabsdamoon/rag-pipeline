"""Vector store backends for the Houmy RAG pipeline."""

from __future__ import annotations

from dotenv import load_dotenv
import os
import uuid
from typing import Any, Dict, Iterator, List, Optional

try:  # Optional dependency for local testing
    import chromadb
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    chromadb = None

try:  # Optional dependency for Supabase mode
    import psycopg2
    from psycopg2.extras import DictCursor, execute_values
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    psycopg2 = None
    DictCursor = None
    execute_values = None

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base

# Load dotenv
load_dotenv(".env")

# Determine database URL priority: explicit DSN > computed from Supabase project
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")

if SUPABASE_DB_URL:
    DATABASE_URL = SUPABASE_DB_URL
elif SUPABASE_URL and SUPABASE_PASSWORD:
    # Extract database details from Supabase URL (format: https://projectref.supabase.co)
    import re

    match = re.search(r"https://([^.]+)\.supabase\.co", SUPABASE_URL)
    if not match:
        raise SystemExit(
            "ERROR: SUPABASE_URL is not in the expected format 'https://<ref>.supabase.co'."
        )
    project_ref = match.group(1)
    DATABASE_URL = (
        f"postgresql://postgres:{SUPABASE_PASSWORD}@db.{project_ref}.supabase.co:5432/postgres"
    )
else:
    raise SystemExit(
        "ERROR: Provide SUPABASE_DB_URL or both SUPABASE_URL and SUPABASE_DB_PASSWORD to use the Supabase backend."
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables() -> None:
    """Create ORM tables if they do not yet exist."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """Yield a database session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


ChunkRecord = Dict[str, Any]
HistoryRecord = Dict[str, Any]


class VectorStoreBackend:
    """Minimal interface for persistence/search backends."""

    def store_chunks(self, source_id: str, chunks: List[ChunkRecord]) -> None:
        raise NotImplementedError

    def query(
        self,
        query_embedding: List[float],
        limit: int,
        source_ids: Optional[List[str]],
        min_relevance: float,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError


class HistoryStoreBackend:
    """Interface for storing and retrieving conversation history."""

    def store_turn(
        self,
        *,
        user_id: str,
        session_id: Optional[str],
        summary: str,
        embedding: List[float],
        turn_timestamp,
    ) -> None:
        raise NotImplementedError

    def query_history(
        self,
        *,
        query_embedding: List[float],
        limit: int,
        user_id: Optional[str],
        min_relevance: float,
    ) -> List[HistoryRecord]:
        raise NotImplementedError

    def delete_user_history(self, *, user_id: str) -> None:
        raise NotImplementedError


class ChromaVectorStore(VectorStoreBackend):
    """Vector store backed by local ChromaDB persistence."""

    def __init__(self, collection_name: str, persist_directory: str) -> None:
        if chromadb is None:
            raise RuntimeError("chromadb is required when test_with_chromadb=True")
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def store_chunks(self, source_id: str, chunks: List[ChunkRecord]) -> None:
        if not chunks:
            return

        try:
            # Remove previously indexed chunks for this source to avoid duplicates.
            self.collection.delete(where={"source_id": source_id})
        except Exception:
            # Ignore delete errors (collection may be empty).
            pass

        ids = [chunk["chunk_id"] for chunk in chunks]
        embeddings = [chunk["embedding"] for chunk in chunks]
        documents = [chunk["content"] for chunk in chunks]
        metadatas = [
            {
                "source_id": source_id,
                "chunk_index": chunk["chunk_index"],
            }
            for chunk in chunks
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        query_embedding: List[float],
        limit: int,
        source_ids: Optional[List[str]],
        min_relevance: float,
    ) -> List[Dict[str, Any]]:
        where_clause: Dict[str, Any] = {}
        if source_ids:
            where_clause["source_id"] = {"$in": source_ids}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=max(limit * 2, limit),
            where=where_clause if where_clause else None,
        )

        matches: List[Dict[str, Any]] = []
        if not results.get("ids"):
            return matches

        for idx in range(len(results["ids"][0])):
            distance = results["distances"][0][idx]
            relevance = 1 - distance
            if relevance < min_relevance:
                continue

            matches.append(
                {
                    "source_id": results["metadatas"][0][idx]["source_id"],
                    "page_number": results["metadatas"][0][idx].get("chunk_index", 0),
                    "content": results["documents"][0][idx],
                    "relevance_score": round(relevance, 3),
                }
            )

        matches.sort(key=lambda item: item["relevance_score"], reverse=True)
        return matches[:limit]


class ChromaHistoryStore(HistoryStoreBackend):
    """History store backed by a dedicated ChromaDB collection."""

    def __init__(self, collection_name: str, persist_directory: str) -> None:
        if chromadb is None:
            raise RuntimeError("chromadb is required when test_with_chromadb=True")
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def store_turn(
        self,
        *,
        user_id: str,
        session_id: Optional[str],
        summary: str,
        embedding: List[float],
        turn_timestamp,
    ) -> None:
        turn_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "session_id": session_id,
            "turn_timestamp": turn_timestamp.isoformat() if hasattr(turn_timestamp, "isoformat") else str(turn_timestamp),
        }

        self.collection.add(
            ids=[turn_id],
            embeddings=[embedding],
            documents=[summary],
            metadatas=[metadata],
        )

    def query_history(
        self,
        *,
        query_embedding: List[float],
        limit: int,
        user_id: Optional[str],
        min_relevance: float,
    ) -> List[HistoryRecord]:
        where_clause: Dict[str, Any] = {}
        if user_id:
            where_clause["user_id"] = user_id

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=max(limit * 2, limit),
            where=where_clause or None,
        )

        matches: List[HistoryRecord] = []
        if not results.get("ids"):
            return matches

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for idx, turn_id in enumerate(ids):
            distance = distances[idx]
            relevance = 1 - distance
            if relevance < min_relevance:
                continue

            metadata = metadatas[idx] or {}
            matches.append(
                {
                    "history_id": turn_id,
                    "user_id": metadata.get("user_id"),
                    "session_id": metadata.get("session_id"),
                    "summary": documents[idx],
                    "turn_timestamp": metadata.get("turn_timestamp"),
                    "relevance_score": round(relevance, 3),
                }
            )

        matches.sort(key=lambda item: item["relevance_score"], reverse=True)
        return matches[:limit]

    def delete_user_history(self, *, user_id: str) -> None:
        try:
            self.collection.delete(where={"user_id": user_id})
        except Exception as exc:
            print(f"[HISTORY WARNING] Failed to delete Chroma history for {user_id}: {exc}")


class SupabaseVectorStore(VectorStoreBackend):
    """Vector store backed by Supabase Postgres + pgvector."""

    def __init__(self, dsn: str, embedding_dimensions: int) -> None:
        if psycopg2 is None or execute_values is None or DictCursor is None:
            raise RuntimeError(
                "psycopg2-binary is required to use the Supabase vector store backend."
            )

        self.dsn = dsn
        self.embedding_dimensions = embedding_dimensions

    def _connect(self):
        return psycopg2.connect(self.dsn)

    @staticmethod
    def _format_vector(values: List[float]) -> str:
        return "[" + ",".join(f"{str(value)}" for value in values) + "]"

    def store_chunks(self, source_id: str, chunks: List[ChunkRecord]) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.document_chunks WHERE source_id = %s",
                    (source_id,),
                )

                if not chunks:
                    conn.commit()
                    return

                rows = [
                    (
                        str(uuid.uuid4()),
                        None,  # document_id (optional)
                        source_id,
                        chunk["chunk_index"],
                        chunk["content"],
                        self._format_vector(chunk["embedding"]),
                        chunk.get("token_count"),
                    )
                    for chunk in chunks
                ]

                execute_values(
                    cur,
                    """
                    INSERT INTO public.document_chunks
                    (id, document_id, source_id, chunk_index, content, embedding, token_count)
                    VALUES %s
                    """,
                    rows,
                    template="(%s, %s, %s, %s, %s, %s::vector, %s)",
                )

            conn.commit()
        finally:
            conn.close()

    def query(
        self,
        query_embedding: List[float],
        limit: int,
        source_ids: Optional[List[str]],
        min_relevance: float,
    ) -> List[Dict[str, Any]]:
        vector_literal = self._format_vector(query_embedding)

        filter_clause = ""
        params: List[Any] = [vector_literal]
        if source_ids:
            filter_clause = " AND source_id = ANY(%s)"
            params.append(list(source_ids))

        params.append(limit)

        sql = f"""
            SELECT
                source_id,
                chunk_index,
                content,
                1 - (embedding <=> %s::vector) AS similarity
            FROM public.document_chunks
            WHERE 1=1{filter_clause}
            ORDER BY similarity DESC
            LIMIT %s;
        """

        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        finally:
            conn.close()

        matches: List[Dict[str, Any]] = []
        for row in rows:
            similarity = float(row["similarity"])
            if similarity < min_relevance:
                continue

            matches.append(
                {
                    "source_id": row["source_id"],
                    "page_number": row["chunk_index"],
                    "content": row["content"],
                    "relevance_score": round(similarity, 3),
                }
            )

        return matches[:limit]


class SupabaseHistoryStore(HistoryStoreBackend):
    """History store backed by Supabase Postgres + pgvector."""

    def __init__(self, dsn: str) -> None:
        if psycopg2 is None or DictCursor is None:
            raise RuntimeError(
                "psycopg2-binary is required to use the Supabase history store backend."
            )
        self.dsn = dsn

    def _connect(self):
        return psycopg2.connect(self.dsn)

    @staticmethod
    def _format_vector(values: List[float]) -> str:
        return "[" + ",".join(f"{str(value)}" for value in values) + "]"

    def store_turn(
        self,
        *,
        user_id: str,
        session_id: Optional[str],
        summary: str,
        embedding: List[float],
        turn_timestamp,
    ) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.history (id, user_id, session_id, summary, embedding, turn_timestamp)
                    VALUES (%s, %s, %s, %s, %s::vector, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        session_id,
                        summary,
                        self._format_vector(embedding),
                        turn_timestamp,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def query_history(
        self,
        *,
        query_embedding: List[float],
        limit: int,
        user_id: Optional[str],
        min_relevance: float,
    ) -> List[HistoryRecord]:
        vector_literal = self._format_vector(query_embedding)

        filter_clause = ""
        params: List[Any] = [vector_literal]
        if user_id:
            filter_clause += " AND user_id = %s"
            params.append(user_id)

        params.append(limit)

        sql = f"""
            SELECT
                id,
                user_id,
                session_id,
                summary,
                turn_timestamp,
                1 - (embedding <=> %s::vector) AS similarity
            FROM public.history
            WHERE 1=1{filter_clause}
            ORDER BY similarity DESC
            LIMIT %s;
        """

        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        finally:
            conn.close()

        matches: List[HistoryRecord] = []
        for row in rows:
            similarity = float(row["similarity"])
            if similarity < min_relevance:
                continue

            matches.append(
                {
                    "history_id": row["id"],
                    "user_id": row["user_id"],
                    "session_id": row["session_id"],
                    "summary": row["summary"],
                    "turn_timestamp": row["turn_timestamp"],
                    "relevance_score": round(similarity, 3),
                }
            )

        return matches[:limit]

    def delete_user_history(self, *, user_id: str) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.history WHERE user_id = %s",
                    (user_id,),
                )
            conn.commit()
        finally:
            conn.close()
