"""
Authentication Router - User registration, login, profile management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import hashlib
import secrets
import uuid
from datetime import datetime as dt

from databases import get_db
from models import User, UserProfile, ConversationHistory
from schemas import (
    UserAuthResponse,
    UserRegisterRequest,
    UserLoginRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
    ConversationHistoryListResponse,
    ConversationHistoryResponse
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================================
# Password Hashing Utilities
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    try:
        salt, pwd_hash = hashed.split('$')
        return hashlib.sha256((password + salt).encode()).hexdigest() == pwd_hash
    except:
        return False


# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/register", response_model=UserAuthResponse)
async def register_user(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user with username and password (local SQLite)."""
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == request.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail=f"Username '{request.username}' already exists")

        # Check if user_handle already exists (if provided)
        if request.user_handle:
            existing_handle = db.query(User).filter(User.user_handle == request.user_handle).first()
            if existing_handle:
                raise HTTPException(status_code=400, detail=f"User handle '{request.user_handle}' already exists")

        # Create new user
        user_uuid = str(uuid.uuid4())
        hashed_pwd = hash_password(request.password)

        new_user = User(
            uuid=user_uuid,
            username=request.username,
            password_hash=hashed_pwd,
            user_handle=request.user_handle,
            created_at=dt.utcnow()
        )
        db.add(new_user)

        # Create user profile
        new_profile = UserProfile(
            user_uuid=user_uuid,
            name=request.name,
            age=request.age,
            email=request.email
        )
        db.add(new_profile)

        db.commit()
        db.refresh(new_user)

        return UserAuthResponse(
            uuid=new_user.uuid,
            username=new_user.username,
            user_handle=new_user.user_handle,
            created_at=new_user.created_at.isoformat(),
            last_login=None,
            message="User registered successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to register user: {str(e)}")


@router.post("/login", response_model=UserAuthResponse)
async def login_user(request: UserLoginRequest, db: Session = Depends(get_db)):
    """Login with username and password (local SQLite)."""
    try:
        # Find user by username
        user = db.query(User).filter(User.username == request.username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Update last login
        user.last_login = dt.utcnow()
        db.commit()
        db.refresh(user)

        return UserAuthResponse(
            uuid=user.uuid,
            username=user.username,
            user_handle=user.user_handle,
            created_at=user.created_at.isoformat(),
            last_login=user.last_login.isoformat() if user.last_login else None,
            message="Login successful"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.get("/profile/{user_uuid}", response_model=UserProfileResponse)
async def get_user_profile(user_uuid: str, db: Session = Depends(get_db)):
    """Get user profile with conversation count."""
    try:
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        profile = db.query(UserProfile).filter(UserProfile.user_uuid == user_uuid).first()
        conversation_count = db.query(ConversationHistory).filter(
            ConversationHistory.user_uuid == user_uuid
        ).count()

        return UserProfileResponse(
            uuid=user.uuid,
            username=user.username,
            user_handle=user.user_handle,
            name=profile.name if profile else None,
            age=profile.age if profile else None,
            email=profile.email if profile else None,
            created_at=user.created_at.isoformat(),
            conversation_count=conversation_count
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}")


@router.put("/profile/{user_uuid}", response_model=UserProfileResponse)
async def update_user_profile(
    user_uuid: str,
    request: UserProfileUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update user profile information."""
    try:
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        profile = db.query(UserProfile).filter(UserProfile.user_uuid == user_uuid).first()
        if not profile:
            # Create profile if it doesn't exist
            profile = UserProfile(user_uuid=user_uuid)
            db.add(profile)

        # Update profile fields
        if request.name is not None:
            profile.name = request.name
        if request.age is not None:
            profile.age = request.age
        if request.email is not None:
            profile.email = request.email
        if request.user_handle is not None:
            # Check if handle is already taken
            existing_handle = db.query(User).filter(
                User.user_handle == request.user_handle,
                User.uuid != user_uuid
            ).first()
            if existing_handle:
                raise HTTPException(status_code=400, detail=f"User handle '{request.user_handle}' already exists")
            user.user_handle = request.user_handle

        profile.updated_at = dt.utcnow()
        db.commit()
        db.refresh(user)
        db.refresh(profile)

        conversation_count = db.query(ConversationHistory).filter(
            ConversationHistory.user_uuid == user_uuid
        ).count()

        return UserProfileResponse(
            uuid=user.uuid,
            username=user.username,
            user_handle=user.user_handle,
            name=profile.name,
            age=profile.age,
            email=profile.email,
            created_at=user.created_at.isoformat(),
            conversation_count=conversation_count
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@router.get("/history/{user_uuid}", response_model=ConversationHistoryListResponse)
async def get_user_conversation_history(
    user_uuid: str,
    limit: int = 50,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get conversation history for a user."""
    try:
        # Verify user exists
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Query conversations
        query = db.query(ConversationHistory).filter(ConversationHistory.user_uuid == user_uuid)

        if session_id:
            query = query.filter(ConversationHistory.session_id == session_id)

        query = query.order_by(ConversationHistory.timestamp.desc()).limit(limit)
        conversations = query.all()

        conversation_responses = [
            ConversationHistoryResponse(
                conversation_uuid=conv.conversation_uuid,
                user_uuid=conv.user_uuid,
                session_id=conv.session_id,
                user_message=conv.user_message,
                assistant_message=conv.assistant_message,
                domain=conv.domain,
                language=conv.language,
                timestamp=conv.timestamp.isoformat()
            )
            for conv in conversations
        ]

        return ConversationHistoryListResponse(
            conversations=conversation_responses,
            total_count=len(conversation_responses),
            user_uuid=user_uuid
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")


@router.delete("/history/{user_uuid}")
async def delete_user_conversation_history(
    user_uuid: str,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Delete conversation history for a user."""
    try:
        # Verify user exists
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Delete conversations
        query = db.query(ConversationHistory).filter(ConversationHistory.user_uuid == user_uuid)

        if session_id:
            query = query.filter(ConversationHistory.session_id == session_id)

        deleted_count = query.delete()
        db.commit()

        message = f"Deleted {deleted_count} conversation(s)"
        if session_id:
            message += f" for session {session_id}"

        return {"message": message, "deleted_count": deleted_count}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation history: {str(e)}")
