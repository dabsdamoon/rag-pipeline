"""Query Supabase document chunks directly using pgvector similarity.

This helper connects to the Supabase Postgres instance, generates an embedding
for the provided query using OpenAI, and issues a cosine-similarity search
against the `public.document_chunks` table. It is intended for manual
verification that data ingested via `process_source` is available in
Supabase/pgvector.

Environment variables:
    SUPABASE_DB_URL         Postgres connection string with direct access.
    OPENAI_API_KEY          API key for embedding generation.
    SUPABASE_TEST_QUERY     Query text (default: "무통 분만이란?").
    SUPABASE_TEST_LIMIT     Number of chunks to return (default: 5).
    SUPABASE_TEST_SOURCE_IDS Comma-separated list of source_ids to filter.
"""

from __future__ import annotations

import os
import sys
from contextlib import closing, contextmanager
from typing import Iterable, List, Sequence

import psycopg2
from psycopg2.extras import DictCursor

from dotenv import load_dotenv
from modules.rag_pipeline import RAGPipeline


def load_env_list(name: str) -> List[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def format_vector_literal(values: Sequence[float]) -> str:
    """Convert an embedding to pgvector literal syntax."""
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


@contextmanager
def temporary_chroma_dir() -> Iterable[None]:
    """Point Chroma persistence at a temp directory while the pipeline is initialised."""
    import tempfile

    original = os.environ.get("CHROMA_PERSIST_DIRECTORY")
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["CHROMA_PERSIST_DIRECTORY"] = tmpdir
        try:
            yield
        finally:
            if original is not None:
                os.environ["CHROMA_PERSIST_DIRECTORY"] = original
            else:
                os.environ.pop("CHROMA_PERSIST_DIRECTORY", None)


def query_supabase(
    conn_str: str,
    vector_literal: str,
    limit: int,
    source_ids: Iterable[str] | None,
):
    filter_clause = ""
    params: List[object] = [vector_literal]

    if source_ids:
        filter_clause = " AND source_id = ANY(%s)"
        params.append(list(source_ids))

    params.extend((vector_literal, limit))

    sql = f"""
        SELECT
            source_id,
            chunk_index,
            content,
            1 - (embedding <=> %s::vector) AS similarity
        FROM public.document_chunks
        WHERE 1=1{filter_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """

    with closing(psycopg2.connect(conn_str)) as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def main() -> None:
    load_dotenv(".env")

    conn_str = os.getenv("SUPABASE_DB_URL")
    if not conn_str:
        print("SUPABASE_DB_URL is required", file=sys.stderr)
        sys.exit(1)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is required", file=sys.stderr)
        sys.exit(1)

    query = os.getenv("SUPABASE_TEST_QUERY", "무통 분만이란?")
    limit = int(os.getenv("SUPABASE_TEST_LIMIT", "5"))
    source_ids = load_env_list("SUPABASE_TEST_SOURCE_IDS")

    with temporary_chroma_dir():
        pipeline = RAGPipeline()
        print(f"Generating embedding for query via RAG pipeline: {query}")
        embedding = pipeline.embeddings.embed_query(query)
    vector_literal = format_vector_literal(embedding)

    print("Running similarity search against Supabase...")
    rows = query_supabase(conn_str, vector_literal, limit, source_ids or None)

    if not rows:
        print("No rows returned.")
        return

    for idx, row in enumerate(rows, start=1):
        print("-" * 80)
        print(f"Rank #{idx}")
        print(f"Source ID : {row['source_id']}")
        print(f"Chunk     : {row['chunk_index']}")
        print(f"Similarity: {row['similarity']:.4f}")
        excerpt = row['content'][:200].replace("\n", " ")
        print(f"Excerpt   : {excerpt}...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Cancelled by user", file=sys.stderr)
