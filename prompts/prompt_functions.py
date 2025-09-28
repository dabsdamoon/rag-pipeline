"""Legacy prompt helper kept for backward compatibility.

The modern pipeline composes prompts via :mod:`prompts.prompt_manager`. This
module now exposes thin wrappers so existing imports continue to work while
delegating to the layered prompt manager.
"""

from __future__ import annotations

from typing import Dict, List, Optional

try:
    from .prompt_manager import PromptManager

    _manager = PromptManager()
except ModuleNotFoundError:  # PyYAML not installed; legacy functions will fail clearly
    _manager = None


def get_system_prompt(language: str = "English", **_: Dict) -> str:
    if _manager is None:
        raise ModuleNotFoundError("PyYAML is required to build prompts.")
    system_prompt, _user_prompt, _ = _manager.build_prompt_messages(
        query="", language=language, domain="books"
    )
    return system_prompt


def get_books_prompt(
    question: str,
    language: str = "English",
    context_docs: Optional[List[Dict]] = None,
    source_metadata: Optional[Dict[str, Dict]] = None,
) -> str:
    if _manager is None:
        raise ModuleNotFoundError("PyYAML is required to build prompts.")
    _system, user_prompt, _ = _manager.build_prompt_messages(
        query=question,
        language=language,
        context_docs=context_docs,
        domain="books",
        source_metadata=source_metadata,
    )
    return user_prompt


def get_insurance_prompt(
    question: str,
    language: str = "English",
    context_docs: Optional[List[Dict]] = None,
    source_metadata: Optional[Dict[str, Dict]] = None,
) -> str:
    if _manager is None:
        raise ModuleNotFoundError("PyYAML is required to build prompts.")
    _system, user_prompt, _ = _manager.build_prompt_messages(
        query=question,
        language=language,
        context_docs=context_docs,
        domain="insurance",
        source_metadata=source_metadata,
    )
    return user_prompt


PROMPT_FUNCTIONS = {
    "system": get_system_prompt,
    "books": get_books_prompt,
    "insurance": get_insurance_prompt,
}
