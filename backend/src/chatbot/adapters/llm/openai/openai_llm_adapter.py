from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Literal

import httpx

from chatbot.domain.conversation.ports.chat_llm import ChatLLM, ChatParams, LlmChunk

_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"


def _held_prefix_len(buf: str, tag: str) -> int:
    """Length of ``buf`` safe to emit without swallowing a partial ``tag``.

    Holds back a trailing run of chars that could be the start of ``tag``
    arriving split across chunk boundaries (e.g. ``"foo</th"`` holds ``"</th"``).
    """
    for k in range(min(len(tag) - 1, len(buf)), 0, -1):
        if buf.endswith(tag[:k]):
            return len(buf) - k
    return len(buf)


_TextKind = Literal["token", "thinking"]


class _ThinkTagSplitter:
    """Incremental splitter for models that inline reasoning as ``<think>…</think>``
    in ``content`` instead of a separate ``reasoning_content`` field (depends on
    llama.cpp's ``--reasoning-format``). Feeds content deltas in, yields
    ``("thinking"|"token", text)`` pairs, buffering partial tags across chunks."""

    def __init__(self) -> None:
        self._in_think = False
        self._buf = ""

    def feed(self, text: str) -> list[tuple[_TextKind, str]]:
        self._buf += text
        out: list[tuple[_TextKind, str]] = []
        while True:
            if not self._in_think:
                idx = self._buf.find(_THINK_OPEN)
                if idx == -1:
                    safe = _held_prefix_len(self._buf, _THINK_OPEN)
                    if safe:
                        out.append(("token", self._buf[:safe]))
                        self._buf = self._buf[safe:]
                    break
                if idx > 0:
                    out.append(("token", self._buf[:idx]))
                self._buf = self._buf[idx + len(_THINK_OPEN) :]
                self._in_think = True
            else:
                idx = self._buf.find(_THINK_CLOSE)
                if idx == -1:
                    safe = _held_prefix_len(self._buf, _THINK_CLOSE)
                    if safe:
                        out.append(("thinking", self._buf[:safe]))
                        self._buf = self._buf[safe:]
                    break
                if idx > 0:
                    out.append(("thinking", self._buf[:idx]))
                self._buf = self._buf[idx + len(_THINK_CLOSE) :]
                self._in_think = False
        return out

    def flush(self) -> list[tuple[_TextKind, str]]:
        if not self._buf:
            return []
        kind: _TextKind = "thinking" if self._in_think else "token"
        out: list[tuple[_TextKind, str]] = [(kind, self._buf)]
        self._buf = ""
        return out


class OpenAILikeLLMAdapter(ChatLLM):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float | None = 300.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def stream_chat(
        self, messages: list[dict], system_prompt: str, params: ChatParams
    ) -> AsyncIterator[LlmChunk]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        body: dict = {
            "model": self._model,
            "stream": True,
            "messages": full_messages,
            "chat_template_kwargs": {"enable_thinking": params.enable_thinking},
        }
        # Send temperature/max_tokens only when overridden, so the server keeps
        # its own default otherwise (never conflate an unset value with 0).
        if params.temperature is not None:
            body["temperature"] = params.temperature
        if params.max_tokens is not None:
            body["max_tokens"] = params.max_tokens
        # Fallback for models that inline reasoning as <think> tags in `content`
        # rather than a dedicated `reasoning_content` field. When the server does
        # separate them, no tags appear in `content` and the splitter is a no-op.
        splitter = _ThinkTagSplitter()
        async with self._client.stream(
            "POST",
            f"{self._base_url}/v1/chat/completions",
            headers=headers,
            json=body,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"]
                reasoning = delta.get("reasoning_content")
                if reasoning:
                    yield LlmChunk(kind="thinking", content=reasoning)
                content = delta.get("content", "")
                if content:
                    for kind, text in splitter.feed(content):
                        yield LlmChunk(kind=kind, content=text)
            for kind, text in splitter.flush():
                yield LlmChunk(kind=kind, content=text)
