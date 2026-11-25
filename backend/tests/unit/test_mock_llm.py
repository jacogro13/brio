import pytest

from chatbot.adapters.llm.mock.mock_llm_adapter import MockLLMAdapter
from chatbot.domain.conversation.ports.chat_llm import ChatParams


@pytest.mark.asyncio
async def test_mock_llm_yields_tokens_and_thinking_when_enabled():
    adapter = MockLLMAdapter()
    params = ChatParams(enable_thinking=True)
    chunks = [chunk async for chunk in adapter.stream_chat([], "You are helpful.", params)]

    tokens = [c.content for c in chunks if c.kind == "token"]
    thinking = [c.content for c in chunks if c.kind == "thinking"]

    assert "".join(tokens).strip()
    assert "".join(thinking).strip()
    # thinking is emitted before the answer
    kinds = [c.kind for c in chunks]
    assert kinds.index("thinking") < kinds.index("token")


@pytest.mark.asyncio
async def test_mock_llm_suppresses_thinking_when_disabled():
    adapter = MockLLMAdapter()
    params = ChatParams(enable_thinking=False)
    chunks = [chunk async for chunk in adapter.stream_chat([], "You are helpful.", params)]

    assert [c.kind for c in chunks] and all(c.kind == "token" for c in chunks)
