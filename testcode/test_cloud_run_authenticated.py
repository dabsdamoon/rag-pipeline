"""Invoke the deployed Cloud Run chat API using an authenticated request.

This helper fetches an ID token for the Cloud Run service using gcloud and
executes a test chat request. It is meant for manual testing while the service
remains locked down to specific IAM principals.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Dict, List

import httpx


# DEFAULT_SERVICE_URL = "https://houmy-api-932784017415.us-central1.run.app" # for relays-cloud
DEFAULT_SERVICE_URL = "https://houmy-api-369068805659.us-central1.run.app" # for project-houmy

def get_env_list(name: str) -> List[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def build_payload() -> Dict[str, object]:
    payload: Dict[str, object] = {
        "message": os.getenv("CHAT_MESSAGE", "안녕하세요, 서비스 점검 중입니다."),
        "language": os.getenv("CHAT_LANGUAGE", "Korean"),
        "domain": os.getenv("CHAT_DOMAIN", "books"),
        "session_id": os.getenv("CHAT_SESSION_ID", "cloud-run-test-session"),
    }

    source_ids = get_env_list("CHAT_SOURCE_IDS")
    if source_ids:
        payload["source_ids"] = source_ids

    max_tokens = os.getenv("CHAT_MAX_TOKENS")
    if max_tokens:
        try:
            payload["max_tokens"] = int(max_tokens)
        except ValueError:
            print("CHAT_MAX_TOKENS must be an integer", file=sys.stderr)
            sys.exit(1)

    min_relevance = os.getenv("CHAT_MIN_RELEVANCE_SCORE")
    if min_relevance:
        try:
            payload["min_relevance_score"] = float(min_relevance)
        except ValueError:
            print("CHAT_MIN_RELEVANCE_SCORE must be numeric", file=sys.stderr)
            sys.exit(1)

    return payload


def get_identity_token(service_url: str) -> str:
    account = os.getenv("GCLOUD_ACCOUNT", "dabin@relays.co.kr")
    cmd = ["gcloud", "auth", "print-identity-token"]

    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def main() -> None:
    service_url = os.getenv("CLOUD_RUN_SERVICE_URL", DEFAULT_SERVICE_URL).rstrip("/")
    token = get_identity_token(service_url)
    payload = build_payload()

    print("Sending request with payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    chat_url = f"{service_url}/chat"

    with httpx.Client(timeout=60.0) as client:
        response = client.post(chat_url, json=payload, headers=headers)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        print(f"Response body: {response.text}", file=sys.stderr)
        sys.exit(1)

    print("Response:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"Failed to fetch identity token: {exc.stderr}", file=sys.stderr)
        sys.exit(exc.returncode)
