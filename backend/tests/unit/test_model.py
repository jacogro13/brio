from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from chatbot.domain.conversation.model import Attachment, Conversation, Message, Role, ToolEvent
from chatbot.domain.errors import InvalidInput
from chatbot.domain.user.model import User


def _msg(role: Role, content: str) -> Message:
    return Message(id=uuid4(), role=role, content=content, created_at=datetime.now(tz=UTC))


def test_add_message_sets_title_from_first_user_message():
    conv = Conversation(id=uuid4(), title=None, messages=[], created_at=datetime.now(tz=UTC))
    conv.add_message(_msg("user", "Hello, how are you?"))
    assert conv.title == "Hello, how are you?"


def test_add_message_truncates_title_at_60_chars():
    long_content = "x" * 80
    conv = Conversation(id=uuid4(), title=None, messages=[], created_at=datetime.now(tz=UTC))
    conv.add_message(_msg("user", long_content))
    assert conv.title == "x" * 60


def test_add_message_does_not_override_existing_title():
    conv = Conversation(
        id=uuid4(), title="Existing title", messages=[], created_at=datetime.now(tz=UTC)
    )
    conv.add_message(_msg("user", "A new message"))
    assert conv.title == "Existing title"


def test_add_message_assistant_does_not_set_title():
    conv = Conversation(id=uuid4(), title=None, messages=[], created_at=datetime.now(tz=UTC))
    conv.add_message(_msg("assistant", "Some reply"))
    assert conv.title is None


def test_add_message_appends_to_messages():
    conv = Conversation(id=uuid4(), title=None, messages=[], created_at=datetime.now(tz=UTC))
    msg = _msg("user", "Hi")
    conv.add_message(msg)
    assert conv.messages == [msg]


# ── D1: fields are validated on creation and on every assignment ─────────────


def _user(**overrides) -> User:
    fields = {
        "id": uuid4(),
        "username": "alice",
        "hashed_password": "x",
        "created_at": datetime.now(tz=UTC),
    }
    return User(**(fields | overrides))


def test_unknown_role_is_rejected_on_creation():
    bad_role: Any = "system"

    with pytest.raises(InvalidInput) as excinfo:
        _msg(bad_role, "hi")

    assert excinfo.value.field == "role"


def test_unknown_role_is_rejected_on_assignment():
    message = _msg("user", "hi")
    bad_role: Any = "robot"

    with pytest.raises(InvalidInput) as excinfo:
        message.role = bad_role

    assert excinfo.value.field == "role"
    assert message.role == "user"


@pytest.mark.parametrize("role", ["user", "assistant"])
def test_known_roles_are_allowed(role):
    assert _msg(role, "hi").role == role


def test_unknown_language_is_rejected():
    with pytest.raises(InvalidInput) as excinfo:
        _user(language="fr")

    assert excinfo.value.field == "language"


@pytest.mark.parametrize("language", ["en", "it", "de"])
def test_known_languages_are_allowed(language):
    assert _user(language=language).language == language


@pytest.mark.parametrize("username", ["", "   "])
def test_blank_username_is_rejected(username):
    with pytest.raises(InvalidInput) as excinfo:
        _user(username=username)

    assert excinfo.value.field == "username"


def test_username_is_kept_as_typed():
    assert _user(username=" alice ").username == " alice "


@pytest.mark.parametrize(
    ("field", "value"),
    [("temperature", 2.5), ("temperature", -0.1), ("max_tokens", 0)],
)
def test_out_of_range_conversation_setting_is_rejected_on_assignment(field, value):
    conv = Conversation(id=uuid4(), title=None, messages=[], created_at=datetime.now(tz=UTC))

    with pytest.raises(InvalidInput) as excinfo:
        setattr(conv, field, value)

    assert excinfo.value.field == field


@pytest.mark.parametrize(
    ("field", "value"),
    [("temperature", 0.0), ("temperature", 2.0), ("max_tokens", 1), ("temperature", None)],
)
def test_in_range_conversation_setting_is_allowed(field, value):
    conv = Conversation(id=uuid4(), title=None, messages=[], created_at=datetime.now(tz=UTC))

    setattr(conv, field, value)

    assert getattr(conv, field) == value


@pytest.mark.parametrize(("field", "value"), [("filename", ""), ("size", -1)])
def test_invalid_attachment_field_is_rejected(field, value):
    fields = {
        "id": uuid4(),
        "conversation_id": uuid4(),
        "filename": "notes.txt",
        "content_type": "text/plain",
        "size": 3,
        "s3_key": "conversations/x/y/notes.txt",
        "created_at": datetime.now(tz=UTC),
    }

    with pytest.raises(InvalidInput) as excinfo:
        Attachment(**(fields | {field: value}))

    assert excinfo.value.field == field


@pytest.mark.parametrize(
    "record",
    [
        {
            "id": 0,
            "tool": "web_search",
            "query": "q",
            "ok": True,
            "summary": "1 result",
            "results": [{"title": "T", "url": "https://t.example"}],
        },
        {
            "id": 1,
            "tool": "fetch_page",
            "url": "https://x.example",
            "ok": False,
            "summary": "fetch error",
            "results": [],
        },
        {"id": 2, "tool": "web_search", "query": "stopped early"},
    ],
)
def test_tool_event_json_round_trips(record):
    assert ToolEvent.from_json(record).to_json() == record


def test_tool_event_with_bad_ok_is_rejected():
    with pytest.raises(InvalidInput) as excinfo:
        ToolEvent.from_json({"id": 0, "tool": "web_search", "ok": "maybe"})

    assert excinfo.value.field == "ok"
