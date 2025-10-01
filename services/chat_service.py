"""Chat service for RAG pipeline."""

import uuid
from typing import List, Dict, Any, Optional, Generator
import openai

from prompts.prompt_manager import PromptManager
from exceptions import LLMError, StreamingError
from config import get_settings


class ChatService:
    """Handles chat response generation using LLM."""

    def __init__(
        self,
        openai_client: openai.OpenAI,
        prompt_manager: PromptManager,
        source_metadata: Dict[str, Dict[str, str]],
    ):
        """
        Initialize chat service.

        Args:
            openai_client: OpenAI client instance
            prompt_manager: Prompt manager instance
            source_metadata: Source metadata mapping
        """
        self.openai_client = openai_client
        self.prompt_manager = prompt_manager
        self.source_metadata = source_metadata
        self.settings = get_settings()

    def generate_response(
        self,
        query: str,
        context_docs: List[Dict[str, Any]],
        language: str = "English",
        domain: Optional[str] = None,
        session_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        layer_config: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a chat response (non-streaming).

        Args:
            query: User query
            context_docs: Retrieved context documents
            language: Response language
            domain: Domain context
            session_id: Session identifier
            max_tokens: Maximum tokens for response
            layer_config: Prompt layer configuration

        Returns:
            Response dictionary with text, sources, and token usage

        Raises:
            LLMError: If LLM call fails
        """
        try:
            # Build prompts
            system_prompt, user_prompt, _prompt_meta = self.prompt_manager.build_prompt_messages(
                query=query,
                language=language,
                context_docs=context_docs,
                domain=domain,
                source_metadata=self.source_metadata,
                layer_config=layer_config,
            )

            if not user_prompt:
                raise ValueError("Unable to generate user prompt")

            # Prepare sources for response
            sources = self._prepare_sources(context_docs)

            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            # Make OpenAI API call
            api_params = {
                "model": self.settings.llm_model,
                "messages": messages,
            }
            if max_tokens is not None:
                api_params["max_completion_tokens"] = max_tokens

            response = self.openai_client.chat.completions.create(**api_params)

            # Extract response
            ai_response = response.choices[0].message.content
            tokens_used = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

            return {
                "response": ai_response,
                "sources": sources,
                "tokens_used": tokens_used,
                "session_id": session_id or str(uuid.uuid4())
            }

        except Exception as e:
            print(f"[CHAT ERROR] Error generating response: {e}")
            import traceback
            traceback.print_exc()
            raise LLMError(
                "Failed to generate response",
                details={"query": query[:100], "error": str(e)}
            ) from e

    def generate_streaming_response(
        self,
        query: str,
        context_docs: List[Dict[str, Any]],
        language: str = "English",
        domain: Optional[str] = None,
        session_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        layer_config: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a streaming chat response.

        Args:
            query: User query
            context_docs: Retrieved context documents
            language: Response language
            domain: Domain context
            session_id: Session identifier
            max_tokens: Maximum tokens for response
            layer_config: Prompt layer configuration

        Returns:
            Dictionary with stream generator, sources, and session_id

        Raises:
            StreamingError: If streaming fails
        """
        try:
            # Build prompts
            system_prompt, user_prompt, _prompt_meta = self.prompt_manager.build_prompt_messages(
                query=query,
                language=language,
                context_docs=context_docs,
                domain=domain,
                source_metadata=self.source_metadata,
                layer_config=layer_config,
            )

            if not user_prompt:
                raise ValueError("Unable to generate user prompt")

            # Prepare sources
            sources = self._prepare_sources(context_docs)

            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            # Make streaming OpenAI API call
            api_params = {
                "model": self.settings.llm_model_streaming,
                "messages": messages,
                "stream": True
            }
            if max_tokens is not None:
                api_params["max_completion_tokens"] = max_tokens

            response_stream = self.openai_client.chat.completions.create(**api_params)

            return {
                "stream": response_stream,
                "sources": sources,
                "session_id": session_id or str(uuid.uuid4())
            }

        except Exception as e:
            print(f"[CHAT ERROR] Error generating streaming response: {e}")
            import traceback
            traceback.print_exc()
            raise StreamingError(
                "Failed to generate streaming response",
                details={"query": query[:100], "error": str(e)}
            ) from e

    def _prepare_sources(self, context_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare source references from context documents.

        Args:
            context_docs: Context documents from search

        Returns:
            List of formatted source references
        """
        sources = []
        try:
            for doc in context_docs:
                meta = self.source_metadata.get(doc["source_id"], {})
                source_info = {
                    "source_id": doc["source_id"],
                    "display_name": meta.get("display_name", doc["source_id"]),
                    "purchase_link": meta.get("purchase_link", ""),
                    "page_number": doc.get("page_number", 0),
                    "excerpt": doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"],
                    "relevance_score": doc.get("relevance_score", 0.0)
                }
                sources.append(source_info)
        except Exception as e:
            print(f"[CHAT WARNING] Error preparing sources: {e}")
            import traceback
            traceback.print_exc()

        return sources
