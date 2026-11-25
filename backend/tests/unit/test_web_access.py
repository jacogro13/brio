from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from chatbot.adapters.llm.mock.mock_llm_adapter import MockLLMAdapter
from chatbot.adapters.web.mock import MockPageFetcher, MockWebSearch
from chatbot.domain.conversation.model import Conversation
from chatbot.services.conversation.send_message import SendMessageUseCase
from tests.unit.fakes import USER_ID, make_uow_factory

SYSTEM_PROMPT = "You are a helpful assistant."


def _conv() -> Conversation:
    return Conversation(id=uuid4(), title=None, messages=[], created_at=datetime.now(tz=UTC))


async def _collect(agen) -> list[dict]:
    return [event async for event in agen]


def _use_case(store):
    return SendMessageUseCase(
        make_uow_factory(store),
        MockLLMAdapter(),
        SYSTEM_PROMPT,
        web_search=MockWebSearch(),
        page_fetcher=MockPageFetcher(),
    )


@pytest.mark.asyncio
async def test_web_access_runs_tool_loop_and_persists_tool_events():
    conv = _conv()
    store = {conv.id: conv}
    uc = _use_case(store)

    # The mock LLM emits a tool_call when the message contains `[use web]`.
    events = await _collect(uc.stream(conv.id, USER_ID, "weather [use web]", web_access=True))

    types = [e["type"] for e in events]
    assert "tool_start" in types and "tool_end" in types
    assert types[-1] == "done"

    assistant = store[conv.id].messages[-1]
    assert assistant.role == "assistant"
    assert assistant.content  # a final answer was produced after the tool result
    assert assistant.tool_events and assistant.tool_events[0].tool == "web_search"
    assert assistant.tool_events[0].ok is True


@pytest.mark.asyncio
async def test_web_access_off_does_not_call_tools():
    conv = _conv()
    store = {conv.id: conv}
    uc = _use_case(store)

    events = await _collect(uc.stream(conv.id, USER_ID, "weather [use web]", web_access=False))

    # No tool events when the toggle is off, even with the `[use web]` marker.
    assert all(e["type"] not in ("tool_start", "tool_end") for e in events)
    assert store[conv.id].messages[-1].tool_events is None


@pytest.mark.asyncio
async def test_web_access_without_wired_tools_falls_back_to_plain_stream():
    conv = _conv()
    store = {conv.id: conv}
    # No web_search / page_fetcher injected → plain stream even if requested.
    uc = SendMessageUseCase(make_uow_factory(store), MockLLMAdapter(), SYSTEM_PROMPT)

    events = await _collect(uc.stream(conv.id, USER_ID, "hi", web_access=True))

    assert all(e["type"] not in ("tool_start", "tool_end") for e in events)
    assert store[conv.id].messages[-1].tool_events is None
