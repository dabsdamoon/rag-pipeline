"""Seed Supabase source_metadata table from assets/dict_source_id.json."""

from __future__ import annotations
from dotenv import load_dotenv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import psycopg
except ModuleNotFoundError:
    psycopg = None

if psycopg is None:
    try:
        import psycopg2
    except ModuleNotFoundError as exc:  # pragma: no cover - install guard
        raise SystemExit(
            "Install psycopg (pip install psycopg[binary]) or psycopg2-binary before running this script."
        ) from exc

load_dotenv(".env")

def _connect(dsn: str):
    if psycopg is not None:
        return psycopg.connect(dsn, autocommit=False)
    return psycopg2.connect(dsn)


def load_metadata(json_path: Path) -> List[Tuple[str, str, str, str, str]]:
    payload: Dict[str, Dict[str, Any]] = json.loads(json_path.read_text())
    rows: List[Tuple[str, str, str, str, str]] = []
    for source_id, info in payload.items():
        rows.append(
            (
                source_id,
                info["name"],
                info["display_name"],
                info["type"],
                info.get("purchase_link", ""),
            )
        )
    return rows


def main() -> None:
    if "SUPABASE_DB_URL" not in os.environ:
        raise SystemExit("ERROR: SUPABASE_DB_URL environment variable missing; run aborted.")

    json_path = Path(os.environ.get("SOURCE_METADATA_PATH", "assets/dict_source_id.json"))
    if not json_path.exists():
        raise SystemExit(f"ERROR: Metadata JSON not found at {json_path}; run aborted.")

    rows = load_metadata(json_path)
    if not rows:
        raise SystemExit("ERROR: No metadata rows found in source JSON; run aborted.")

    upsert_sql = """
        insert into public.source_metadata (source_id, name, display_name, source_type, purchase_link)
        values (%s, %s, %s, %s, %s)
        on conflict (source_id) do update set
            name = excluded.name,
            display_name = excluded.display_name,
            source_type = excluded.source_type,
            purchase_link = excluded.purchase_link;
    """

    conn = _connect(os.environ["SUPABASE_DB_URL"])
    try:
        with conn.cursor() as cur:
            cur.executemany(upsert_sql, rows)
        conn.commit()
        print(f"Upserted {len(rows)} source metadata rows into Supabase.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
