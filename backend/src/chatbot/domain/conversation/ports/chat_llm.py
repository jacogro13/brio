from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LlmChunk:
    """A single streamed piece of an LLM reply.

    ``kind`` discriminates answer text (``token``) from reasoning
    (``thinking``); ``tool_call`` is reserved for Phase 6 (web access) and is
    ``None`` for every other kind.
    """

    kind: Literal["token", "thinking", "tool_call"]
    content: str
    tool_call: object | None = None


@dataclass(frozen=True)
class ChatParams:
    """Per-call generation parameters, resolved by the streaming use cases from
    the conversation's overrides and the server defaults.

    ``temperature`` / ``max_tokens`` are ``None`` when unset — the adapter omits
    them so the LLM server applies its own default. ``enable_thinking`` is always
    a concrete bool (the use case resolves the conversation override against the
    server default before constructing this)."""

    temperature: float | None = None
    max_tokens: int | None = None
    enable_thinking: bool = False


class ChatLLM(ABC):
    @abstractmethod
    def stream_chat(
        self, messages: list[dict], system_prompt: str, params: ChatParams
    ) -> AsyncIterator[LlmChunk]: ...
