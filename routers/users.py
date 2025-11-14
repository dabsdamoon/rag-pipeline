"""
Users Router - Firebase-based user management
"""
from fastapi import APIRouter, HTTPException

from schemas import (
    UserCreateRequest,
    UserResponse,
    UserProfileResponse,
    UserUpdateRequest
)

router = APIRouter(prefix="/users", tags=["Users"])


# Dependencies will be injected by main.py
firebase_service = None


def set_firebase_service(service):
    """Set the Firebase service instance"""
    global firebase_service
    firebase_service = service


@router.post("/", response_model=UserResponse)
async def create_user(request: UserCreateRequest):
    """Create a new user profile (no authentication required for demo)"""
    try:
        user_data = firebase_service.create_user(
            user_id=request.user_id,
            name=request.name,
            age=request.age
        )
        return UserResponse(**user_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(user_id: str):
    """Get user profile and conversation statistics"""
    try:
        user_data = firebase_service.get_user(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Get conversation count
        conversations = firebase_service.get_user_conversations(user_id, limit=1000)

        return UserProfileResponse(
            user=UserResponse(**user_data),
            conversation_count=len(conversations)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user profile: {str(e)}")


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_profile(user_id: str, request: UserUpdateRequest):
    """Update user profile information"""
    try:
        # First check if user exists
        user_data = firebase_service.get_user(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user
        success = firebase_service.update_user(
            user_id=user_id,
            name=request.name,
            age=request.age
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update user")

        # Get updated user data
        updated_user = firebase_service.get_user(user_id)
        return UserResponse(**updated_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")
