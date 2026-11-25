from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from chatbot.domain.conversation.model import Conversation
from chatbot.services.conversation._streaming import resolve_chat_config
from chatbot.services.conversation.language import apply_language


def _conv(**overrides) -> Conversation:
    return Conversation(
        id=uuid4(),
        title="t",
        messages=[],
        created_at=datetime.now(tz=UTC),
        **overrides,
    )


@pytest.mark.parametrize(
    "language, expected_suffix",
    [
        ("en", ""),
        ("fr", ""),  # unknown code → no directive
        ("it", "\n\nRispondi sempre in italiano."),
        ("de", "\n\nAntworte immer auf Deutsch."),
    ],
)
def test_apply_language_appends_directive(language, expected_suffix):
    assert apply_language("You are helpful.", language) == "You are helpful." + expected_suffix


def test_resolve_chat_config_uses_default_prompt_with_language():
    prompt, _ = resolve_chat_config(_conv(), "Base prompt.", False, language="it")
    assert prompt == "Base prompt.\n\nRispondi sempre in italiano."


def test_resolve_chat_config_language_composes_with_override():
    # A per-conversation override governs persona; the language directive is
    # still appended after it.
    conv = _conv(system_prompt_override="Speak like a pirate.")
    prompt, _ = resolve_chat_config(conv, "Base.", False, language="de")
    assert prompt == "Speak like a pirate.\n\nAntworte immer auf Deutsch."


def test_resolve_chat_config_english_is_noop():
    conv = _conv(system_prompt_override="Custom.")
    prompt, _ = resolve_chat_config(conv, "Base.", False, language="en")
    assert prompt == "Custom."


def test_resolve_chat_config_defaults_to_english():
    prompt, _ = resolve_chat_config(_conv(), "Base.", False)
    assert prompt == "Base."
