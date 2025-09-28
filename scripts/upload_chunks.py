"""Upload document chunks to the selected vector store backend.

This script reuses the RAG pipeline to process sources and persist their
embeddings either to Supabase pgvector or to the local ChromaDB instance used
for tests.

Usage examples:

    # Process a single source into Supabase (default backend)
    python scripts/upload_chunks.py --source-id BOOK001

    # Process multiple sources into Supabase
    python scripts/upload_chunks.py --source-id BOOK001 --source-id BOOK002

    # Process all known sources into local ChromaDB
    TEST_WITH_CHROMADB=true python scripts/upload_chunks.py --backend chroma --all

Environment variables:
    OPENAI_API_KEY      Required for embedding generation.
    SUPABASE_DB_URL     Required when using the Supabase backend.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, List

from concurrent.futures import ProcessPoolExecutor, as_completed

from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from rag_pipeline import RAGPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload document chunks to a vector store backend.")
    parser.add_argument(
        "--backend",
        choices=("supabase", "chroma"),
        default="supabase",
        help="Vector store backend to use (default: supabase)",
    )
    parser.add_argument(
        "--source-id",
        action="append",
        dest="source_ids",
        help="Source ID to process; may be provided multiple times.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process every source known to the metadata table.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Chunk size to use during processing (default: 500).",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Chunk overlap to use during processing (default: 100).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker processes (default: 4).",
    )
    return parser.parse_args()


def validate_environment(args: argparse.Namespace) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("ERROR: OPENAI_API_KEY environment variable missing; run aborted.")

    if args.backend == "supabase" and not os.getenv("SUPABASE_DB_URL"):
        raise SystemExit("ERROR: SUPABASE_DB_URL must be set when using the Supabase backend; run aborted.")


def resolve_sources(pipeline: RAGPipeline, args: argparse.Namespace) -> List[str]:
    if args.all:
        return sorted(pipeline.source_metadata.keys())

    if args.source_ids:
        return args.source_ids

    raise SystemExit("ERROR: Provide at least one --source-id or use --all; run aborted.")


def process_single_source(source_id: str, backend: str, chunk_size: int, chunk_overlap: int) -> str:
    """Top-level function executed in subprocesses for Supabase ingestion."""
    load_dotenv(".env")
    pipeline = RAGPipeline(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        test_with_chromadb=backend == "chroma",
    )
    ok = pipeline.process_source(source_id)
    if not ok:
        raise RuntimeError(f"Pipeline returned False for {source_id}")
    return source_id


def process_sources(
    pipeline: RAGPipeline,
    source_ids: Iterable[str],
    backend: str,
    workers: int,
) -> None:
    successes: List[str] = []
    failures: List[str] = []

    id_list = list(source_ids)
    if workers > 1:
        print(f"Running ingestion with {workers} processes...")
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(
                    process_single_source,
                    source_id,
                    backend,
                    pipeline.chunk_size,
                    pipeline.chunk_overlap,
                ): source_id
                for source_id in id_list
            }

            for future in as_completed(future_map):
                source_id = future_map[future]
                try:
                    result_id = future.result()
                except Exception as exc:
                    print(f"Processing {source_id} failed: {exc}")
                    failures.append(source_id)
                else:
                    print(f"Processing {result_id} succeeded")
                    successes.append(result_id)
    else:
        for source_id in id_list:
            try:
                print(f"Processing {source_id}...")
                ok = pipeline.process_source(source_id)
            except Exception as exc:  # pragma: no cover - defensive
                print(f"  Failed: {exc}")
                failures.append(source_id)
                continue

            if ok:
                print("  Success")
                successes.append(source_id)
            else:
                print("  Failed: pipeline returned False")
                failures.append(source_id)

    print("\nSummary:")
    print(f"  Succeeded: {len(successes)}")
    if successes:
        print(f"    {', '.join(successes)}")
    print(f"  Failed   : {len(failures)}")
    if failures:
        print(f"    {', '.join(failures)}")

    if failures:
        raise SystemExit(1)


def main() -> None:
    load_dotenv(".env")
    args = parse_args()
    validate_environment(args)

    pipeline = RAGPipeline(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        test_with_chromadb=args.backend == "chroma",
    )

    sources = resolve_sources(pipeline, args)
    process_sources(pipeline, sources, args.backend, args.workers)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        sys.exit(1)
