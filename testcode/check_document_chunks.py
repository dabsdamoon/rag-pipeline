"""Inspect rows in the Supabase document_chunks table."""

from __future__ import annotations

import os
import sys
from typing import Optional

from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "ERROR: psycopg2-binary must be installed to query Supabase; run pip install psycopg2-binary"
    ) from exc


def fetch_chunks(conn_str: str, limit: Optional[int]) -> None:
    sql = "SELECT source_id, chunk_index, embedding, left(content, 120) AS excerpt FROM public.document_chunks ORDER BY source_id, chunk_index"
    if limit is not None:
        sql += " LIMIT %s"
        params = (limit,)
    else:
        params = None

    with psycopg2.connect(conn_str) as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    if not rows:
        print("No rows found in public.document_chunks")
        return

    for row in rows:
        print(
            f"source_id={row['source_id']} chunk_index={row['chunk_index']} excerpt={row['excerpt']}"
        )


def main() -> None:
    load_dotenv(".env")
    conn_str = os.getenv("SUPABASE_DB_URL")
    if not conn_str:
        raise SystemExit("ERROR: SUPABASE_DB_URL environment variable missing; run aborted.")

    limit_env = os.getenv("CHUNKS_INSPECT_LIMIT")
    limit = int(limit_env) if limit_env else None

    fetch_chunks(conn_str, limit)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        sys.exit(1)
