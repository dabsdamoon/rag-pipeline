"""
Roleplay Router - Character-based roleplay chat
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
import uuid
import json

from schemas import RoleplayChatRequest, RoleplayChatResponse

router = APIRouter(prefix="/roleplay", tags=["Roleplay"])


# Dependencies will be injected by main.py
character_storage = None
roleplay_manager = None


def set_roleplay_services(storage, manager):
    """Set the character storage and roleplay manager instances"""
    global character_storage, roleplay_manager
    character_storage = storage
    roleplay_manager = manager


@router.post("/chat", response_model=RoleplayChatResponse)
async def roleplay_chat(request: RoleplayChatRequest):
    """
    Chat with a character in roleplay mode (non-streaming).

    This endpoint:
    1. Retrieves the character from ChromaDB
    2. Formats the roleplay prompt with character data and conversation history
    3. Aggregates with system roleplay prompt
    4. Sends to LLM and returns response
    5. Saves the conversation turn
    """
    try:
        # Get character from storage
        character = character_storage.get_character(request.character_id)
        if not character:
            raise HTTPException(status_code=404, detail=f"Character not found: {request.character_id}")

        # Generate or use existing session ID
        session_id = request.session_id or f"roleplay_{uuid.uuid4()}"

        # Chat with character
        response_data = await roleplay_manager.chat(
            character=character,
            message=request.message,
            session_id=session_id,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False
        )

        return RoleplayChatResponse(
            response=response_data["response"],
            session_id=response_data["session_id"],
            character_name=response_data["character_name"],
            tokens_used=response_data.get("tokens_used", {})
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ROLEPLAY ERROR] Chat failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Roleplay chat failed: {str(e)}")


@router.post("/chat/stream")
async def roleplay_chat_stream(request: RoleplayChatRequest):
    """
    Chat with a character in roleplay mode with streaming response.

    This endpoint:
    1. Retrieves the character from ChromaDB
    2. Formats the roleplay prompt with character data and conversation history
    3. Aggregates with system roleplay prompt
    4. Streams LLM response in real-time (SSE format)
    5. Saves the conversation turn after streaming completes
    """
    print(f"📨 Received roleplay streaming chat request for character: {request.character_id}")

    try:
        # Get character from storage
        character = character_storage.get_character(request.character_id)
        if not character:
            raise HTTPException(status_code=404, detail=f"Character not found: {request.character_id}")

        # Generate or use existing session ID
        session_id = request.session_id or f"roleplay_{uuid.uuid4()}"

        # Get stream from roleplay manager
        response_data = await roleplay_manager.chat(
            character=character,
            message=request.message,
            session_id=session_id,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True
        )

        async def generate():
            try:
                accumulated_chunks: List[str] = []

                # Stream content from OpenAI chunks in SSE format
                async for chunk in response_data["stream"]:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        accumulated_chunks.append(content)
                        yield f"data: {content}\n\n"

                # Save conversation after streaming completes
                final_response = "".join(accumulated_chunks).strip()
                if final_response:
                    roleplay_manager.save_turn_external(
                        session_id=session_id,
                        user_message=request.message,
                        assistant_message=final_response,
                        character_name=character.get("name", "Character")
                    )
                    print(f"[ROLEPLAY] Saved streaming conversation turn for session: {session_id}")

            except Exception as e:
                import traceback
                error_msg = f"Stream generation error: {str(e)}"
                print(error_msg)
                print(traceback.format_exc())
                error_data = f"data: {json.dumps({'error': str(e)})}\n\n"
                yield error_data

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Roleplay chat stream error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}")
async def get_roleplay_history(session_id: str, limit: Optional[int] = None):
    """
    Get conversation history for a roleplay session.
    """
    try:
        history = roleplay_manager.get_conversation_history(session_id, limit)
        return {
            "session_id": session_id,
            "history": history,
            "turn_count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.delete("/history/{session_id}")
async def clear_roleplay_history(session_id: str):
    """
    Clear conversation history for a roleplay session.
    """
    try:
        success = roleplay_manager.clear_conversation(session_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return {"message": f"Cleared history for session: {session_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear history: {str(e)}")
