from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from chatbot.adapters.web.mock import MockPageFetcher, MockWebSearch
from chatbot.adapters.web.trafilatura_fetcher import UnsafeUrlError, _assert_public_url
from chatbot.domain.conversation.ports.chat_llm import ChatLLM, ChatParams, LlmChunk
from chatbot.domain.conversation.ports.web_tools import SearchResult
from chatbot.services.conversation.tool_loop import (
    ToolCallScanner,
    WebTools,
    _parse_tool_call,
    run_tool_loop,
)

PARAMS = ChatParams()


# ---------- ToolCallScanner (the cross-chunk buffering parser) ----------


def _feed(scanner: ToolCallScanner, *chunks: str) -> tuple[str, dict | None]:
    out: list[str] = []
    for c in chunks:
        for _, text in scanner.feed(c):
            out.append(text)
    for _, text in scanner.flush():
        out.append(text)
    return "".join(out), scanner.tool_call


def test_scanner_plain_text_passthrough():
    text, call = _feed(ToolCallScanner(), "just ", "a normal ", "reply")
    assert text == "just a normal reply"
    assert call is None


def test_scanner_detects_and_suppresses_block():
    text, call = _feed(
        ToolCallScanner(),
        '```tool_call\n{"name": "web_search", "arguments": {"query": "cats"}}\n```',
    )
    assert text == ""  # the block is suppressed, not streamed
    assert call == {"name": "web_search", "arguments": {"query": "cats"}}


def test_scanner_block_split_across_chunks():
    # Fence + JSON arrive split at awkward boundaries.
    text, call = _feed(
        ToolCallScanner(),
        "prefix ",
        "``",
        "`to",
        "ol_call\n{",
        '"name": "fetch_page", ',
        '"arguments": {"url": "https://x.com"}}',
        "\n``",
        "`",
    )
    assert text == "prefix "
    assert call == {"name": "fetch_page", "arguments": {"url": "https://x.com"}}


def test_scanner_false_alarm_flushed_raw():
    # A fenced block that is NOT valid tool_call JSON must be streamed verbatim.
    text, call = _feed(ToolCallScanner(), "see ```tool_call\nnot json here\n``` done")
    assert call is None
    assert "```tool_call" in text and "not json here" in text and "done" in text


def test_scanner_incomplete_block_flushed_on_end():
    # Opening fence but the stream ends before a close → treat as false alarm.
    text, call = _feed(ToolCallScanner(), '```tool_call\n{"name": "web_search"')
    assert call is None
    assert text.startswith("```tool_call")


def test_scanner_backtick_prefix_not_leaked_prematurely():
    # A lone trailing backtick run must be held back until we know it isn't a fence.
    scanner = ToolCallScanner()
    emitted = [t for _, t in scanner.feed("hello ``")]
    assert "".join(emitted) == "hello "  # the "``" is held back


def test_parse_tool_call_tolerates_json_hint_and_whitespace():
    assert _parse_tool_call('  json\n{"name": "x", "arguments": {}}  ') == {
        "name": "x",
        "arguments": {},
    }
    assert _parse_tool_call("garbage") is None
    assert _parse_tool_call('{"no_name": 1}') is None


# ---------- native Gemma tool-call format (drift fallback, ADR-005) ----------


def test_scanner_detects_native_tool_call_with_list_query():
    # Gemma drifts into its own <|tool_call>call:name{...}<tool_call|> syntax,
    # with an unquoted key and a *list* of query alternatives.
    text, call = _feed(
        ToolCallScanner(),
        '<|tool_call>call:web_search{query: ["mentrix jobs", "mentrix careers"]}<tool_call|>',
    )
    assert text == ""  # suppressed, not leaked to the user
    assert call == {
        "name": "web_search",
        "arguments": {"query": ["mentrix jobs", "mentrix careers"]},
    }


def test_scanner_native_block_split_across_chunks():
    text, call = _feed(
        ToolCallScanner(),
        "prefix ",
        "<|tool",
        "_call>call:fetch_page{",
        'url: "https://x.com"}<tool',
        "_call|>",
    )
    assert text == "prefix "
    assert call == {"name": "fetch_page", "arguments": {"url": "https://x.com"}}


def test_scanner_native_missing_close_marker_parsed_on_flush():
    # Model drops the closing marker but the payload is complete → still a call.
    text, call = _feed(ToolCallScanner(), '<|tool_call>call:web_search{query: "cats"}')
    assert text == ""
    assert call == {"name": "web_search", "arguments": {"query": "cats"}}


# ---------- run_tool_loop ----------


class ScriptedLLM(ChatLLM):
    """Emits a scripted list of content strings, one per successive invocation."""

    def __init__(self, turns: list[str]) -> None:
        self._turns = turns
        self._i = 0
        self.invocations: list[list[dict]] = []

    async def stream_chat(
        self, messages: list[dict], system_prompt: str, params: ChatParams
    ) -> AsyncIterator[LlmChunk]:
        self.invocations.append(list(messages))
        content = self._turns[min(self._i, len(self._turns) - 1)]
        self._i += 1
        for ch in content:
            yield LlmChunk(kind="token", content=ch)


async def _collect(agen) -> list[dict]:
    return [e async for e in agen]


@pytest.mark.asyncio
async def test_run_tool_loop_executes_search_then_answers():
    llm = ScriptedLLM(
        [
            '```tool_call\n{"name": "web_search", "arguments": {"query": "cats"}}\n```',
            "Cats are great.",
        ]
    )
    search = MockWebSearch(
        results=[SearchResult(title="Cats", url="https://cats.example", snippet="meow")]
    )
    tools = WebTools(search=search, fetcher=MockPageFetcher(), max_iterations=4)

    events = await _collect(
        run_tool_loop(
            llm, "You are helpful.", PARAMS, [{"role": "user", "content": "cats?"}], tools
        )
    )

    types = [e["type"] for e in events]
    assert "tool_start" in types and "tool_end" in types
    start = next(e for e in events if e["type"] == "tool_start")
    end = next(e for e in events if e["type"] == "tool_end")
    assert start["tool"] == "web_search" and start["query"] == "cats"
    assert end["ok"] is True and end["results"] == [
        {"title": "Cats", "url": "https://cats.example"}
    ]
    answer = "".join(e["content"] for e in events if e["type"] == "token")
    assert answer == "Cats are great."
    assert search.calls == [("cats", 5)]
    # The tool result was appended as a synthetic user turn for the 2nd invocation.
    assert any(
        m["role"] == "user" and "[tool_result web_search]" in m["content"]
        for m in llm.invocations[1]
    )


@pytest.mark.asyncio
async def test_run_tool_loop_executes_native_format_with_list_query():
    # The exact drift that leaked raw to the user: native markers + list query.
    llm = ScriptedLLM(
        [
            '<|tool_call>call:web_search{query: ["mentrix jobs", "mentrix careers"]}<tool_call|>',
            "Mentrix has no public job listings.",
        ]
    )
    search = MockWebSearch(
        results=[SearchResult(title="Mentrix", url="https://mentrix.example", snippet="")]
    )
    tools = WebTools(search=search, fetcher=MockPageFetcher(), max_iterations=4)

    events = await _collect(
        run_tool_loop(llm, "sys", PARAMS, [{"role": "user", "content": "jobs?"}], tools)
    )

    # No raw markers leaked as answer tokens.
    answer = "".join(e["content"] for e in events if e["type"] == "token")
    assert answer == "Mentrix has no public job listings."
    assert "tool_call" not in answer
    # The search actually ran, on the first of the listed queries.
    start = next(e for e in events if e["type"] == "tool_start")
    assert start["tool"] == "web_search" and start["query"] == "mentrix jobs"
    assert search.calls == [("mentrix jobs", 5)]


@pytest.mark.asyncio
async def test_run_tool_loop_respects_iteration_cap():
    # The model always asks for another tool; the loop must stop after max_iterations.
    always_call = '```tool_call\n{"name": "web_search", "arguments": {"query": "q"}}\n```'
    llm = ScriptedLLM([always_call])
    search = MockWebSearch()
    tools = WebTools(search=search, fetcher=MockPageFetcher(), max_iterations=3)

    events = await _collect(
        run_tool_loop(llm, "sys", PARAMS, [{"role": "user", "content": "go"}], tools)
    )

    tool_starts = [e for e in events if e["type"] == "tool_start"]
    assert len(tool_starts) == 3  # capped
    assert len(search.calls) == 3


@pytest.mark.asyncio
async def test_run_tool_loop_no_tool_call_streams_directly():
    llm = ScriptedLLM(["Just a plain answer."])
    tools = WebTools(search=MockWebSearch(), fetcher=MockPageFetcher())
    events = await _collect(
        run_tool_loop(llm, "sys", PARAMS, [{"role": "user", "content": "hi"}], tools)
    )
    assert [e["type"] for e in events] == ["token"] * len("Just a plain answer.")


# ---------- SSRF guard ----------


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/x",
        "file:///etc/passwd",
        "http://localhost/",
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
    ],
)
def test_ssrf_guard_rejects_unsafe(url):
    with pytest.raises(UnsafeUrlError):
        _assert_public_url(url)


def test_ssrf_guard_allows_public_ip_literal():
    # 8.8.8.8 is a global address; a literal needs no DNS.
    _assert_public_url("https://8.8.8.8/")
