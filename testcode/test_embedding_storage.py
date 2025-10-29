"""Quick check that chunk embeddings are stored and retrievable.

This script patches the OpenAI embedding client with a deterministic stub so we
can run the pipeline end-to-end without external dependencies. It processes a
source, verifies that embeddings were written to Chroma, and issues a search to
ensure the stored chunks are returned.
"""

from __future__ import annotations

import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, List

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from metadata_utils import get_source_metadata_map, seed_metadata_from_json

load_dotenv(".env")


class FakeEmbeddings:
    """Return a simple, deterministic 3-D vector for any text."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - interface hook
        self._scale = float(kwargs.get("dimensions", 3))

    def embed_query(self, text: str) -> List[float]:
        norm = float(sum(ord(ch) for ch in text) % 997 or 1)
        return [norm / i for i in (1, 2, 4)]


@contextmanager
def patched_embeddings() -> Iterable[None]:
    import rag_pipeline
    from unittest.mock import Mock, patch

    with patch.object(rag_pipeline, "OpenAIEmbeddings", side_effect=lambda *a, **k: FakeEmbeddings(*a, **k)):
        with patch.object(rag_pipeline.openai, "OpenAI", return_value=Mock()):
            yield


def main() -> None:
    from modules.rag_pipeline import RAGPipeline

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["CHROMA_PERSIST_DIRECTORY"] = tmpdir

        with patched_embeddings():
            if not get_source_metadata_map():
                inserted = seed_metadata_from_json("assets/dict_source_id.json")
                if not inserted:
                    raise RuntimeError("Source metadata table is empty; provide assets/dict_source_id.json or seed manually.")
            pipeline = RAGPipeline(
                chunk_size=400,
                chunk_overlap=0,
                embedding_model="fake",
                embedding_dimensions=3,
                test_with_chromadb=True,
            )

            if not pipeline.process_sources(["BOOK002"]):
                raise RuntimeError("Failed to process source BOOK002")

            stored_count = pipeline.collection.count()
            assert stored_count > 0, "No chunks persisted to Chroma"

            sample = pipeline.collection.peek(1)
            if not sample.get("ids"):
                raise RuntimeError("Collection.peek returned no records")

            sample_id = sample["ids"][0]
            sample_embedding = pipeline.collection.get(
                ids=[sample_id], include=["embeddings"]
            )["embeddings"][0]
            assert len(sample_embedding) == pipeline.embedding_dimensions, (
                f"Expected embedding dimension {pipeline.embedding_dimensions}, got {len(sample_embedding)}"
            )

            results = pipeline.search_documents(
                query="무통 테크닉이 궁금해",
                limit=3,
                source_ids=["BOOK002"],
                min_relevance_score=0.0,
            )

            if not results:
                raise RuntimeError("Search returned no results")

            print(f"Stored chunk count: {stored_count}")
            print(f"Top result source: {results[0]['source_id']}")
            print(f"Excerpt: {results[0]['content'][:100]}...")


if __name__ == "__main__":
    main()
