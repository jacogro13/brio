"""Assistant reply language directives.

The user's language preference (``users.language``, one of ``en``/``it``/``de``)
is turned into a short instruction appended to the resolved system prompt so the
model answers in that language. English is the default and needs no directive.
A per-conversation ``system_prompt_override`` still governs tone/persona — the
directive is appended after it, so language is honored without clobbering it.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "en"

# Codes we accept everywhere (API validation, CLI, frontend switcher).
SUPPORTED_LANGUAGES = ("en", "it", "de")

_DIRECTIVES: dict[str, str] = {
    "it": "Rispondi sempre in italiano.",
    "de": "Antworte immer auf Deutsch.",
}


def apply_language(system_prompt: str, language: str) -> str:
    """Return ``system_prompt`` with the language directive appended, or
    unchanged for English / unknown codes."""
    directive = _DIRECTIVES.get(language)
    if directive is None:
        return system_prompt
    return system_prompt.rstrip() + "\n\n" + directive
