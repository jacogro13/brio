# ADR-003: Typed SSE event protocol

**Status**: Accepted
**Date**: 2026-07-12

## Context

The streaming endpoints emitted an ad-hoc SSE payload: `{"token": "..."}` per
chunk, `{"done": true}` at the end, `{"error": "..."}` on failure. Three
consumers parsed it — the React frontend, the CLI, and (implicitly) the tests.
The framing (`data: {json}\n\n`) lived *inside* the `send_message` use case,
which mixed transport concerns into the application layer and made a use case
un-reusable by a non-HTTP entrypoint (the CLI had to re-parse SSE strings it had
just been handed in-process).

Phase 1 of the Claude.ai-like upgrade adds three more streaming flows
(regenerate, edit) and later phases add `thinking`, `tool_start`/`tool_end`
events. The old two-shape payload has no room to grow and no discriminator.

## Decision

**A single typed event union**, discriminated by a `type` field:

- `{"type": "token", "content": "..."}`
- `{"type": "done", "message_id": "<uuid>" | null}`
- `{"type": "error", "code": "...", "message": "..."}` (`code` added in work
  item 002: the same stable code as the matching domain error in HTTP error
  bodies, e.g. `conversation_not_found`; `message` is English, for debugging)

Later phases extend the union (`thinking`, `tool_start`, `tool_end`) without
breaking the shape. There is **no version field**: the frontend, CLI, and
backend ship together from this monorepo.

**Framing moves out of the use cases.** Use cases (`send_message`,
`regenerate_message`, `edit_message`) are async generators that `yield` plain
event **dicts**. A new `entrypoints/routers/sse.py::sse_stream()` helper wraps
any such generator into a `StreamingResponse`, applying the `data: {json}\n\n`
framing and SSE headers in one place. The CLI consumes the same dict generator
directly (`cli/rendering.py::stream_events`) with no SSE parsing.

**Shared streaming tail.** The stream-then-persist logic common to send /
regenerate / edit lives in `services/conversation/_streaming.py::stream_and_persist`,
which yields the `token` events and the terminating `done` event and persists
the assistant reply in a dedicated final UoW. The delegating use cases wrap it
in `contextlib.aclosing` so the tail's `finally`-persist still runs when the
outer generator is `aclose()`d on a client disconnect (Stop / dropped
connection) — without `aclosing`, abandoning the outer `async for` leaves the
inner generator suspended and the partial reply unsaved until GC.

## Consequences

- Adding an event type is additive: a new `{"type": ...}` member, handled by the
  frontend/CLI switch, with no protocol version bump.
- Use cases are transport-agnostic; the CLI wires them in-process with zero SSE
  string handling.
- **Stop is a client-side abort.** The frontend aborts the `fetch`; the backend
  generator is `aclose()`d, the `aclosing`-guarded tail persists whatever
  streamed, and the frontend refetches the conversation to pick up real message
  ids (needed for edit/regenerate) and the auto-title.
- New routes: `PATCH /conversations/{id}` (rename),
  `POST /conversations/{id}/messages/regenerate`,
  `POST /conversations/{id}/messages/{message_id}/edit`.
- The repository gains `delete_messages(conversation_id, message_ids)` — deletion
  by explicit id list computed from the ordered `conv.messages`, never a
  `created_at >=` range (timestamps can tie).
