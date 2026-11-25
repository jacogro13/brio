from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from chatbot.domain.conversation.ports.chat_llm import ChatLLM, ChatParams, LlmChunk

_MOCK_THINKING = "Let me think about this. The user asked something, so I will reply."
_MOCK_REPLY = "This is a mock response. The LLM adapter is not configured."
_MOCK_WEB_REPLY = "Based on the search results, here is the answer with a source."

# Emitted (split across chunk boundaries on purpose, to exercise the tool_loop
# scanner's cross-chunk buffering) when a user message contains `[use web]` and
# no tool result is in history yet.
_TOOL_CALL_CHUNKS = [
    "```to",
    "ol_call\n",
    '{"name": "web_search", "arguments": {"query": "example"}}',
    "\n``",
    "`",
]


def _wants_web(messages: list[dict]) -> bool:
    """True when the latest user turn asks for web access (`[use web]` hook) and
    no `[tool_result ...]` turn is present yet — so the mock calls a tool exactly
    once, then answers on the follow-up invocation."""
    if any("[tool_result" in str(m.get("content", "")) for m in messages):
        return False
    for m in reversed(messages):
        if m.get("role") == "user":
            return "[use web]" in str(m.get("content", ""))
    return False


class MockLLMAdapter(ChatLLM):
    async def stream_chat(
        self, messages: list[dict], system_prompt: str, params: ChatParams
    ) -> AsyncIterator[LlmChunk]:
        # Web-tools test hook: emit one tool_call block, suppressed + executed by
        # the tool loop; the follow-up invocation (with the tool_result in
        # history) falls through to a normal answer.
        if _wants_web(messages):
            for chunk in _TOOL_CALL_CHUNKS:
                yield LlmChunk(kind="token", content=chunk)
                await asyncio.sleep(0)
            return

        used_web = any("[tool_result" in str(m.get("content", "")) for m in messages)
        # Deterministic thinking first (powers unit/e2e thinking tests), then the
        # answer. Honour the resolved `enable_thinking` so the per-message
        # toggle is exercisable without a real reasoning model.
        if params.enable_thinking:
            for word in _MOCK_THINKING.split():
                yield LlmChunk(kind="thinking", content=word + " ")
                await asyncio.sleep(0)
        reply = _MOCK_WEB_REPLY if used_web else _MOCK_REPLY
        for word in reply.split():
            yield LlmChunk(kind="token", content=word + " ")
            await asyncio.sleep(0)
