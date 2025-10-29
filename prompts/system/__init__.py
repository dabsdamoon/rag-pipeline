from .general import SYSTEM_GENERAL_PROMPT
from .roleplay import SYSTEM_ROLEPLAY_PROMPT

# Default to generic prompt
SYSTEM_PROMPT = SYSTEM_GENERAL_PROMPT

# Available system prompt options
DICT_SYSTEM_PROMPTS = {
    "generic": SYSTEM_GENERAL_PROMPT,
    "roleplay": SYSTEM_ROLEPLAY_PROMPT,
}
