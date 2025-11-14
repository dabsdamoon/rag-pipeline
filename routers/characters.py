"""
Characters Router - Character creation and management
"""
from fastapi import APIRouter, HTTPException

from schemas import (
    AvailableTagsResponse,
    CharacterCreateRequest,
    CharacterResponse,
    CharacterSaveRequest,
    CharacterSaveResponse,
    CharacterListResponse
)

router = APIRouter(prefix="/character", tags=["Characters"])


# Dependencies will be injected by main.py
character_pipeline = None
character_storage = None


def set_character_services(pipeline, storage):
    """Set the character pipeline and storage instances"""
    global character_pipeline, character_storage
    character_pipeline = pipeline
    character_storage = storage


@router.get("/tags", response_model=AvailableTagsResponse)
async def get_available_tags():
    """Get all available character tags."""
    try:
        tags = character_pipeline.get_available_tags()
        return AvailableTagsResponse(**tags)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available tags: {str(e)}")


@router.post("/create", response_model=CharacterResponse)
async def create_character(request: CharacterCreateRequest):
    """
    Create a character with AI-generated speaking style and appearance.

    This endpoint uses LLM to generate detailed character descriptions based on
    the provided attributes (name, occupation, age, gender) and personality tags.

    Speaking style and appearance are generated in parallel for better performance.
    """
    try:
        character = await character_pipeline.create_character(
            name=request.name,
            occupation=request.occupation,
            age=request.age,
            gender=request.gender,
            tags=request.tags.model_dump(),
            model=request.model,
            temperature=request.temperature
        )

        return CharacterResponse(**character)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create character: {str(e)}")


@router.post("/save", response_model=CharacterSaveResponse)
async def save_character(request: CharacterSaveRequest):
    """
    Save a character profile to ChromaDB storage.

    This endpoint persists a character profile (typically created via /character/create)
    to ChromaDB for later retrieval and use in roleplay scenarios.
    """
    try:
        character_id = character_storage.save_character(request.character)
        return CharacterSaveResponse(
            character_id=character_id,
            message=f"Character '{request.character.get('name')}' saved successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save character: {str(e)}")


@router.get("/{character_id}")
async def get_character(character_id: str):
    """
    Retrieve a character profile by ID from ChromaDB.
    """
    try:
        character = character_storage.get_character(character_id)
        if not character:
            raise HTTPException(status_code=404, detail=f"Character not found: {character_id}")
        return character
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve character: {str(e)}")


@router.get("/list/all", response_model=CharacterListResponse)
async def list_characters(limit: int = 100):
    """
    List all saved characters from ChromaDB.
    """
    try:
        characters = character_storage.list_characters(limit=limit)
        return CharacterListResponse(
            characters=characters,
            total_count=len(characters)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list characters: {str(e)}")


@router.delete("/{character_id}")
async def delete_character(character_id: str):
    """
    Delete a character profile from ChromaDB.
    """
    try:
        success = character_storage.delete_character(character_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Character not found: {character_id}")
        return {"message": f"Character {character_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete character: {str(e)}")
