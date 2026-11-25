# 002 — Backend v2 foundations

App: Chatbot · Created: 2026-11-19
Status: shipped
<!-- draft → approved → building → in review → shipped | abandoned -->

## Why
Chatbot's backend predates Blueprint v2. Every part of it handles the basics its own way:
- Error classes are scattered: `ConversationNotFoundError` sits in
  `upload_attachment.py` and the auth errors in `services/user/_auth.py`.
- Routers `try/except` them into `HTTPException(detail=...)`.
- Settings are read in two places: a local `Settings` class for the API, and
  `os.environ` in the CLI.
- Logging is a bare `basicConfig` with no request id.
- Domain fields are loosely typed (`role: str`, `tool_events: list[dict]`).
- Nothing runs ruff or pyright on the backend.

This change gives the backend the same foundations as Famiglia. Later Chatbot changes
(imperative ORM mapping, auth ports, frontend v2) build on it. It is the second
Chatbot Blueprint v2 change, after 001 (CI and container fixes).

## What changes
Users see no difference: chat, attachments, tools, login and the CLI work as before.

- **Canonical files**: the app copies `shared/backend/` (`settings_base.py`,
  `domain/errors.py`, `domain/validated.py`, `entrypoints/error_handlers.py`,
  `entrypoints/logging_setup.py`) with their `# canonical:` headers.
  `make -C shared drift` is clean for Chatbot.
- **D1 validated domain**: domain entities mix in `Validated`, so fields are checked
  when an entity is created and on every assignment. Loose types become precise ones,
  e.g. `role` is a literal/enum and `tool_events` is a typed model, not `list[dict]`.
  Rules that span several fields live in entity methods.
- **D2 one error model**:
  - Every expected failure is a `DomainError` subclass with a stable `code`, defined
    in the domain, not in a service module.
  - Routers have no `try/except` for domain errors. One handler turns them into
    `{code, message, field}` with the right status.
  - Bad or expired tokens and rate limiting also answer in that shape.
- **SSE errors**: stream `error` events (conversation not found, message not found,
  nothing to regenerate) keep `message` and gain the same stable `code` as the
  matching domain error. The frontend and CLI keep working unchanged.
- **Frontend shim**: only `frontend/src/api/auth.ts` changes. It reads the new error
  body (`message`), so register and login errors still show a sensible text. Turning
  error codes into text properly (`messageFor`) is Frontend v2.
- **D4 settings**: one `AppSettings` (from `settings_base.py`), validated at startup,
  with no default passwords. The API and the CLI both use it. The CLI's
  `os.environ` reads go away.
- **D6 logging**: the canonical setup gives readable stdout lines with a request id,
  one access line per request, and every 500 logged with its traceback. `GET /health`
  writes no access line.
- **D3 quality gates**: `ruff format --check`, `ruff check` and `pyright` pass on
  `backend/`. They are part of `make lint` / `make typecheck` (so `make test` and
  `make test-backend`) and of CI.

## Out of scope
- Imperative ORM mapping. `DeclarativeBase` and the `*Model` classes stay; that is the
  next backlog item.
- Auth behind `PasswordHasher` / `TokenService` ports (D7). `bcrypt`/`jwt` stay where
  they are.
- Frontend v2: generated `schema.d.ts`, canonical `client.ts`, TanStack Query,
  `messageFor`, splitting large components. The only frontend change is the `auth.ts`
  shim above.
- v1 docs cleanup (MkDocs, trimming `CLAUDE.md`).
- Any change to API paths, request shapes, SSE event types or the database schema
  (no migration).

## Acceptance checks
- [ ] `make -C shared drift` reports no unlabelled edits in Chatbot, and the five
      canonical backend files are present with their headers.
- [ ] `grep -rn "except .*Error" backend/src/chatbot/entrypoints/routers` finds no
      `try/except` around domain errors, and `grep -rn "HTTPException"
      backend/src/chatbot/entrypoints/routers` finds nothing.
- [ ] `grep -rn "class .*Error" backend/src/chatbot/services` finds nothing: domain
      errors live in the domain.
- [ ] Unit tests show the error bodies `{code, message, field}`, with a test for each:
      - unknown conversation → 404 `not_found` (or a more specific code);
      - duplicate username → 409;
      - wrong password → 401;
      - oversized attachment → 413;
      - expired token → 401;
      - rate limit → 429.
- [ ] A unit test shows an SSE `error` event for an unknown conversation carries both
      `code` and `message`.
- [ ] Unit tests show an entity rejects an invalid field on creation **and** on
      assignment, e.g. an unknown `role`.
- [ ] Starting the API or the CLI with a required setting missing fails at startup,
      with an error that names the setting. `grep -rn "os.environ\|getenv"
      backend/src` finds nothing outside the settings module.
- [ ] `make lint` and `make typecheck` run ruff (format + check) and pyright on the
      backend as well as the frontend, and pass. CI runs them.
- [ ] `make test` passes (lint, typecheck, unit, integration, e2e).
- [ ] With `make backend` running, the log has a request id on each access line and
      no line for `GET /health`. A forced 500 is logged with its traceback.
- [ ] In the app: registering an existing username and logging in with a wrong
      password each show an error message, not a blank or generic crash. Chat, file
      upload and the CLI (`make cli`) work as before.
- [ ] After deploy, `chatbot_api` is `healthy` on the mini-PC, and you can log in and
      send a message.

## Open questions
<!-- none -->

---
Approved by: Jacopo Grotti · Date: 2026-11-19
