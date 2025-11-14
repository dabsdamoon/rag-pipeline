"""Character Storage Service using ChromaDB for persisting character profiles."""

import chromadb
from chromadb.config import Settings
from typing import Dict, List, Optional, Any
import json
from pathlib import Path
import uuid


class CharacterStorageService:
    """Service for storing and retrieving character profiles using ChromaDB."""

    def __init__(
        self,
        persist_directory: str = "./chroma_data/characters",
        collection_name: str = "character_profiles"
    ):
        """
        Initialize Character Storage Service.

        Args:
            persist_directory: Directory to persist ChromaDB data
            collection_name: Name of the ChromaDB collection
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Storage for AI character profiles for roleplay"}
        )

        print(f"[CHARACTER STORAGE] Initialized with collection: {collection_name}")
        print(f"[CHARACTER STORAGE] Persist directory: {self.persist_directory}")

    def save_character(self, character: Dict[str, Any]) -> str:
        """
        Save a character profile to ChromaDB.

        Args:
            character: Character data dictionary with keys:
                - name, occupation, age, gender, tags, speaking_style, appearance

        Returns:
            character_id: UUID of the saved character

        Example:
            >>> character_id = storage.save_character({
            ...     "name": "Alice",
            ...     "occupation": "Engineer",
            ...     "age": 28,
            ...     "gender": "Female",
            ...     "tags": {"relationship": "co-worker", "tone": "casual"},
            ...     "speaking_style": "...",
            ...     "appearance": "..."
            ... })
        """
        # Generate unique ID
        character_id = str(uuid.uuid4())

        # Create searchable document (concatenate key character info)
        document = f"""
        Name: {character.get('name', '')}
        Occupation: {character.get('occupation', '')}
        Age: {character.get('age', '')}
        Gender: {character.get('gender', '')}
        Relationship: {character.get('tags', {}).get('relationship', '')}
        Tone: {character.get('tags', {}).get('tone', '')}
        Characteristics: {character.get('tags', {}).get('characteristics', '')}
        Speaking Style: {character.get('speaking_style', '')}
        Appearance: {character.get('appearance', '')}
        """.strip()

        # Prepare metadata (ChromaDB metadata must be flat key-value)
        metadata = {
            "name": str(character.get("name", "")),
            "occupation": str(character.get("occupation", "")),
            "age": str(character.get("age", "")),
            "gender": str(character.get("gender", "")),
            "relationship": str(character.get("tags", {}).get("relationship", "")),
            "tone": str(character.get("tags", {}).get("tone", "")),
            "characteristics": str(character.get("tags", {}).get("characteristics", "")),
            # Store complex data as JSON strings
            "character_json": json.dumps(character, ensure_ascii=False)
        }

        # Add to collection
        self.collection.add(
            documents=[document],
            metadatas=[metadata],
            ids=[character_id]
        )

        print(f"[CHARACTER STORAGE] Saved character '{character.get('name')}' with ID: {character_id}")
        return character_id

    def get_character(self, character_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a character profile by ID.

        Args:
            character_id: UUID of the character

        Returns:
            Character data dictionary or None if not found
        """
        try:
            result = self.collection.get(
                ids=[character_id],
                include=["metadatas"]
            )

            if not result["ids"]:
                print(f"[CHARACTER STORAGE] Character not found: {character_id}")
                return None

            # Parse character from JSON metadata
            metadata = result["metadatas"][0]
            character = json.loads(metadata["character_json"])
            character["character_id"] = character_id

            print(f"[CHARACTER STORAGE] Retrieved character '{character.get('name')}': {character_id}")
            return character

        except Exception as e:
            print(f"[CHARACTER STORAGE ERROR] Failed to get character {character_id}: {e}")
            return None

    def list_characters(
        self,
        limit: int = 100,
        filters: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        List all characters with optional filtering.

        Args:
            limit: Maximum number of characters to return
            filters: Optional metadata filters (e.g., {"gender": "Female"})

        Returns:
            List of character dictionaries with character_id included

        Example:
            >>> characters = storage.list_characters(
            ...     limit=10,
            ...     filters={"gender": "Female"}
            ... )
        """
        try:
            # Build where clause for filtering
            where = filters if filters else None

            result = self.collection.get(
                limit=limit,
                where=where,
                include=["metadatas"]
            )

            characters = []
            for idx, character_id in enumerate(result["ids"]):
                metadata = result["metadatas"][idx]
                character = json.loads(metadata["character_json"])
                character["character_id"] = character_id
                characters.append(character)

            print(f"[CHARACTER STORAGE] Listed {len(characters)} characters")
            return characters

        except Exception as e:
            print(f"[CHARACTER STORAGE ERROR] Failed to list characters: {e}")
            return []

    def search_characters(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search characters by semantic similarity.

        Args:
            query: Search query (e.g., "friendly female engineer")
            limit: Maximum number of results
            filters: Optional metadata filters

        Returns:
            List of character dictionaries with relevance scores

        Example:
            >>> results = storage.search_characters(
            ...     query="humorous co-worker",
            ...     limit=5
            ... )
        """
        try:
            where = filters if filters else None

            result = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=where,
                include=["metadatas", "distances"]
            )

            characters = []
            if result["ids"] and result["ids"][0]:
                for idx, character_id in enumerate(result["ids"][0]):
                    metadata = result["metadatas"][0][idx]
                    character = json.loads(metadata["character_json"])
                    character["character_id"] = character_id
                    character["relevance_score"] = 1 - (result["distances"][0][idx] if result["distances"] else 0)
                    characters.append(character)

            print(f"[CHARACTER STORAGE] Found {len(characters)} characters for query: '{query}'")
            return characters

        except Exception as e:
            print(f"[CHARACTER STORAGE ERROR] Failed to search characters: {e}")
            return []

    def delete_character(self, character_id: str) -> bool:
        """
        Delete a character by ID.

        Args:
            character_id: UUID of the character

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            self.collection.delete(ids=[character_id])
            print(f"[CHARACTER STORAGE] Deleted character: {character_id}")
            return True
        except Exception as e:
            print(f"[CHARACTER STORAGE ERROR] Failed to delete character {character_id}: {e}")
            return False

    def update_character(self, character_id: str, character: Dict[str, Any]) -> bool:
        """
        Update a character profile.

        Args:
            character_id: UUID of the character
            character: Updated character data

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Delete old version
            self.delete_character(character_id)

            # Re-add with same ID
            document = f"""
            Name: {character.get('name', '')}
            Occupation: {character.get('occupation', '')}
            Age: {character.get('age', '')}
            Gender: {character.get('gender', '')}
            Relationship: {character.get('tags', {}).get('relationship', '')}
            Tone: {character.get('tags', {}).get('tone', '')}
            Characteristics: {character.get('tags', {}).get('characteristics', '')}
            Speaking Style: {character.get('speaking_style', '')}
            Appearance: {character.get('appearance', '')}
            """.strip()

            metadata = {
                "name": str(character.get("name", "")),
                "occupation": str(character.get("occupation", "")),
                "age": str(character.get("age", "")),
                "gender": str(character.get("gender", "")),
                "relationship": str(character.get("tags", {}).get("relationship", "")),
                "tone": str(character.get("tags", {}).get("tone", "")),
                "characteristics": str(character.get("tags", {}).get("characteristics", "")),
                "character_json": json.dumps(character, ensure_ascii=False)
            }

            self.collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[character_id]
            )

            print(f"[CHARACTER STORAGE] Updated character: {character_id}")
            return True

        except Exception as e:
            print(f"[CHARACTER STORAGE ERROR] Failed to update character {character_id}: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the character collection.

        Returns:
            Dictionary with collection statistics
        """
        try:
            count = self.collection.count()
            return {
                "total_characters": count,
                "collection_name": self.collection.name,
                "persist_directory": str(self.persist_directory)
            }
        except Exception as e:
            print(f"[CHARACTER STORAGE ERROR] Failed to get stats: {e}")
            return {"error": str(e)}
