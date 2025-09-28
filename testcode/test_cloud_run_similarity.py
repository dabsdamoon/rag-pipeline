"""Call the Cloud Run `/search` endpoint and print retrieved chunks.

This script mirrors the Supabase direct query test but exercises the deployed
FastAPI service instead. It authenticates using the Houmy API token and posts a
search request, printing the returned chunks and similarity scores.

Environment variables:
    CLOUD_RUN_SERVICE_URL   Base URL of the deployed service.
    API_TOKEN               Optional API token for Authorization header.
    SEARCH_QUERY            Query text (default: "무통 분만이란?").
    SEARCH_SOURCE_IDS       Comma-separated list of source IDs to filter.
    SEARCH_LIMIT            Number of results to request (default: 5).
    SEARCH_MIN_SCORE        Minimum relevance (default: 0.2).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List

import httpx


# DEFAULT_SERVICE_URL = "https://houmy-api-932784017415.us-central1.run.app" # for relays-cloud
DEFAULT_SERVICE_URL = "https://houmy-api-369068805659.us-central1.run.app" # for project-houmy

DEFAULT_API_TOKEN = os.getenv("API_TOKEN") or os.getenv("TEST_API_TOKEN")


def load_env_list(name: str) -> List[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def build_payload() -> Dict[str, object]:
    payload: Dict[str, object] = {
        "query": os.getenv("SEARCH_QUERY", "수녀님이랑 어떤 일이 있었어?"),
        "limit": int(os.getenv("SEARCH_LIMIT", "5")),
        "min_relevance_score": float(os.getenv("SEARCH_MIN_SCORE", "0.2")),
    }

    source_ids = load_env_list("SEARCH_SOURCE_IDS")
    if source_ids:
        payload["source_ids"] = source_ids

    return payload


def main() -> None:
    service_url = os.getenv("CLOUD_RUN_SERVICE_URL", DEFAULT_SERVICE_URL).rstrip("/")
    token = os.getenv("API_TOKEN", DEFAULT_API_TOKEN)
    payload = build_payload()

    print("Sending search request with payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    search_url = f"{service_url}/search"

    with httpx.Client(timeout=60.0) as client:
        response = client.post(search_url, headers=headers, json=payload)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        print(f"Response body: {response.text}", file=sys.stderr)
        sys.exit(1)

    body = response.json()
    print("Response:")
    print(json.dumps(body, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Cancelled by user", file=sys.stderr)
