"""Roleplay Manager Service for handling character-based conversations."""

import openai
from typing import Dict, List, Optional, Any, AsyncGenerator
from config import get_settings
from prompts.system.roleplay import SYSTEM_ROLEPLAY_PROMPT
from prompts.domain.roleplay import ROLEPLAY_PROMPT
import uuid


class RoleplayManager:
    """Manager for roleplay conversations with AI characters."""

    def __init__(self, openai_client: Optional[openai.AsyncOpenAI] = None):
        """
        Initialize Roleplay Manager.

        Args:
            openai_client: Async OpenAI client (optional, will create default)
        """
        self.settings = get_settings()
        self.openai_client = openai_client or self._create_openai_client()

        # Simple in-memory conversation history (keyed by session_id)
        self.conversations: Dict[str, List[Dict[str, str]]] = {}

    def _create_openai_client(self) -> openai.AsyncOpenAI:
        """Create default async OpenAI client."""
        return openai.AsyncOpenAI(api_key=self.settings.openai_api_key)

    def _format_character_prompt(self, character: Dict[str, Any]) -> str:
        """
        Format the roleplay prompt with character data.

        Args:
            character: Character profile dictionary

        Returns:
            Formatted roleplay prompt
        """
        return ROLEPLAY_PROMPT.format(
            name=character.get("name", "Unknown"),
            age=character.get("age", "Unknown"),
            gender=character.get("gender", "Unknown"),
            occupation=character.get("occupation", "Unknown"),
            relationship=character.get("tags", {}).get("relationship", "Unknown"),
            tone=character.get("tags", {}).get("tone", "Unknown"),
            characteristics=character.get("tags", {}).get("characteristics", "Unknown"),
            speaking_style=character.get("speaking_style", "No specific style defined"),
            appearance=character.get("appearance", "No appearance description")
        )

    def _format_conversation_history(self, session_id: str, limit: int = 10) -> str:
        """
        Format conversation history for inclusion in prompt.

        Args:
            session_id: Session identifier
            limit: Maximum number of recent turns to include

        Returns:
            Formatted conversation history
        """
        if session_id not in self.conversations:
            return "This is the beginning of the conversation."

        history = self.conversations[session_id][-limit:]

        if not history:
            return "This is the beginning of the conversation."

        formatted = "**Conversation History:**\n"
        for turn in history:
            formatted += f"\nUser: {turn['user']}\n{turn.get('character_name', 'Character')}: {turn['assistant']}\n"

        return formatted

    def _build_system_prompt(
        self,
        character: Dict[str, Any],
        session_id: str
    ) -> str:
        """
        Build complete system prompt with character context and history.

        Args:
            character: Character profile dictionary
            session_id: Session identifier for history

        Returns:
            Complete system prompt
        """
        # Get formatted character prompt
        character_prompt = self._format_character_prompt(character)

        # Get conversation history
        history = self._format_conversation_history(session_id)

        # Aggregate: System roleplay instructions + Character context + History
        aggregated_prompt = f"""{SYSTEM_ROLEPLAY_PROMPT}

---

{character_prompt}

---

{history}
"""
        return aggregated_prompt

    async def chat(
        self,
        character: Dict[str, Any],
        message: str,
        session_id: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.8,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Send a message to the character and get a response.

        Args:
            character: Character profile dictionary
            message: User's message
            session_id: Session ID for conversation continuity
            model: OpenAI model to use
            temperature: Generation temperature
            max_tokens: Maximum tokens for response
            stream: Whether to stream the response

        Returns:
            Dictionary with response, session_id, and optionally stream generator
        """
        # Generate or use existing session ID
        if not session_id:
            session_id = f"roleplay_{uuid.uuid4()}"

        # Build system prompt with character and history
        system_prompt = self._build_system_prompt(character, session_id)

        # Prepare messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        # Call OpenAI
        try:
            if stream:
                # Return stream generator
                response_stream = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True
                )

                return {
                    "stream": response_stream,
                    "session_id": session_id,
                    "character_name": character.get("name", "Character")
                }
            else:
                # Get complete response
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                assistant_message = response.choices[0].message.content

                # Save conversation turn
                self._save_turn(
                    session_id=session_id,
                    user_message=message,
                    assistant_message=assistant_message,
                    character_name=character.get("name", "Character")
                )

                return {
                    "response": assistant_message,
                    "session_id": session_id,
                    "character_name": character.get("name", "Character"),
                    "tokens_used": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }

        except Exception as e:
            print(f"[ROLEPLAY ERROR] Failed to get response: {e}")
            raise

    def _save_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        character_name: str
    ):
        """
        Save a conversation turn to memory.

        Args:
            session_id: Session identifier
            user_message: User's message
            assistant_message: Assistant's response
            character_name: Name of the character
        """
        if session_id not in self.conversations:
            self.conversations[session_id] = []

        self.conversations[session_id].append({
            "user": user_message,
            "assistant": assistant_message,
            "character_name": character_name
        })

        print(f"[ROLEPLAY] Saved conversation turn for session: {session_id}")

    def save_turn_external(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        character_name: str
    ):
        """
        Public method to save a conversation turn externally (e.g., after streaming).

        Args:
            session_id: Session identifier
            user_message: User's message
            assistant_message: Assistant's response
            character_name: Name of the character
        """
        self._save_turn(session_id, user_message, assistant_message, character_name)

    def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of recent turns to retrieve

        Returns:
            List of conversation turns
        """
        if session_id not in self.conversations:
            return []

        history = self.conversations[session_id]
        if limit:
            history = history[-limit:]

        return history

    def clear_conversation(self, session_id: str) -> bool:
        """
        Clear conversation history for a session.

        Args:
            session_id: Session identifier

        Returns:
            True if cleared successfully, False if session not found
        """
        if session_id in self.conversations:
            del self.conversations[session_id]
            print(f"[ROLEPLAY] Cleared conversation for session: {session_id}")
            return True
        return False
