from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from chatbot.adapters.llm.openai.openai_llm_adapter import _ThinkTagSplitter
from chatbot.domain.conversation.model import Conversation
from chatbot.services.conversation.send_message import SendMessageUseCase
from tests.unit.fakes import USER_ID, FakeLLM, make_uow_factory

SYSTEM_PROMPT = "You are a helpful assistant."


def _conv() -> Conversation:
    return Conversation(id=uuid4(), title=None, messages=[], created_at=datetime.now(tz=UTC))


async def _collect(agen) -> list[dict]:
    return [event async for event in agen]


@pytest.mark.asyncio
async def test_thinking_events_streamed_and_persisted_not_replayed():
    conv = _conv()
    store = {conv.id: conv}
    llm = FakeLLM(tokens=["Hel", "lo"], thinking=["Think", "ing"])
    uc = SendMessageUseCase(make_uow_factory(store), llm, SYSTEM_PROMPT)

    events = await _collect(uc.stream(conv.id, USER_ID, "hi"))

    assert [e["type"] for e in events] == [
        "thinking",
        "thinking",
        "token",
        "token",
        "done",
    ]
    assert "".join(e["content"] for e in events if e["type"] == "thinking") == "Thinking"

    assistant = store[conv.id].messages[-1]
    assert assistant.role == "assistant"
    assert assistant.content == "Hello"
    assert assistant.thinking == "Thinking"
    # thinking is never sent back to the LLM as history (only role/content)
    assert llm.last_history == [{"role": "user", "content": "hi"}]


def _split(splitter: _ThinkTagSplitter, *chunks: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for c in chunks:
        out.extend(splitter.feed(c))
    out.extend(splitter.flush())
    return out


def test_think_splitter_inline_tags():
    out = _split(_ThinkTagSplitter(), "<think>reason</think>answer")
    assert out == [("thinking", "reason"), ("token", "answer")]


def test_think_splitter_tag_across_chunk_boundary():
    # `<think>` and `</think>` arrive split across chunk boundaries
    out = _split(_ThinkTagSplitter(), "<thi", "nk>rea", "son</thi", "nk>done")
    joined_thinking = "".join(t for k, t in out if k == "thinking")
    joined_tokens = "".join(t for k, t in out if k == "token")
    assert joined_thinking == "reason"
    assert joined_tokens == "done"


def test_think_splitter_plain_content_passthrough():
    out = _split(_ThinkTagSplitter(), "just ", "a normal ", "reply")
    assert all(k == "token" for k, _ in out)
    assert "".join(t for _, t in out) == "just a normal reply"
