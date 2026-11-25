# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation

Docs are plain Markdown in `docs/`: `architecture.md` (the overview, with container and component diagrams), `adr/` (design decisions, listed in `adr/README.md`) and `work/` (one record per change: spec, plan, review). When asked about architecture, layering, streaming, auth, attachments, web access, or the rationale for any design choice, prefer `docs/architecture.md` and `docs/adr/` — they are the source of truth and are kept current.

## Commands

### First-time setup

```bash
make env          # Generate .env with random secrets (run once)
make migration    # Apply alembic migrations
```

### Backend (from repo root)

```bash
make sync              # uv sync
make unit-backend      # pytest tests/unit (in-process, no Docker)
make integration       # pytest tests/integration (Postgres testcontainer)
make test-backend      # lint + typecheck + unit-backend + integration
make backend           # uvicorn dev server (http://localhost:5004) — applies migrations first
```

Run a single test:
```bash
cd backend && uv run pytest tests/unit/test_model.py
cd backend && uv run pytest tests/unit/test_model.py::test_function_name
```

### Frontend (from repo root)

```bash
make frontend          # Vite dev server (http://localhost:5174, proxies /api → :5004)
make unit-frontend     # vitest
cd frontend && npm run lint
cd frontend && npm run build
```

### CLI (from repo root)

```bash
make cli               # Terminal REPL — applies migrations, runs `uv run --project=backend chatbot`
```

The CLI talks directly to Postgres and the LLM in-process — no FastAPI involved. Slash commands: `/new`, `/list`, `/switch <n>`, `/delete <n>`, `/help`, `/quit`. Reference files in a message with `@path` (paths resolve relative to the directory the CLI was launched from); paths outside cwd, binaries, and files larger than 100 KB are skipped. Output is plain-token streaming.

### E2E (from repo root)

```bash
make e2e    # Isolated full stack via -p chatbot_e2e + Playwright (e2e/)
```

The e2e stack runs in its own compose project (`chatbot_e2e`) with `docker-compose.e2e.yml` dropping the db host port. `make e2e`'s `down -v` teardown does NOT wipe the dev db volume.

- E2E self-contained: yes (checked 2026-11-19) — `make e2e` runs its own compose project `chatbot_e2e` with a throwaway db and garage (no host ports), the mock LLM (`LLM_BASE_URL=`) and mock web tools (`WEB_TOOLS_ENABLED=false`), reaches only `http://localhost:120`, and ends with `down -v`. So the factory may run it. Re-check if e2e ever gains an external service.

### Docker

```bash
docker compose --profile app up --build   # Dev stack — local source, frontend on http://localhost:120
```

### Aggregates

```bash
make test       # Full gate: lint → typecheck → unit → integration → e2e
make lint       # ruff format --check + ruff check (backend), eslint (frontend)
make typecheck  # pyright (backend), tsc -b (frontend)
make drift      # canonical shared/ copies are unedited (BLUEPRINT §15)
make types      # regenerate frontend/src/api/schema.d.ts from the backend's OpenAPI (offline)
make clean      # docker compose down -v (dev + e2e)
```

## Architecture

Multi-conversation chat over a local LLM (any OpenAI-compatible server), with a web UI
and a terminal CLI on the same use cases: hexagonal FastAPI backend (rich form, BLUEPRINT
§3b), React + TanStack Query frontend. **[`docs/architecture.md`](docs/architecture.md)**
is the overview: containers, backend layers and their diagram, the model, the streaming
flow, frontend layers, draft chat, where errors show, i18n, look and rendering.

### Gotchas while coding

- `MessageInput` is keyed by `threadKey`, which is bumped on select/new/delete but **not** when a draft is promoted to a real conversation — bumping it there remounts the composer and wipes staged text and attachments. Callers of `ensureConversation()` use the id it returns, never state read back.
- Conversation detail queries never refetch on their own (`staleTime: Infinity`, no refetch on focus): `useChatStream` writes optimistic messages into that cache entry. Don't add background refetches.
- Settings overrides: empty inputs map to `null` (= server default) — never `||`, never conflate `null` with `0`/`false`. Same on the backend: `None` override → default.
- After any backend schema change run `make types` and commit `frontend/src/api/schema.d.ts` with it; never edit that file.
- Hooks get the client from `useApi()` (deviation from Famiglia: openapi-fetch captures `fetch` at creation). Tests wrap in `ApiProvider` with the `src/test/` fakes, no `vi.mock`; there are no vitest globals, so a file with several rendering tests calls `afterEach(cleanup)`.
- Components never call `api`/`fetch`, never read status codes or `err.message`: they show `messageFor[lang]` for the error. No `console.error` in `src/`.
- A new UI string needs at least its English entry in `src/i18n/strings.ts` (missing `it`/`de` keys fall back to English); a new error code goes in `src/api/errors.ts`.
- `navigator.clipboard` is missing over plain HTTP on the LAN: copy through `utils/clipboard.ts`. Use `utils/uuid.ts`, never bare `crypto.randomUUID`.
- Colours are CSS vars from `index.css` (`var(--…)`), never inline hex (the one exception is `#fff` on the accent). Media queries go in `index.css` classes, not inline styles.
- boto3 (Garage) only through the anyio thread pool; services and domain never import `bcrypt`, `jwt` or boto3.

### E2E — Top-level `e2e/` (Playwright + TypeScript)

Black-box specs: `conversations.spec.ts` covers create, send, stream, persist, delete; `interactions.spec.ts` (stop/edit/retry/rename), `thinking.spec.ts`, `attachments.spec.ts` (upload → link → download round-trip against the e2e Garage; an over-limit upload shows its error), and `i18n.spec.ts` (switch language → UI translates + persists via `/auth/me`; the upload error in Italian). e2e users default to English, so the other specs keep asserting English text. Specs do not import frontend/backend types.

### Test strategy

| Layer               | Location                          | Database                                 | Runs with             |
|---------------------|-----------------------------------|------------------------------------------|-----------------------|
| Backend unit        | `backend/tests/unit/`             | In-process (no Postgres)                 | `make unit-backend`   |
| Frontend unit       | `frontend/src/**/*.test.ts(x)` (`src/test/` fakes) | n/a                     | `make unit-frontend`  |
| Backend integration | `backend/tests/integration/`      | Real Postgres via testcontainers         | `make integration`    |
| End-to-end          | `e2e/*.spec.ts` (Playwright)      | Real Postgres via `compose --profile app`| `make e2e`            |

### CI/CD

`.github/workflows/ci.yml` (on `main`, `ubuntu-24.04`): lint/typecheck/unit (backend
+ frontend, plus `make types && git diff --exit-code frontend/src/api/schema.d.ts` so a
stale generated schema fails the build) → integration → browser e2e → amd64 Docker build & push of `chatbot-api`
and `chatbot-frontend` to ghcr.io, tagged `sha-<short sha>` (pin it as `IMAGE_TAG` to
roll back), the branch name and `latest`.

## Conventions to keep

- **src-layout**: package at `backend/src/chatbot/`. Do not flatten.
- **Hexagonal layering**: `domain/` and `services/` never import from `adapters/` or `entrypoints/`.
- **`ChatLLM.stream_chat` is an async generator** yielding `LlmChunk` values — never a plain coroutine returning a list. It takes `(messages, system_prompt, params: ChatParams)`; generation params are **per-call**, resolved from the conversation's overrides, never baked into the adapter.
- **`send_message` two-UoW pattern**: one UoW to save the user message + build history, then stream, then a second UoW to save the assistant reply. This lets the user message commit before the LLM responds.
- **No `container_name`** on dev compose services (incl. `garage`/`garage-init`), so the `chatbot_e2e` project runs alongside the dev project.
- **All S3/Garage calls go through the anyio thread pool** — never call boto3 directly from an async path.
- **Attachment storage is a port with a null fallback**: `GARAGE_ENDPOINT` unset ⇒ `NullAttachmentStorage`, mirroring the LLM mock fallback.
- **E2E specs are black-box**: never import frontend/backend types.
- **Use cases yield plain event dicts; SSE framing lives in the router.** Streaming use cases yield the typed event union (see ADR-003); `routers/sse.py::sse_stream()` frames them for HTTP, and the CLI consumes the same dicts in-process via `cli/rendering.py::stream_events` (no SSE parsing).
