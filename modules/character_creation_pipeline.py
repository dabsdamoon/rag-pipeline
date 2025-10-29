"""Character Creation Pipeline using LLM for generating character details.

This module generates character descriptions (speaking style, appearance) based on
provided attributes like name, occupation, age, gender, and personality tags.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import openai
from config import get_settings
from prompts.character import (
    SPEAKING_STYLE_SYSTEM_PROMPT,
    get_speaking_style_prompt,
    APPEARANCE_SYSTEM_PROMPT,
    get_appearance_prompt
)


class CharacterCreationPipeline:
    """Pipeline for creating character profiles using LLM generation."""

    def __init__(
        self,
        openai_client: Optional[openai.AsyncOpenAI] = None,
        tags_config_path: str = "assets/dict_tags.json",
    ):
        """
        Initialize Character Creation Pipeline.

        Args:
            openai_client: Async OpenAI client (optional, will create default)
            tags_config_path: Path to tags configuration JSON
        """
        self.settings = get_settings()
        self.openai_client = openai_client or self._create_openai_client()
        self.tags_config_path = tags_config_path
        self.available_tags = self._load_tags()

    def _create_openai_client(self) -> openai.AsyncOpenAI:
        """Create default async OpenAI client."""
        return openai.AsyncOpenAI(api_key=self.settings.openai_api_key)

    def _load_tags(self) -> Dict[str, List[str]]:
        """Load available tags from configuration file."""
        try:
            tags_path = Path(self.tags_config_path)
            if not tags_path.exists():
                print(f"[CHARACTER WARNING] Tags file not found: {self.tags_config_path}")
                return {
                    "relationship": ["friend", "co-worker"],
                    "tone": ["formal", "casual"],
                    "characteristics": ["humorous", "tsundere", "empathetic"]
                }

            with open(tags_path, 'r', encoding='utf-8') as f:
                tags = json.load(f)
                print(f"[CHARACTER] Loaded tags: {tags}")
                return tags
        except Exception as e:
            print(f"[CHARACTER ERROR] Failed to load tags: {e}")
            return {}

    def validate_tags(self, tags: Dict[str, str]) -> Dict[str, List[str]]:
        """
        Validate tags against available options.

        Args:
            tags: Dictionary with tag categories and selected values

        Returns:
            Dictionary with validation errors (empty if all valid)

        Example:
            >>> errors = pipeline.validate_tags({
            ...     "relationship": "friend",
            ...     "tone": "casual",
            ...     "characteristics": "humorous"
            ... })
        """
        errors = {}

        for category, value in tags.items():
            if category not in self.available_tags:
                errors[category] = f"Unknown tag category: {category}"
            elif value not in self.available_tags[category]:
                errors[category] = (
                    f"Invalid value '{value}'. "
                    f"Available options: {', '.join(self.available_tags[category])}"
                )

        return errors

    async def create_character(
        self,
        name: str,
        occupation: str,
        age: int,
        gender: str,
        tags: Dict[str, str],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Generate character profile with speaking style and appearance asynchronously.

        Speaking style and appearance are generated in parallel for better performance.

        Args:
            name: Character's name
            occupation: Character's occupation
            age: Character's age
            gender: Character's gender
            tags: Dictionary of tags (relationship, tone, characteristics)
            model: OpenAI model to use
            temperature: Generation temperature (0.0-1.0)

        Returns:
            Dictionary containing:
                - name: str
                - occupation: str
                - age: int
                - gender: str
                - tags: Dict[str, str]
                - speaking_style: str
                - appearance: str
                - success: bool
                - errors: List[str] (if any)

        Example:
            >>> character = await pipeline.create_character(
            ...     name="Alice",
            ...     occupation="Software Engineer",
            ...     age=28,
            ...     gender="Female",
            ...     tags={
            ...         "relationship": "co-worker",
            ...         "tone": "casual",
            ...         "characteristics": "humorous"
            ...     }
            ... )
        """
        # Validate inputs
        errors = []

        if not name or len(name.strip()) == 0:
            errors.append("Name is required")

        if not occupation or len(occupation.strip()) == 0:
            errors.append("Occupation is required")

        if age < 1 or age > 150:
            errors.append("Age must be between 1 and 150")

        if not gender or len(gender.strip()) == 0:
            errors.append("Gender is required")

        # Validate tags
        tag_errors = self.validate_tags(tags)
        if tag_errors:
            for category, error in tag_errors.items():
                errors.append(f"Tag validation error for '{category}': {error}")

        if errors:
            return {
                "name": name,
                "occupation": occupation,
                "age": age,
                "gender": gender,
                "tags": tags,
                "speaking_style": "",
                "appearance": "",
                "success": False,
                "errors": errors
            }

        # Generate character details using LLM (in parallel for better performance)
        try:
            # Run both generations concurrently
            speaking_style, appearance = await asyncio.gather(
                self._generate_speaking_style(
                    name=name,
                    occupation=occupation,
                    age=age,
                    gender=gender,
                    tags=tags,
                    model=model,
                    temperature=temperature
                ),
                self._generate_appearance(
                    name=name,
                    occupation=occupation,
                    age=age,
                    gender=gender,
                    tags=tags,
                    model=model,
                    temperature=temperature
                )
            )

            return {
                "name": name,
                "occupation": occupation,
                "age": age,
                "gender": gender,
                "tags": tags,
                "speaking_style": speaking_style,
                "appearance": appearance,
                "success": True,
                "errors": []
            }

        except Exception as e:
            print(f"[CHARACTER ERROR] Failed to generate character: {e}")
            return {
                "name": name,
                "occupation": occupation,
                "age": age,
                "gender": gender,
                "tags": tags,
                "speaking_style": "",
                "appearance": "",
                "success": False,
                "errors": [f"Generation failed: {str(e)}"]
            }

    async def _generate_speaking_style(
        self,
        name: str,
        occupation: str,
        age: int,
        gender: str,
        tags: Dict[str, str],
        model: str,
        temperature: float
    ) -> str:
        """Generate speaking style description using LLM asynchronously."""

        prompt = get_speaking_style_prompt(
            name=name,
            occupation=occupation,
            age=age,
            gender=gender,
            relationship=tags.get('relationship', 'N/A'),
            tone=tags.get('tone', 'N/A'),
            characteristics=tags.get('characteristics', 'N/A')
        )

        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": SPEAKING_STYLE_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=temperature,
            max_tokens=500
        )

        return response.choices[0].message.content.strip()

    async def _generate_appearance(
        self,
        name: str,
        occupation: str,
        age: int,
        gender: str,
        tags: Dict[str, str],
        model: str,
        temperature: float
    ) -> str:
        """Generate appearance description using LLM asynchronously."""

        prompt = get_appearance_prompt(
            name=name,
            occupation=occupation,
            age=age,
            gender=gender,
            characteristics=tags.get('characteristics', 'N/A')
        )

        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": APPEARANCE_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=temperature,
            max_tokens=500
        )

        return response.choices[0].message.content.strip()

    def get_available_tags(self) -> Dict[str, List[str]]:
        """
        Get all available tag options.

        Returns:
            Dictionary with tag categories and their available values
        """
        return self.available_tags.copy()

    async def create_batch_characters(
        self,
        characters: List[Dict[str, Any]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Create multiple characters in batch asynchronously.

        All characters are created in parallel for maximum performance.

        Args:
            characters: List of character attribute dictionaries
            model: OpenAI model to use
            temperature: Generation temperature

        Returns:
            List of character profile dictionaries

        Example:
            >>> results = await pipeline.create_batch_characters([
            ...     {
            ...         "name": "Alice",
            ...         "occupation": "Engineer",
            ...         "age": 28,
            ...         "gender": "Female",
            ...         "tags": {"relationship": "co-worker", "tone": "casual", "characteristics": "humorous"}
            ...     },
            ...     {
            ...         "name": "Bob",
            ...         "occupation": "Designer",
            ...         "age": 32,
            ...         "gender": "Male",
            ...         "tags": {"relationship": "friend", "tone": "formal", "characteristics": "empathetic"}
            ...     }
            ... ])
        """
        # Create all characters in parallel
        tasks = [
            self.create_character(
                name=char_data.get("name", ""),
                occupation=char_data.get("occupation", ""),
                age=char_data.get("age", 25),
                gender=char_data.get("gender", ""),
                tags=char_data.get("tags", {}),
                model=model,
                temperature=temperature
            )
            for char_data in characters
        ]

        results = await asyncio.gather(*tasks)
        return list(results)
