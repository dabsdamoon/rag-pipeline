"""
Dependencies package - FastAPI dependency injection helpers
"""
from .user_profile import enrich_with_user_profile, get_user_profile_info

__all__ = [
    "enrich_with_user_profile",
    "get_user_profile_info",
]
