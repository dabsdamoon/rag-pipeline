"""
Routers package - FastAPI route handlers organized by domain
"""
from . import auth
from . import chat
from . import sources
from . import characters
from . import roleplay
from . import users
from . import history
from . import prompts

__all__ = [
    "auth",
    "chat",
    "sources",
    "characters",
    "roleplay",
    "users",
    "history",
    "prompts",
]
