"""Utility script to purge demo-page conversation history."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(PROJECT_ROOT))

from rag_pipeline import RAGPipeline  # noqa: E402  (import after sys.path tweak)


def main() -> None:
    use_chromadb = os.getenv("TEST_WITH_CHROMADB", "false").strip().lower() == "true"

    pipeline = RAGPipeline(test_with_chromadb=use_chromadb)

    if not pipeline.history_manager:
        print("History manager is not configured; nothing to delete.")
        return

    pipeline.clear_user_history("demopage")
    print("Cleared history entries for user_id='demopage'.")


if __name__ == "__main__":
    main()

