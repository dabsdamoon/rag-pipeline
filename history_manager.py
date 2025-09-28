"""Utilities for managing conversation history within the RAG pipeline."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from databases import HistoryStoreBackend
from prompts.summarize.default import DEFAULT_SUMMARY_PROMPT
from prompts.system.history import SYSTEM_HISTORY_PROMPT
from utils.timing import measure_time

class HistoryManager:
    """Encapsulates summarisation, storage, and retrieval of chat history."""

    def __init__(
        self,
        *,
        embeddings,
        openai_client,
        history_store: Optional[HistoryStoreBackend],
        summary_prompt: str = DEFAULT_SUMMARY_PROMPT,
        results_limit: int = 5,
        min_relevance: float = 0.2,
    ) -> None:
        self.embeddings = embeddings
        self.openai_client = openai_client
        self.history_store = history_store
        self.summary_prompt = summary_prompt
        self.results_limit = results_limit
        self.min_relevance = min_relevance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @measure_time("Prepare History Context")
    def prepare_history_context(
        self,
        *,
        message: str,
        user_id: Optional[str],
    ) -> Tuple[Optional[List[float]], List[Dict[str, Any]], str]:
        """Return query embedding, raw history records, and aggregated text."""

        if not self._can_use_history(user_id):
            return None, [], ""

        query_embedding = self.embeddings.embed_query(message)
        history_records = self.fetch_relevant_history(
            query_embedding=query_embedding,
            user_id=user_id,
        )
        history_text = self.build_history_text(history_records)

        return query_embedding, history_records, history_text

    def apply_history_layer(
        self,
        layer_config: Optional[Dict[str, Dict[str, Any]]],
        history_text: str,
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """Inject aggregated history text into the prompt layer configuration."""

        if not history_text:
            return copy.deepcopy(layer_config) if layer_config else None

        config = copy.deepcopy(layer_config) if layer_config else {}

        existing = config.get("history")
        if existing is None:
            config["history"] = {
                "id": "default",
                "variables": {"history": history_text},
                "include": True,
            }
            return config

        if existing.get("include") is False:
            return config

        if existing.get("prompt"):
            return config

        variables = copy.deepcopy(existing.get("variables") or {})
        if variables.get("history"):
            variables["history"] = f"{variables['history']}\n{history_text}"
        else:
            variables["history"] = history_text

        existing["variables"] = variables
        if not existing.get("id"):
            existing["id"] = "default"
        config["history"] = existing
        return config

    @measure_time("Record Turn History")
    def record_turn_history(
        self,
        *,
        user_id: Optional[str],
        session_id: Optional[str],
        user_message: str,
        assistant_message: str,
        turn_timestamp: Optional[datetime] = None,
    ) -> Optional[str]:
        """Summarise and persist a chat turn; returns stored summary when available."""

        if not self._can_use_history(user_id):
            return None

        summary = self.summarize_turn(user_message, assistant_message)
        if not summary:
            return None

        try:
            embedding = self.embeddings.embed_query(summary)
            timestamp = turn_timestamp or datetime.now(timezone.utc)
            self.history_store.store_turn(
                user_id=user_id,  # type: ignore[arg-type]
                session_id=session_id,
                summary=summary,
                embedding=embedding,
                turn_timestamp=timestamp,
            )
        except Exception as exc:
            print(f"[HISTORY WARNING] Failed to store turn history: {exc}")

        return summary

    def purge_user_history(self, user_id: str) -> None:
        if not self._can_use_history(user_id):
            return

        try:
            self.history_store.delete_user_history(user_id=user_id)  # type: ignore[arg-type]
        except Exception as exc:
            print(f"[HISTORY WARNING] Failed to purge history for {user_id}: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @measure_time("Summarise chat turn")
    def summarize_turn(self, user_message: str, assistant_message: str) -> Optional[str]:
        """Summarise a single chat turn via the LLM."""

        if not user_message or not assistant_message or not self.openai_client:
            return None

        prompt = self.summary_prompt.format(
            user_message=user_message.strip(),
            assistant_message=assistant_message.strip(),
        ).strip()

        messages = [
            {"role": "system", "content": SYSTEM_HISTORY_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
            )
        except Exception as exc:
            print(f"[HISTORY ERROR] Failed to summarise turn: {exc}")
            return None

        summary = response.choices[0].message.content if response.choices else ""
        return summary.strip() if summary else None

    def fetch_relevant_history(
        self,
        *,
        query_embedding: List[float],
        user_id: Optional[str],
        limit: Optional[int] = None,
        min_relevance: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve stored summaries related to the current query."""

        if not self._can_use_history(user_id):
            return []

        history_limit = limit if limit is not None else self.results_limit
        if history_limit <= 0:
            return []

        try:
            return self.history_store.query_history(
                query_embedding=query_embedding,
                limit=history_limit,
                user_id=user_id,
                min_relevance=min_relevance if min_relevance is not None else self.min_relevance,
            )
        except Exception as exc:
            print(f"[HISTORY WARNING] Failed to query history store: {exc}")
            return []

    @staticmethod
    def build_history_text(history_records: List[Dict[str, Any]]) -> str:
        if not history_records:
            return ""

        lines: List[str] = []
        for record in history_records:
            summary = record.get("summary")
            if not summary:
                continue

            timestamp = record.get("turn_timestamp")
            if isinstance(timestamp, datetime):
                timestamp_str = timestamp.isoformat()
            elif timestamp:
                timestamp_str = str(timestamp)
            else:
                timestamp_str = ""

            if timestamp_str:
                lines.append(f"[{timestamp_str}] {summary}")
            else:
                lines.append(summary)

        return "\n".join(lines)

    def _can_use_history(self, user_id: Optional[str]) -> bool:
        return bool(user_id and self.history_store)
