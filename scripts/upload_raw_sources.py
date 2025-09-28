from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trigger raw source uploads via the Houmy API")
    parser.add_argument("--bucket", required=True, help="Target Supabase Storage bucket name")
    parser.add_argument(
        "--metadata",
        default="assets/dict_source_id.json",
        help="Path to metadata JSON file consumed by the API",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Optional prefix added to each uploaded object path",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting existing objects via upsert",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List planned uploads without sending files",
    )
    parser.add_argument(
        "--create-bucket",
        action="store_true",
        help="Create the bucket if it does not exist",
    )
    parser.add_argument(
        "--public-bucket",
        action="store_true",
        help="Mark the bucket as public when creating it (requires --create-bucket)",
    )
    parser.add_argument(
        "--api-base",
        default="http://localhost:8001",
        help="Base URL for the Houmy API (default: http://localhost:8001)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    metadata_path = Path(args.metadata).resolve()
    if not metadata_path.exists():
        print(f"Metadata file not found: {metadata_path}")
        return 1

    payload = {
        "bucket": args.bucket,
        "metadata_path": str(metadata_path),
        "prefix": args.prefix,
        "overwrite": args.overwrite,
        "dry_run": args.dry_run,
        "create_bucket": args.create_bucket,
        "public_bucket": args.public_bucket,
    }

    endpoint = args.api_base.rstrip("/") + "/sources/upload_raw"

    try:
        response = requests.post(endpoint, json=payload, timeout=300)
    except requests.RequestException as exc:
        print(f"Failed to reach API: {exc}")
        return 1

    if response.status_code != 200:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        print(f"Upload failed with status {response.status_code}: {detail}")
        return 1

    body = response.json()
    bucket = body.get("bucket", args.bucket)
    for item in body.get("results", []):
        status = item.get("status", "unknown").upper()
        source_id = item.get("source_id", "<unknown>")
        local_path = item.get("local_path", "")
        remote_path = item.get("remote_path") or ""
        message = f"[ {status} ] {source_id}: {local_path}"
        if remote_path:
            message += f" -> {bucket}/{remote_path}"
        detail = item.get("detail")
        if detail:
            message += f" ({detail})"
        print(message)

    return 0


if __name__ == "__main__":
    sys.exit(main())
