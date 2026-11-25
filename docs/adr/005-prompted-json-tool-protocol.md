# ADR-005: Prompted-JSON web-access tool protocol

**Status**: Accepted
**Date**: 2026-07-13

## Context

Phase 6 gives the assistant web access: a 🌐 composer toggle lets a turn search
the web and read pages before answering. This needs a tool-call mechanism —
the model asks for a search / page fetch, we run it, feed the result back, and
let it answer.

The obvious route is native OpenAI-style `tools` on `/v1/chat/completions`. Our
host is llama.cpp serving **Gemma 4 26B-A4B**. Gemma 4 *does* have native
function calling (Gemma 3 did not), but on llama.cpp it is not a first-class
path: there's no native format handler for Gemma 4 (it falls back to the generic
Jinja handler, needs `--jinja`), and the tokenizer/template/streaming bugs were
only fixed very recently. Worse, Gemma 4 forces reasoning by default, which
routes tool-call output into `reasoning_content` unless thinking is disabled. In
short: native tools are technically possible but not yet *reliable* on our stack.

## Decision

**Prompted-JSON, not native `tools`.** When web access is on we append a
protocol block to the system prompt instructing the model to emit a single fenced
```` ```tool_call ```` block containing `{"name", "arguments"}`, then stop. The
whole policy lives in `services/conversation/tool_loop.py` — **application layer,
not an adapter** — so a native-`tools` implementation can swap in later behind the
same use-case seam once llama.cpp's Gemma 4 support matures.

**Thinking is forced off for the loop.** `send_message` resolves
`enable_thinking=False` (via `dataclasses.replace` on `ChatParams`) whenever
`web_access` is on, so the tool_call block lands in `content` where the scanner
can see it instead of being swallowed into `reasoning_content`.

**Native-format drift is tolerated, not just the prompted fence.** Gemma 4 has
native function calling and stochastically emits its own
`<|tool_call>call:<name>{…}<tool_call|>` token format instead of the prompted
fence — especially on follow-up turns. Un-recognized, that block streamed raw to
the user and *no tool ran* (the observed "web search sometimes fails" bug). So
`ToolCallScanner` is a small registry of recognizers: the prompted
```` ```tool_call ```` fence (primary) **and** the native marker pair (fallback),
whichever opens earliest in the stream. The native payload is parsed leniently
(`call:<name>{…}`, unquoted keys, and a **list**-valued `query` — Gemma passes
several alternatives — coerced to the first non-empty one). A real call whose
close marker the model dropped is re-parsed at end-of-turn rather than leaked.
The model's request is always re-recorded into history in the *canonical* fenced
form, nudging it back on-protocol for the next turn.

**The loop.** `run_tool_loop` streams a turn through an incremental
`ToolCallScanner` that passes normal text through while holding back any trailing
run that could be the start of an opening marker (cross-chunk buffering — the
subtle part, unit-tested). On a complete, parseable block it suppresses the block,
emits `tool_start`, executes the tool, emits `tool_end`, appends the result as a
synthetic **`user`** turn (`[tool_result <name>]…` — Gemma has no tool role), and
re-invokes. A block that fails to parse is flushed back as raw tokens (false
alarm). It runs at most `WEB_TOOL_MAX_ITERATIONS` (4) tools, then appends a nudge
and forces a final answer with tools disallowed.

**Two ports, both sync-wrapped.** `domain/conversation/ports/web_tools.py`:
`WebSearch.search(query, max_results) -> list[SearchResult]` and
`PageFetcher.fetch(url) -> str`. Adapters `adapters/web/`: `ddgs` search +
`trafilatura` extraction (house convention — Pasti/Blibiobot use trafilatura),
both pushed onto the anyio thread pool. Mock adapters back tests / offline dev
(`WEB_TOOLS_ENABLED=false`). Tool failures never break the stream — they become
an error `tool_result` the model can react to.

**SSRF guard.** The backend sits next to Postgres/Garage on a private network, so
`fetch_page` rejects non-http(s) schemes and any host that resolves to a private /
loopback / link-local / reserved / non-global address — checked on the initial
host *and* every redirect hop (we do the HTTP ourselves rather than
`trafilatura.fetch_url`).

## Consequences

- New migration `0005`: `messages.tool_events JSONB` (nullable) — one record per
  tool call (`id`, `tool`, `query`/`url`, `ok`, `summary`, `results`), so the
  activity chips re-render on reload. Excluded from LLM history, like `thinking`.
- Wire protocol gains two event types (`tool_start`, `tool_end`); the SSE framing
  is already generic, so only the typed unions (frontend + `StreamEvent`) change.
  `SendMessageRequest.web_access: bool` is a per-message toggle, sticky in
  `localStorage` on the frontend.
- Streaming preamble the model emits *before* a tool call is streamed as answer
  tokens (normally empty — the protocol tells it to emit only the block).
- Production needs outbound internet from the api container. `ddgs` +
  `trafilatura` are new backend deps.
- Web access is send-only; regenerate/edit re-answer without tools this phase.
- Swapping to native `tools` later is a `tool_loop.py` + adapter change; the
  use-case seam, event protocol, and persistence stay put.
