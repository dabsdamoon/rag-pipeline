"""Helpers for loading and seeding source metadata."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy.orm import Session

from databases import SessionLocal, create_tables
from models import SourceMetadata

try:
    from supabase import Client, create_client
    from storage3.utils import StorageException
except ModuleNotFoundError:  # pragma: no cover - supabase optional during tests
    Client = None
    create_client = None
    StorageException = None

_SUPABASE_CLIENT: Optional[Client] = None
_SUPABASE_BUCKET_DEFAULT = os.getenv("SUPABASE_SOURCE_BUCKET", "source-raw")


def _serialize(record: SourceMetadata) -> Dict[str, str]:
    return {
        "name": record.name,
        "display_name": record.display_name,
        "source_type": record.source_type,
        "filepath_raw": record.filepath_raw,
        "purchase_link": record.purchase_link,
    }


def get_source_metadata_map(session: Optional[Session] = None) -> Dict[str, Dict[str, str]]:
    """Return metadata keyed by source_id, ensuring tables exist."""
    create_tables()
    local_session = session or SessionLocal()
    try:
        records = local_session.query(SourceMetadata).all()
        return {record.source_id: _serialize(record) for record in records}
    finally:
        if session is None:
            local_session.close()


def _ensure_supabase_client() -> Client:
    if create_client is None:
        raise RuntimeError(
            "supabase client library not installed. Install the 'supabase' package to download remote sources."
        )

    global _SUPABASE_CLIENT
    if _SUPABASE_CLIENT is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "Supabase credentials missing. Set SUPABASE_URL and SUPABASE_SERVICE_KEY to download remote sources."
            )
        _SUPABASE_CLIENT = create_client(url, key)
    return _SUPABASE_CLIENT


def _read_local_text(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _download_supabase_text(filepath: str) -> str:
    bucket = _SUPABASE_BUCKET_DEFAULT
    object_path = filepath

    if bucket and object_path.startswith(f"{bucket}/"):
        object_path = object_path[len(bucket) + 1 :]
    elif not bucket and "/" in filepath:
        bucket, object_path = filepath.split("/", 1)

    if not bucket:
        raise RuntimeError(
            "Unable to determine Supabase bucket for remote file. Set SUPABASE_SOURCE_BUCKET or include the bucket name in filepath_raw."
        )

    client = _ensure_supabase_client()
    storage = client.storage.from_(bucket)

    try:
        payload = storage.download(object_path)
    except StorageException as exc:
        if "/" in filepath:
            candidate_bucket, candidate_path = filepath.split("/", 1)
            if candidate_bucket != bucket:
                storage = client.storage.from_(candidate_bucket)
                payload = storage.download(candidate_path)
            else:
                raise RuntimeError(
                    f"Failed to download {object_path} from bucket {bucket}: {exc}"
                ) from exc
        else:
            raise RuntimeError(
                f"Failed to download {object_path} from bucket {bucket}: {exc}"
            ) from exc

    if isinstance(payload, bytes):
        return payload.decode("utf-8")
    if hasattr(payload, "decode"):
        return payload.decode("utf-8")
    return str(payload)


def load_source_text(filepath: str) -> str:
    """Load text content from local disk or Supabase Storage."""
    local_path = Path(filepath)
    text = _read_local_text(local_path)
    if text is not None:
        return text
    return _download_supabase_text(filepath)


def seed_metadata_from_json(json_path: str, session: Optional[Session] = None) -> int:
    """Insert missing metadata entries from a JSON file. Returns count inserted."""
    if not os.path.exists(json_path):
        return 0

    with open(json_path, "r") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):  # Defensive check
        raise ValueError("metadata JSON must be an object keyed by source_id")

    create_tables()
    local_session = session or SessionLocal()

    try:
        existing_ids = {
            source_id for (source_id,) in local_session.query(SourceMetadata.source_id).all()
        }

        inserted = 0
        for source_id, info in payload.items():
            if source_id in existing_ids:
                continue

            record = SourceMetadata(
                source_id=source_id,
                name=info["name"],
                display_name=info["display_name"],
                source_type=info["type"],
                filepath_raw=info["filepath_raw"],
                purchase_link=info.get("purchase_link", ""),
            )
            local_session.add(record)
            inserted += 1

        if inserted:
            local_session.commit()
        else:
            local_session.rollback()

        return inserted
    finally:
        if session is None:
            local_session.close()
