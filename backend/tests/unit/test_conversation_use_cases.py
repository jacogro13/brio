from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from chatbot.domain.conversation.model import (
    Conversation,
    ConversationNotFound,
    Message,
    Role,
)
from chatbot.services.conversation.edit_message import EditMessageUseCase
from chatbot.services.conversation.regenerate_message import RegenerateMessageUseCase
from chatbot.services.conversation.send_message import SendMessageUseCase
from chatbot.services.conversation.update_conversation import UpdateConversationUseCase
from tests.unit.fakes import USER_ID, FakeLLM, make_uow_factory

SYSTEM_PROMPT = "You are a helpful assistant."


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _msg(role: Role, content: str) -> Message:
    return Message(id=uuid4(), role=role, content=content, created_at=_now())


def _conv(messages: list[Message] | None = None, title: str | None = None) -> Conversation:
    return Conversation(id=uuid4(), title=title, messages=messages or [], created_at=_now())


async def _collect(agen) -> list[dict]:
    return [event async for event in agen]


@pytest.mark.asyncio
async def test_send_message_event_shapes_and_persist():
    conv = _conv()
    store = {conv.id: conv}
    llm = FakeLLM(["Hel", "lo"])
    uc = SendMessageUseCase(make_uow_factory(store), llm, SYSTEM_PROMPT)

    events = await _collect(uc.stream(conv.id, USER_ID, "hi there"))

    assert [e["type"] for e in events] == ["token", "token", "done"]
    assert [e["content"] for e in events if e["type"] == "token"] == ["Hel", "lo"]
    done = events[-1]
    assert done["type"] == "done"
    assert done["message_id"] is not None
    UUID(done["message_id"])  # parseable

    # user + assistant persisted, title auto-set from first user message
    assert [(m.role, m.content) for m in store[conv.id].messages] == [
        ("user", "hi there"),
        ("assistant", "Hello"),
    ]
    assert store[conv.id].title == "hi there"
    # history sent to the LLM is just the new user turn (no prior messages)
    assert llm.last_history == [{"role": "user", "content": "hi there"}]


@pytest.mark.asyncio
async def test_send_message_unknown_conversation_yields_error():
    store: dict = {}
    uc = SendMessageUseCase(make_uow_factory(store), FakeLLM(["x"]), SYSTEM_PROMPT)

    events = await _collect(uc.stream(uuid4(), USER_ID, "hi"))

    assert events == [
        {"type": "error", "code": "conversation_not_found", "message": "conversation not found"}
    ]


@pytest.mark.asyncio
async def test_send_message_partial_persist_on_aclose():
    conv = _conv()
    store = {conv.id: conv}
    llm = FakeLLM(["a", "b", "c"])
    uc = SendMessageUseCase(make_uow_factory(store), llm, SYSTEM_PROMPT)

    agen = uc.stream(conv.id, USER_ID, "hi")
    first = await agen.__anext__()
    second = await agen.__anext__()
    assert (first["content"], second["content"]) == ("a", "b")
    await agen.aclose()  # client disconnect mid-stream

    # the finally-UoW persisted the partial assistant reply ("ab")
    assert [(m.role, m.content) for m in store[conv.id].messages] == [
        ("user", "hi"),
        ("assistant", "ab"),
    ]


@pytest.mark.asyncio
async def test_regenerate_drops_trailing_assistant_and_restreams():
    user = _msg("user", "question")
    assistant = _msg("assistant", "old answer")
    conv = _conv([user, assistant], title="question")
    store = {conv.id: conv}
    llm = FakeLLM(["new ", "answer"])
    uc = RegenerateMessageUseCase(make_uow_factory(store), llm, SYSTEM_PROMPT)

    events = await _collect(uc.stream(conv.id, USER_ID))

    assert [e["type"] for e in events] == ["token", "token", "done"]
    assert [(m.role, m.content) for m in store[conv.id].messages] == [
        ("user", "question"),
        ("assistant", "new answer"),
    ]
    # regenerated from the history ending at the last user turn
    assert llm.last_history == [{"role": "user", "content": "question"}]


@pytest.mark.asyncio
async def test_regenerate_with_no_user_message_errors():
    conv = _conv([_msg("assistant", "orphan")])
    store = {conv.id: conv}
    uc = RegenerateMessageUseCase(make_uow_factory(store), FakeLLM(["x"]), SYSTEM_PROMPT)

    events = await _collect(uc.stream(conv.id, USER_ID))

    assert events == [
        {"type": "error", "code": "nothing_to_regenerate", "message": "nothing to regenerate"}
    ]


@pytest.mark.asyncio
async def test_edit_message_truncates_and_restreams():
    user1 = _msg("user", "first")
    assistant1 = _msg("assistant", "reply one")
    user2 = _msg("user", "second")
    assistant2 = _msg("assistant", "reply two")
    conv = _conv([user1, assistant1, user2, assistant2], title="first")
    store = {conv.id: conv}
    llm = FakeLLM(["edited ", "reply"])
    uc = EditMessageUseCase(make_uow_factory(store), llm, SYSTEM_PROMPT)

    events = await _collect(uc.stream(conv.id, USER_ID, user2.id, "second (edited)"))

    assert [e["type"] for e in events] == ["token", "token", "done"]
    # everything from user2 onward replaced; user1/assistant1 kept
    assert [(m.role, m.content) for m in store[conv.id].messages] == [
        ("user", "first"),
        ("assistant", "reply one"),
        ("user", "second (edited)"),
        ("assistant", "edited reply"),
    ]
    assert llm.last_history == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply one"},
        {"role": "user", "content": "second (edited)"},
    ]


@pytest.mark.asyncio
async def test_edit_nonexistent_message_errors():
    conv = _conv([_msg("user", "hi")])
    store = {conv.id: conv}
    uc = EditMessageUseCase(make_uow_factory(store), FakeLLM(["x"]), SYSTEM_PROMPT)

    events = await _collect(uc.stream(conv.id, USER_ID, uuid4(), "new"))

    assert events == [
        {"type": "error", "code": "message_not_found", "message": "message not found"}
    ]


@pytest.mark.asyncio
async def test_edit_assistant_message_rejected():
    user = _msg("user", "hi")
    assistant = _msg("assistant", "hello")
    conv = _conv([user, assistant])
    store = {conv.id: conv}
    uc = EditMessageUseCase(make_uow_factory(store), FakeLLM(["x"]), SYSTEM_PROMPT)

    events = await _collect(uc.stream(conv.id, USER_ID, assistant.id, "new"))

    assert events == [
        {"type": "error", "code": "message_not_found", "message": "message not found"}
    ]


@pytest.mark.asyncio
async def test_update_conversation_renames():
    conv = _conv(title="old")
    store = {conv.id: conv}
    uc = UpdateConversationUseCase(make_uow_factory(store))

    result = await uc.execute(conv.id, USER_ID, {"title": "new title"})

    assert result is not None
    assert result.title == "new title"
    assert store[conv.id].title == "new title"


@pytest.mark.asyncio
async def test_update_conversation_partial_settings():
    conv = _conv(title="keep")
    store = {conv.id: conv}
    uc = UpdateConversationUseCase(make_uow_factory(store))

    # Only the provided keys are applied; title (omitted) is untouched.
    result = await uc.execute(
        conv.id,
        USER_ID,
        {"temperature": 0.0, "max_tokens": 256},
    )

    assert result is not None
    assert result.title == "keep"
    assert store[conv.id].temperature == 0.0  # 0 kept, not treated as unset
    assert store[conv.id].max_tokens == 256
    assert store[conv.id].system_prompt_override is None


@pytest.mark.asyncio
async def test_update_conversation_resets_setting_to_none():
    conv = _conv(title="t")
    conv.temperature = 1.5
    store = {conv.id: conv}
    uc = UpdateConversationUseCase(make_uow_factory(store))

    result = await uc.execute(conv.id, USER_ID, {"temperature": None})

    assert result is not None
    assert store[conv.id].temperature is None


@pytest.mark.asyncio
async def test_update_unknown_conversation_is_not_found():
    uc = UpdateConversationUseCase(make_uow_factory({}))

    with pytest.raises(ConversationNotFound):
        await uc.execute(uuid4(), USER_ID, {"title": "x"})


@pytest.mark.asyncio
async def test_conversation_overrides_reach_the_llm():
    conv = _conv(title="q")
    conv.temperature = 0.0
    conv.max_tokens = 128
    conv.system_prompt_override = "Be terse."
    store = {conv.id: conv}
    llm = FakeLLM(["ok"])
    uc = SendMessageUseCase(make_uow_factory(store), llm, SYSTEM_PROMPT)

    # Thinking is a per-turn value now, passed on the stream call (not stored).
    await _collect(uc.stream(conv.id, USER_ID, "hi", enable_thinking=True))

    assert llm.last_system_prompt == "Be terse."
    assert llm.last_params is not None
    assert llm.last_params.temperature == 0.0  # explicit 0 override honoured
    assert llm.last_params.max_tokens == 128
    assert llm.last_params.enable_thinking is True


@pytest.mark.asyncio
async def test_defaults_used_when_no_overrides():
    conv = _conv(title="q")
    store = {conv.id: conv}
    llm = FakeLLM(["ok"])
    uc = SendMessageUseCase(make_uow_factory(store), llm, SYSTEM_PROMPT, enable_thinking=True)

    await _collect(uc.stream(conv.id, USER_ID, "hi"))

    assert llm.last_system_prompt == SYSTEM_PROMPT
    assert llm.last_params is not None
    assert llm.last_params.temperature is None  # unset → adapter omits it
    assert llm.last_params.max_tokens is None
    assert llm.last_params.enable_thinking is True  # server default


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start_stream",
    [
        lambda f: SendMessageUseCase(f, FakeLLM(["x"]), SYSTEM_PROMPT).stream(
            uuid4(), USER_ID, "hi"
        ),
        lambda f: RegenerateMessageUseCase(f, FakeLLM(["x"]), SYSTEM_PROMPT).stream(
            uuid4(), USER_ID
        ),
        lambda f: EditMessageUseCase(f, FakeLLM(["x"]), SYSTEM_PROMPT).stream(
            uuid4(), USER_ID, uuid4(), "new"
        ),
    ],
    ids=["send", "regenerate", "edit"],
)
async def test_stream_error_for_unknown_conversation_carries_code_and_message(start_stream):
    events = await _collect(start_stream(make_uow_factory({})))

    assert events == [
        {"type": "error", "code": "conversation_not_found", "message": "conversation not found"}
    ]
