"""Character creation prompt templates."""

from .speaking_style import (
    SPEAKING_STYLE_SYSTEM_PROMPT,
    get_speaking_style_prompt
)
from .appearance import (
    APPEARANCE_SYSTEM_PROMPT,
    get_appearance_prompt
)

__all__ = [
    "SPEAKING_STYLE_SYSTEM_PROMPT",
    "get_speaking_style_prompt",
    "APPEARANCE_SYSTEM_PROMPT",
    "get_appearance_prompt",
]
