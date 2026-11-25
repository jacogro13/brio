"""Prompted-JSON web-access tool loop (Phase 6).

Application policy — **not** an adapter — so a native-``tools`` implementation can
swap in later once llama.cpp's Gemma 4 tool support matures (see
``docs/adr/005-prompted-json-tool-protocol.md``). The model is instructed (via a
system-prompt block) to emit a fenced ```` ```tool_call ```` block with a JSON
``{"name", "arguments"}`` object. We buffer the token stream, suppress a detected
block, execute the tool, append its result as a synthetic ``user`` turn (Gemma has
no tool role), and re-invoke — up to ``max_iterations`` times.

Reasoning stays **off** while the loop runs (the caller resolves
``enable_thinking=False`` whenever web access is on): Gemma 4 otherwise routes
output into ``reasoning_content`` and the fenced block never lands in ``content``
where the scanner can see it.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from urllib.parse import urlparse

from chatbot.domain.conversation.ports.chat_llm import ChatLLM, ChatParams
from chatbot.domain.conversation.ports.web_tools import (
    PageFetcher,
    SearchResult,
    WebSearch,
)

_OPEN_FENCE = "```tool_call"
_CLOSE_FENCE = "```"

# Gemma 4 has native function calling and stochastically drifts into its own
# token format instead of the prompted fence (ADR-005). We recognize that too,
# so a drifted call still executes instead of leaking as raw text to the user.
_NATIVE_OPEN = "<|tool_call>"
_NATIVE_CLOSE = "<tool_call|>"

_LIMIT_NUDGE = (
    "[tool_result] Tool-call limit reached. Answer the user now using the "
    "information gathered above; do not request any more tools."
)

_TOOL_PROTOCOL_PROMPT = """\

# Web access (ENABLED)

Web access is turned ON for this message. You MUST begin by searching the web \
before you answer — do not rely on your own knowledge alone, even if you think \
you already know the answer. Your very first output must be a single fenced code \
block tagged `tool_call` containing a JSON object, then STOP and wait for the \
result. Do not write anything before or after the block.

Available tools:
- `web_search` — arguments: {"query": string}. Returns a list of result titles + URLs.
- `fetch_page` — arguments: {"url": string}. Returns the readable text of one page.

Format (exactly):
```tool_call
{"name": "web_search", "arguments": {"query": "your query"}}
```

Derive the query from the user's latest message. After you receive a \
`[tool_result ...]` message, either call another tool the same way (e.g. \
`fetch_page` on a promising result) or write your final answer in normal prose. \
Never show the raw tool_call block to the user in your final answer, and cite \
the sources you used by URL.
"""


@dataclass(frozen=True)
class WebTools:
    """Bundle of web-access ports + caps passed into the tool loop."""

    search: WebSearch
    fetcher: PageFetcher
    max_iterations: int = 4
    search_max_results: int = 5


def build_tool_system_prompt(base_system_prompt: str) -> str:
    """Append the tool-protocol block to the resolved system prompt."""
    return base_system_prompt.rstrip() + "\n" + _TOOL_PROTOCOL_PROMPT


def _held_prefix_len(buf: str, tag: str) -> int:
    """Length of ``buf`` safe to emit without swallowing a partial ``tag`` that
    may arrive split across chunk boundaries (mirrors the LLM adapter helper)."""
    for k in range(min(len(tag) - 1, len(buf)), 0, -1):
        if buf.endswith(tag[:k]):
            return len(buf) - k
    return len(buf)


def _held_prefix_len_multi(buf: str, tags: list[str]) -> int:
    """``_held_prefix_len`` across several possible open markers: hold back the
    longest trailing run that could be the start of *any* ``tag``."""
    held = 0
    for tag in tags:
        for k in range(min(len(tag) - 1, len(buf)), 0, -1):
            if buf.endswith(tag[:k]):
                held = max(held, k)
                break
    return len(buf) - held


def _parse_tool_call(raw: str) -> dict | None:
    """Parse the JSON inside a captured ```` ```tool_call ```` block. Tolerates a
    leading ``json`` language hint and surrounding whitespace. Returns ``None``
    when the payload isn't a well-formed ``{"name", "arguments"}`` object (the
    scanner then treats the block as a false alarm and streams it raw)."""
    text = raw.strip()
    if text.startswith("json"):
        text = text[4:].lstrip()
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict) or "name" not in obj:
        return None
    return obj


def _lenient_json_object(body: str) -> dict | None:
    """Parse a possibly-sloppy JSON object. Tolerates unquoted keys — Gemma's
    native format emits ``{query: [...]}`` rather than ``{"query": [...]}``."""
    try:
        obj = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        fixed = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r'\1"\2"\3', body)
        try:
            obj = json.loads(fixed)
        except (json.JSONDecodeError, ValueError):
            return None
    return obj if isinstance(obj, dict) else None


def _parse_native_tool_call(raw: str) -> dict | None:
    """Parse Gemma's native ``call:<name>{<args>}`` payload (captured between
    ``<|tool_call>`` / ``<tool_call|>`` markers) into the canonical
    ``{"name", "arguments"}`` shape. Falls back to plain JSON so a native marker
    wrapping a normal object still works. Returns ``None`` on anything else."""
    text = raw.strip()
    m = re.match(r"(?:call:)?\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\{.*\})\s*$", text, re.DOTALL)
    if m:
        args = _lenient_json_object(m.group(2))
        if args is None:
            return None
        return {"name": m.group(1), "arguments": args}
    return _parse_tool_call(text)


@dataclass(frozen=True)
class _Recognizer:
    """One tool-call surface syntax: paired open/close markers + a parser."""

    open: str
    close: str
    parse: Callable[[str], dict | None]


# Ordered by open-marker specificity; both share no common prefix so scan order
# doesn't matter — the scanner picks whichever marker appears earliest in the
# stream. The prompted fence (ADR-005) is primary; the native format is the
# drift fallback.
_RECOGNIZERS: list[_Recognizer] = [
    _Recognizer(_OPEN_FENCE, _CLOSE_FENCE, _parse_tool_call),
    _Recognizer(_NATIVE_OPEN, _NATIVE_CLOSE, _parse_native_tool_call),
]
_OPEN_MARKERS = [r.open for r in _RECOGNIZERS]


def _earliest_open(buf: str) -> tuple[int, _Recognizer | None]:
    """First fully-present open marker in ``buf`` and its recognizer."""
    best_idx, best_rec = -1, None
    for rec in _RECOGNIZERS:
        idx = buf.find(rec.open)
        if idx != -1 and (best_idx == -1 or idx < best_idx):
            best_idx, best_rec = idx, rec
    return best_idx, best_rec


class ToolCallScanner:
    """Incremental scanner over one LLM turn's ``content`` stream.

    Streams normal text through (``feed`` returns ``[(\"token\", text), ...]``),
    holding back only a trailing run that could be the start of an opening
    marker. On a complete, parseable block — the prompted ```` ```tool_call ````
    fence **or** Gemma's native ``<|tool_call>…<tool_call|>`` form — it sets
    ``tool_call`` and suppresses the block; a block that fails to parse is
    flushed back as raw tokens (false alarm). This buffering is the subtle part
    — unit-tested in ``tests/unit/test_tool_loop.py``."""

    def __init__(self) -> None:
        self._buf = ""
        self._active: _Recognizer | None = None
        self._capture = ""
        self.tool_call: dict | None = None

    def feed(self, text: str) -> list[tuple[str, str]]:
        if self.tool_call is not None:
            return []  # ignore anything after a completed tool call
        self._buf += text
        out: list[tuple[str, str]] = []
        while True:
            if self._active is None:
                idx, rec = _earliest_open(self._buf)
                if rec is None:
                    safe = _held_prefix_len_multi(self._buf, _OPEN_MARKERS)
                    if safe:
                        out.append(("token", self._buf[:safe]))
                        self._buf = self._buf[safe:]
                    break
                if idx > 0:
                    out.append(("token", self._buf[:idx]))
                self._buf = self._buf[idx + len(rec.open) :]
                self._active = rec
                self._capture = ""
            else:
                rec = self._active
                idx = self._buf.find(rec.close)
                if idx == -1:
                    safe = _held_prefix_len(self._buf, rec.close)
                    self._capture += self._buf[:safe]
                    self._buf = self._buf[safe:]
                    break
                self._capture += self._buf[:idx]
                rest = self._buf[idx + len(rec.close) :]
                parsed = rec.parse(self._capture)
                if parsed is not None:
                    self.tool_call = parsed
                    self._buf = ""
                    break
                # False alarm: not a real tool call — emit the block verbatim.
                out.append(("token", rec.open + self._capture + rec.close))
                self._active = None
                self._capture = ""
                self._buf = rest
        return out

    def flush(self) -> list[tuple[str, str]]:
        """Emit whatever normal text is still buffered at end of turn. An
        incomplete capture (open marker but no close) is first re-parsed — the
        model may have dropped the close marker on a real call — and only
        flushed raw if that still fails to parse (false alarm)."""
        if self.tool_call is not None:
            return []
        out: list[tuple[str, str]] = []
        if self._active is not None:
            parsed = self._active.parse(self._capture + self._buf)
            if parsed is not None:
                self.tool_call = parsed
            else:
                out.append(("token", self._active.open + self._capture + self._buf))
        elif self._buf:
            out.append(("token", self._buf))
        self._buf = ""
        self._capture = ""
        self._active = None
        return out


def _render_tool_call_block(call: dict) -> str:
    return f"{_OPEN_FENCE}\n{json.dumps(call)}\n{_CLOSE_FENCE}"


def _coerce_arg_str(value: object) -> str:
    """Coerce a tool argument to a single stripped string. Gemma's native format
    often passes ``query`` as a *list* of alternatives — use the first non-empty
    one rather than searching for the list's ``repr`` (or failing outright)."""
    if isinstance(value, list):
        for item in value:
            text = str(item).strip()
            if text:
                return text
        return ""
    return str(value).strip()


def _format_search_results(results: list[SearchResult]) -> str:
    if not results:
        return "No results."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.title}\n   {r.url}")
        if r.snippet:
            lines.append(f"   {r.snippet}")
    return "\n".join(lines)


async def _execute(
    name: str, arguments: dict, tools: WebTools
) -> tuple[bool, str, str, list[dict]]:
    """Run one tool call. Returns ``(ok, summary, result_text, results)`` — the
    tool never raises out of here; failures become an error ``tool_result`` the
    model can react to, never a stream failure."""
    if name == "web_search":
        query = _coerce_arg_str(arguments.get("query", ""))
        if not query:
            return False, "missing query", "Error: web_search needs a 'query'.", []
        try:
            hits = await tools.search.search(query, tools.search_max_results)
        except Exception as exc:  # noqa: BLE001
            return False, f"search error: {exc}", f"Error running web_search: {exc}", []
        results = [{"title": h.title, "url": h.url} for h in hits]
        summary = f"{len(hits)} result{'s' if len(hits) != 1 else ''}"
        return True, summary, _format_search_results(hits), results

    if name == "fetch_page":
        url = _coerce_arg_str(arguments.get("url", ""))
        if not url:
            return False, "missing url", "Error: fetch_page needs a 'url'.", []
        try:
            text = await tools.fetcher.fetch(url)
        except Exception as exc:  # noqa: BLE001 — incl. SSRF guard rejections
            return False, f"fetch error: {exc}", f"Error fetching page: {exc}", []
        host = urlparse(url).hostname or url
        return True, f"{host} — {len(text)} chars", text, []

    return False, f"unknown tool: {name}", f"Error: unknown tool {name!r}.", []


async def _stream_turn(
    llm: ChatLLM,
    working: list[dict],
    system_prompt: str,
    params: ChatParams,
    allow_tool: bool,
) -> AsyncIterator[tuple[str, object]]:
    """Stream one LLM turn. Yields ``(\"thinking\"|\"token\", text)`` and, when
    ``allow_tool`` and a block completes, a final ``(\"tool_call\", dict)`` and
    stops. When ``allow_tool`` is False any tool_call block is silently
    suppressed and only text is streamed."""
    scanner = ToolCallScanner()
    async for chunk in llm.stream_chat(working, system_prompt, params):
        if chunk.kind == "thinking":
            yield ("thinking", chunk.content)
            continue
        if chunk.kind != "token":
            continue
        for _, text in scanner.feed(chunk.content):
            yield ("token", text)
        if allow_tool and scanner.tool_call is not None:
            break
    if not (allow_tool and scanner.tool_call is not None):
        for _, text in scanner.flush():
            yield ("token", text)
        return
    yield ("tool_call", scanner.tool_call)


async def run_tool_loop(
    llm: ChatLLM,
    base_system_prompt: str,
    params: ChatParams,
    history: list[dict],
    tools: WebTools,
) -> AsyncIterator[dict]:
    """Drive the web-access loop, yielding client event dicts
    (``token``/``thinking``/``tool_start``/``tool_end``). Executes at most
    ``tools.max_iterations`` tools, then forces a final answer."""
    system_prompt = build_tool_system_prompt(base_system_prompt)
    working = list(history)
    executed = 0

    while True:
        pending_call: dict | None = None
        async for kind, payload in _stream_turn(
            llm, working, system_prompt, params, allow_tool=True
        ):
            if kind == "tool_call":
                pending_call = payload  # type: ignore[assignment]
            else:
                yield {"type": kind, "content": payload}

        if pending_call is None:
            return

        name = str(pending_call.get("name", ""))
        arguments = pending_call.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}

        # Record the model's own request so the next turn sees its context.
        working.append({"role": "assistant", "content": _render_tool_call_block(pending_call)})
        start: dict = {"type": "tool_start", "id": executed, "tool": name}
        if name == "web_search":
            start["query"] = _coerce_arg_str(arguments.get("query", ""))
        elif name == "fetch_page":
            start["url"] = _coerce_arg_str(arguments.get("url", ""))
        yield start

        ok, summary, result_text, results = await _execute(name, arguments, tools)
        yield {
            "type": "tool_end",
            "id": executed,
            "tool": name,
            "ok": ok,
            "summary": summary,
            "results": results,
        }
        working.append({"role": "user", "content": f"[tool_result {name}]\n{result_text}"})
        executed += 1

        if executed >= tools.max_iterations:
            working.append({"role": "user", "content": _LIMIT_NUDGE})
            async for kind, payload in _stream_turn(
                llm, working, system_prompt, params, allow_tool=False
            ):
                if kind != "tool_call":
                    yield {"type": kind, "content": payload}
            return
