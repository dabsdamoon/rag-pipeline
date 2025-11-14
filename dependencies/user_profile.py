"""
User Profile Dependency - FastAPI dependency for enriching chat requests with user profiles

This module provides a reusable dependency that fetches user profile data and enriches
the layer_config for chat requests, eliminating duplicate code across chat endpoints.
"""
from typing import Dict, Any, Optional
from fastapi import Depends
from sqlalchemy.orm import Session, joinedload

from databases import get_db
from models import User, UserProfile


def enrich_with_user_profile(
    user_id: Optional[str],
    layer_config: Optional[Dict[str, Any]],
    db: Session
) -> Dict[str, Any]:
    """
    Enrich layer_config with user profile information if user_id is provided.

    This helper function:
    1. Checks if a user_id is provided
    2. Queries the database for the user and their profile in a single query (using joinedload)
    3. Enriches the layer_config with user information if profile exists
    4. Returns the enriched (or original) layer_config

    Args:
        user_id: Optional UUID of the user
        layer_config: Optional configuration dict for prompt layers
        db: Database session

    Returns:
        Dictionary with enriched layer configuration
    """
    enriched_config = layer_config or {}

    if not user_id:
        return enriched_config

    try:
        # Optimized query: fetch user and profile in single query using joinedload
        user = db.query(User).options(
            joinedload(User.profile)
        ).filter(User.uuid == user_id).first()

        if user and user.profile:
            # Add user layer to prompt with profile info
            enriched_config["user"] = {
                "include": True,
                "id": "default",
                "variables": {
                    "name": user.profile.name or "User",
                    "age": str(user.profile.age) if user.profile.age else "Not specified",
                }
            }
            print(f"[PROFILE] Using user profile for {user.username}")
    except Exception as e:
        print(f"[PROFILE WARNING] Could not fetch user profile: {e}")

    return enriched_config


def get_user_profile_info(
    user_id: str,
    db: Session = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """
    Get user profile information as a dictionary.

    This is a simpler dependency for cases where you just need the profile data
    without layer_config enrichment.

    Args:
        user_id: UUID of the user
        db: Database session (injected by FastAPI)

    Returns:
        Dictionary with user profile data, or None if not found
    """
    try:
        user = db.query(User).options(
            joinedload(User.profile)
        ).filter(User.uuid == user_id).first()

        if user and user.profile:
            return {
                "uuid": user.uuid,
                "username": user.username,
                "name": user.profile.name,
                "age": user.profile.age,
                "email": user.profile.email,
            }
    except Exception as e:
        print(f"[PROFILE WARNING] Could not fetch user profile: {e}")

    return None
