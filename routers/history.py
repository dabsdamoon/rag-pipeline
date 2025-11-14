"""
History Router - Conversation history management (Firebase)
"""
from fastapi import APIRouter, HTTPException
from typing import Dict

from schemas import (
    ConversationSaveRequest,
    ConversationListRequest,
    ConversationListResponse,
    ConversationResponse,
    ConversationDeleteRequest,
    ConversationDeleteResponse,
    FirebaseStatusResponse
)

router = APIRouter(prefix="/conversations", tags=["History"])


# Dependencies will be injected by main.py
firebase_service = None


def set_firebase_service(service):
    """Set the Firebase service instance"""
    global firebase_service
    firebase_service = service


@router.post("/", response_model=Dict[str, str])
async def save_conversation(request: ConversationSaveRequest):
    """Save a conversation turn (normally called automatically by /chat endpoint)"""
    try:
        conversation_id = firebase_service.save_conversation(
            user_id=request.user_id,
            session_id=request.session_id,
            user_message=request.user_message,
            assistant_message=request.assistant_message,
            metadata=request.metadata
        )
        return {"conversation_id": conversation_id, "message": "Conversation saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save conversation: {str(e)}")


@router.post("/list", response_model=ConversationListResponse)
async def list_conversations(request: ConversationListRequest):
    """Get conversation history for a user"""
    try:
        conversations = firebase_service.get_user_conversations(
            user_id=request.user_id,
            limit=request.limit,
            session_id=request.session_id
        )

        conversation_responses = [
            ConversationResponse(
                id=conv.get("id", ""),
                user_id=conv["user_id"],
                session_id=conv["session_id"],
                user_message=conv["user_message"],
                assistant_message=conv["assistant_message"],
                metadata=conv.get("metadata"),
                timestamp=str(conv.get("timestamp", ""))
            )
            for conv in conversations
        ]

        return ConversationListResponse(
            conversations=conversation_responses,
            user_id=request.user_id,
            total_count=len(conversation_responses)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@router.post("/delete", response_model=ConversationDeleteResponse)
async def delete_conversations(request: ConversationDeleteRequest):
    """Delete conversation history for a user"""
    try:
        deleted_count = firebase_service.delete_user_conversations(
            user_id=request.user_id,
            session_id=request.session_id
        )

        message = f"Deleted {deleted_count} conversation(s)"
        if request.session_id:
            message += f" for session {request.session_id}"

        return ConversationDeleteResponse(
            user_id=request.user_id,
            deleted_count=deleted_count,
            message=message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete conversations: {str(e)}")


@router.get("/firebase/status", response_model=FirebaseStatusResponse)
async def firebase_status():
    """Check Firebase service status"""
    try:
        status = firebase_service.get_status()
        return FirebaseStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Firebase status: {str(e)}")
