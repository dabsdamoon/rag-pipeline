"""Parallel smoke tests for `RAGPipeline.chat` and `chat` with streaming."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.rag_pipeline import RAGPipeline  # noqa: E402


TEST_QUESTIONS_PATH = Path(__file__).with_name("test_questions.json")
TMP_DIR = PROJECT_ROOT / "tmp"

load_dotenv(PROJECT_ROOT / ".env")

TEST_HISTORY_USER_ID = "testcode"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exercise RAGPipeline chat flows in parallel.")
    parser.add_argument(
        "--use-chromadb",
        action="store_true",
        help="Force the pipeline to run with ChromaDB (default honours TEST_WITH_CHROMADB).",
    )
    parser.add_argument(
        "--use-supabase",
        action="store_true",
        help="Force the pipeline to run with Supabase regardless of environment flag.",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Run test cases sequentially without multiprocessing.",
    )
    parser.add_argument(
        "--save-history",
        action="store_true",
        help="Persist history generated during tests (otherwise it is cleaned up).",
    )
    return parser.parse_args()


def resolve_backend(args: argparse.Namespace) -> bool:
    if args.use_chromadb and args.use_supabase:
        raise ValueError("Choose either --use-chromadb or --use-supabase, not both.")

    if args.use_chromadb:
        return True
    if args.use_supabase:
        return False

    return os.getenv("TEST_WITH_CHROMADB", "false").strip().lower() == "true"


def pick_sources(pipeline: RAGPipeline, domain: str, limit: int = 3) -> List[str]:
    domain = domain.lower()
    candidates = [
        source_id
        for source_id, meta in pipeline.source_metadata.items()
        if (domain == "insurance" and meta.get("source_type") == "insurance")
        or (domain != "insurance" and meta.get("source_type") != "insurance")
    ]

    if not candidates:
        raise RuntimeError(f"No sources available for domain '{domain}'.")

    return candidates[:limit]


def load_test_cases() -> List[Tuple[str, str, Dict[str, object]]]:
    if not TEST_QUESTIONS_PATH.exists():
        raise FileNotFoundError(f"Unable to find test questions at {TEST_QUESTIONS_PATH}")

    with TEST_QUESTIONS_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("test_questions.json must map languages to question sets.")

    cases: List[Tuple[str, str, Dict[str, object]]] = []

    for language, language_cases in data.items():
        if not isinstance(language_cases, dict):
            raise ValueError(f"Language '{language}' must map to an object of question cases.")

        for case_name, case_payload in language_cases.items():
            if not isinstance(case_payload, dict):
                raise ValueError(f"Case '{case_name}' for language '{language}' must be an object.")
            for key in ("query", "source_ids", "session_id", "domain"):
                if key not in case_payload:
                    raise ValueError(
                        f"Case '{case_name}' for language '{language}' is missing required key '{key}'."
                    )

            cases.append((language, case_name, case_payload))

    return cases


def execute_test_case(payload: Tuple[str, str, Dict[str, object], bool, str, bool]) -> Dict[str, object]:
    language, case_name, case, use_chromadb, log_directory, save_history = payload

    pipeline = RAGPipeline(test_with_chromadb=use_chromadb)

    domain = case["domain"]
    query = case["query"]
    session_id = case.get("session_id")
    requested_sources = case.get("source_ids") or []
    min_relevance = case.get("min_relevance_score")
    layer_config = case.get("layer_config")

    try:
        if not requested_sources:
            source_ids = pick_sources(pipeline, domain)
        else:
            source_ids = requested_sources

        # Get raw documents
        raw_docs = pipeline.search_documents(
            query=query,
            limit=10,  # Get more for context engineering to optimize
            source_ids=source_ids,
            min_relevance_score=min_relevance if min_relevance is not None else 0.05,
        )

        # Apply context engineering to optimize results
        engineered_context = pipeline.context_engineer.engineer_context(
            query=query,
            raw_documents=raw_docs,
            query_type=None,  # Auto-detect
            source_metadata=pipeline.source_metadata,
        )

        docs = engineered_context["documents"]

        stream = False # For token counting, set to False

        chat_kwargs = {
            "message": query,
            "language": language,
            "session_id": session_id,
            "domain": domain,
            "stream": stream,
            "source_ids": source_ids,
            "min_relevance_score": min_relevance,
            "layer_config": layer_config,
            "user_id": TEST_HISTORY_USER_ID,
        }

        response_payload = pipeline.chat(**chat_kwargs)

        if stream:
            streamed_text = ""
            for chunk in response_payload.get("stream", []):
                delta = chunk.choices[0].delta.content
                if delta:
                    streamed_text += delta
            response_text = streamed_text
            tokens_used = None
        else:
            response_text = response_payload.get("response", "")
            tokens_used = response_payload.get("tokens_used")

        if response_text and save_history:
            try:
                pipeline.record_turn_history(
                    user_id=TEST_HISTORY_USER_ID,
                    session_id=response_payload.get("session_id"),
                    user_message=query,
                    assistant_message=response_text,
                )
            except Exception as exc:
                print(f"[TEST WARNING] Unable to record test history: {exc}")

        log_dir_path = Path(log_directory)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time() * 1000)
        log_filename = f"chat_test_{language.lower()}_{case_name}_{domain.lower()}_{timestamp}.json"
        log_path = log_dir_path / log_filename

        log_data = {
            "language": language,
            "case_name": case_name,
            "domain": domain,
            "query": query,
            "session_id": session_id,
            "use_chromadb": use_chromadb,
            "requested_source_ids": requested_sources,
            "resolved_source_ids": source_ids,
            "context_engineering": {
                "query_type": engineered_context["query_type"],
                "raw_document_count": len(raw_docs),
                "optimized_document_count": len(docs),
                "estimated_tokens": engineered_context["context_stats"]["estimated_tokens"],
                "stats": engineered_context["context_stats"],
            },
            "documents": docs,
            "response_text": response_text,
            "tokens_used": tokens_used,
            "min_relevance_score": min_relevance,
            "layer_config": layer_config,
        }

        with log_path.open("w", encoding="utf-8") as file:
            json.dump(log_data, file, ensure_ascii=False, indent=2)

        return {
            "language": language,
            "case_name": case_name,
            "domain": domain,
            "response_preview": response_text[:120],
            "log_path": str(log_path),
            "query_type": engineered_context["query_type"],
            "docs_optimized": f"{len(raw_docs)} → {len(docs)}",
            "tokens_saved": engineered_context["context_stats"]["estimated_tokens"],
        }
    finally:
        if not save_history:
            try:
                pipeline.clear_user_history(TEST_HISTORY_USER_ID)
            except Exception as exc:
                print(f"[TEST WARNING] Unable to purge test history: {exc}")



def main() -> None:
    args = parse_args()
    use_chromadb = resolve_backend(args)

    backend_label = "ChromaDB" if use_chromadb else "Supabase"
    print(f"Initialising RAGPipeline tests ({backend_label})")

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY environment variable is required to instantiate RAGPipeline.")

    test_cases = load_test_cases()
    timestamp_label = time.strftime("%Y%m%d_%H%M%S")
    log_directory = TMP_DIR / f"log_{timestamp_label}"
    log_directory.mkdir(parents=True, exist_ok=True)
    payloads: List[Tuple[str, str, Dict[str, object], bool, str, bool]] = [
        (language, case_name, case_payload, use_chromadb, str(log_directory), args.save_history)
        for language, case_name, case_payload in test_cases
    ]

    if args.no_parallel:
        for payload in payloads:
            summary = execute_test_case(payload)
            print(
                f"Completed {summary['language']}::{summary['case_name']} ({summary['domain']}) "
                f"[{summary['query_type']}]\n"
                f"  Context Engineering: {summary['docs_optimized']} docs, {summary['tokens_saved']} tokens\n"
                f"  Log: {summary['log_path']}\n"
                f"  Response: {summary['response_preview']}"
            )
    else:
        with ProcessPoolExecutor() as executor:
            for summary in executor.map(execute_test_case, payloads):
                print(
                    f"Completed {summary['language']}::{summary['case_name']} ({summary['domain']}) "
                    f"[{summary['query_type']}]\n"
                    f"  Context Engineering: {summary['docs_optimized']} docs, {summary['tokens_saved']} tokens\n"
                    f"  Log: {summary['log_path']}\n"
                    f"  Response: {summary['response_preview']}"
                )


if __name__ == "__main__":
    main()
