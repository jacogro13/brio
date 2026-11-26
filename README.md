# Brio

A persistent multi-conversation chat interface backed by a local LLM.

Brio is called `chatbot` in the code, the images and the work records. It is the example
app of [officina](https://github.com/jacogro13/officina), the gated workflow I have
developed it with since November 2026: every change since then (001–008) has a spec, plan
and review under `docs/work/`. Its features from before that (streaming, attachments,
web access, multiuser, mobile layout) were built without the factory, from two plans
written in July 2026: [`docs/IMPROVEMENT_PLAN.md`](docs/IMPROVEMENT_PLAN.md) and
[`docs/MOBILE_UX_PLAN.md`](docs/MOBILE_UX_PLAN.md).

Supports any OpenAI-compatible server — Ollama, llama.cpp, LM Studio, etc.

Prerequisites: Python 3.12 + `uv`, Node 20 + `npm`, Docker with Compose v2.

```bash
make env && make backend   # API on :5004
make frontend              # UI  on :5174
```

See `CLAUDE.md` for the full command reference and architecture overview.

## Local LLM

In production Brio talks to Gemma 4 26B-A4B served by llama.cpp on my own server, the
same machine that runs [officina](https://github.com/jacogro13/officina)'s worker model.
It works with any OpenAI-compatible server.

- **Behind a port:** the domain only knows `ChatLLM`; `OpenAILikeLLMAdapter` talks to
  the server, `MockLLMAdapter` stands in when `LLM_BASE_URL` is empty. The e2e tests run
  with the mock, so they need no model.
- **Streaming** to the browser over a typed SSE protocol
  ([ADR-003](docs/adr/003-typed-sse-event-protocol.md)).
- **Thinking models:** thinking can be switched per conversation (sent as
  `chat_template_kwargs.enable_thinking`); reasoning is kept apart from the answer,
  whether the server sends it as `reasoning_content` or inline as `<think>` tags.
- **Web access without native function calling:** search and page fetches use a
  prompted-JSON tool loop with an SSRF guard
  ([ADR-005](docs/adr/005-prompted-json-tool-protocol.md)).
- **Known gap:** if the model server is down, the stream just ends; there is no error
  event yet.

## Environment

`make env` generates `.env` from `.env.example` (random DB password + a
correctly-formatted `GK…` Garage key). Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | — | Async Postgres DSN (`make backend` host view; compose overrides it in-container). |
| `LLM_BASE_URL` | `http://localhost:11434` | OpenAI-compatible chat server. **Empty ⇒ mock LLM.** |
| `LLM_MODEL` | `llama3.2` | Model name the server serves. |
| `LLM_CHAT_ENABLE_THINKING` | `false` | Server-wide default for reasoning display (per-conversation override in the ⚙ popover). |
| `SYSTEM_PROMPT` | `You are a helpful assistant.` | Default system prompt. |
| `CHATBOT_LANGUAGE` | `en` | **CLI-only** assistant reply language (`en`/`it`/`de`). The web app derives this per-user from `users.language`. |
| `GARAGE_ENDPOINT` | `http://localhost:3907` (dev) | Garage S3 endpoint. **Empty ⇒ in-memory attachment storage.** In prod the shared Garage via the `garage` alias. |
| `GARAGE_BUCKET` | `chatbot` | Attachment bucket. |
| `GARAGE_ACCESS_KEY_ID` / `GARAGE_SECRET_ACCESS_KEY` | — | S3 credentials (`GK`+12 hex bytes for the id). |
| `GARAGE_REGION` | `garage` | S3 region. |
| `ATTACHMENT_MAX_BYTES` | `10485760` | Reject uploads larger than this (413). |
| `ATTACHMENT_MAX_EXTRACTED_CHARS` | `40000` | Truncate extracted text to bound the LLM context. |
| `WEB_TOOLS_ENABLED` | `true` | Web access (🌐). **`false` ⇒ mock search/fetch adapters** (offline dev). |
| `WEB_TOOL_MAX_ITERATIONS` | `4` | Max tool calls per web-access turn before forcing an answer. |
| `WEB_SEARCH_MAX_RESULTS` | `5` | Results per `web_search` call. |
| `WEB_FETCH_MAX_CHARS` | `20000` | Truncate each fetched page to bound the LLM context. |
| `JWT_SECRET_KEY` | — (**required**) | Signs JWT access tokens. `make env` generates it; append `JWT_SECRET_KEY=$(openssl rand -hex 32)` to an existing `.env`. |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `43200` | Token lifetime (30 days — LAN app). |
| `LOGIN_RATE_LIMIT` | `5/minute` | slowapi budget on `POST /auth/login`, per client IP. |

Attachments (file uploads) are stored in Garage — an isolated per-app container
in dev, the **shared** `shared_garage` in production. See
[ADR-004](docs/adr/004-attachments-in-garage.md).

Web access (🌐 composer toggle) runs a prompted-JSON tool loop — DuckDuckGo
search (`ddgs`) + page extraction (`trafilatura`), with thinking forced off for
the turn and an SSRF guard on page fetches. See
[ADR-005](docs/adr/005-prompted-json-tool-protocol.md).

## Adding a new LLM provider

1. Create `backend/src/chatbot/adapters/llm/<provider>/<provider>_llm_adapter.py`
   implementing `ChatLLM`.
2. Wire it in `get_llm()` in `entrypoints/dependencies.py` (API) and in
   `entrypoints/cli/dependencies.py` (CLI), behind a new env-var guard.
3. Add a new ADR documenting the choice.
