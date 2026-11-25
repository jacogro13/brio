# 002 — Plan

Spec: [spec.md](spec.md) (approved 2026-11-19)

## Approach
Bring Chatbot's backend (rich form, `backend/src/chatbot/`) onto BLUEPRINT §3c: D1, D2,
D3, D4, D6, with the canonical files from `shared/backend/` (§15, `shared/README.md`).
In the rich form the copies go under `backend/src/chatbot/…`; only their import lines
change (`from chatbot.domain.errors import …`).

**Shared change first.** The spec requires 401 for a wrong password and 413 for an
oversized attachment. `errors.py`/`error_handlers.py` v1 have no kinds for these.
BLUEPRINT §3c already says auth errors "arrive as v2 of the file with the first
migrated app that has users", and Chatbot is that app. So task 1 bumps both files to
v2 in `shared/`:
- `Unauthorized` → 401, `Forbidden` → 403, `PayloadTooLarge` → 413;
- `ERROR_RESPONSES` gains 401, 403, 413 and 429;
- §3c gets one updated line.

No local labels are needed.

**Rate limit and tokens.** slowapi's `RateLimitExceeded` is a Starlette `HTTPException`,
so the canonical handler already answers 429 with `{code: "http_429", …}`. The custom
429 handler in `main.py` goes away. A bad or expired token raises the domain error
`InvalidToken(Unauthorized)` from `get_current_user`, not `HTTPException`.

**Order.**
1. Gates first (ruff, then pyright), so every later task is written to them and the
   big mechanical diff lands alone.
2. Then canonical files with settings, logging and errors.
3. D1 last, because it touches the most code paths and the persistence mapping.

**No new ADR.** ADR-003 (SSE protocol) is amended for the error event's `code`.

**HTTP tests.** Error bodies and logging need HTTP-level unit tests, which the backend
doesn't have yet. Task 5 adds `tests/unit/test_api.py`:
- FastAPI `TestClient` over the app, with `app.dependency_overrides` pointing at the
  fakes in `tests/unit/fakes.py`;
- env set with `monkeypatch` and `get_settings.cache_clear()`;
- no network and no DB.

If `main.py`'s import-time `get_settings()` gets in the way, `main.py` gets a small
`create_app()`.

## Tasks

| # | Task | Files | Check | Status |
|---|------|-------|-------|--------|
| 1 | **shared v2 error kinds.** Add `Unauthorized` (401, `code="unauthorized"`), `Forbidden` (403) and `PayloadTooLarge` (413) to `shared/backend/domain/errors.py`. Map them in `error_handlers.py`; `ERROR_RESPONSES` covers 400/401/403/404/409/413/422/429/500. Bump both headers to v2 and update the §3c "Auth errors…" line in BLUEPRINT. | `shared/backend/domain/errors.py`, `shared/backend/entrypoints/error_handlers.py`, shared tests, `BLUEPRINT.md` §3c | `make -C shared test`. New parametrized test: each new kind → its status and `{code, message, field}`. `make -C shared drift` shows Famiglia `outdated`, not FAIL. | | done |
| 2 | **Ruff gate.** Add the §3c `[tool.ruff]` block to `backend/pyproject.toml` (rich form: `src = ["src"]`), with `ruff` in the `dev` group. Run `ruff format` over `src`/`tests` (mechanical, its own commit). Fix the ~150 `ruff check` findings: `--fix` for the safe ones, and FastAPI `Depends`/`File` defaults (B008, 63) move to `Annotated[...]`. Fix B904 with `from`; noqa only with a reason. `make lint` also runs `ruff format --check` + `ruff check` in `backend/`; CI gets the same step. | `backend/pyproject.toml`, `backend/src/**`, `backend/tests/**`, `Makefile`, `.github/workflows/ci.yml` | `make lint` passes. `make unit-backend integration` passes (behaviour unchanged). | | done |
| 3 | **Pyright gate.** Add `[tool.pyright]` (standard, `venvPath = "."`, `venv = ".venv"`), with `pyright` in `dev`. Fix the 28 errors, e.g. `send_message.py:102` gets an `AsyncGenerator` type so `aclosing` accepts it. Baseline only with `# pyright: ignore[<rule>]` plus a reason. `make typecheck` also runs `uv run pyright` in `backend/`. `make test-backend` = `lint typecheck unit-backend integration` (as in Famiglia). CI step. | `backend/pyproject.toml`, `backend/src/**`, `Makefile`, `ci.yml` | `make typecheck` passes. `make test-backend` passes. | | done |
| 4 | **Canonical files + D4 settings.** Copy the five `shared/backend/` files (errors/error_handlers at v2) into `src/chatbot/{domain,entrypoints}/` and `entrypoints/settings_base.py`; fix only the import lines. Add a `drift` target to the Makefile (`make -C ../shared drift APP=Chatbot`). Move `Settings` to `entrypoints/settings.py` as `Settings(AppSettings)` with every current field, plus `chatbot_cli_user` and `chatbot_language`, which keep the env names `CHATBOT_CLI_USER`/`CHATBOT_LANGUAGE`. `jwt_secret_key` is required. The engine uses `settings.sqlalchemy_url("postgresql+asyncpg")`. The CLI's `build_context`/`resolve_user_id` read `get_settings()`. `.env` is still found by the existing `_find_dotenv`, and a validation error is shown as a clean exit naming the setting. No `os.environ`/`getenv` left outside the settings module. | `entrypoints/{settings,settings_base,error_handlers,logging_setup}.py`, `domain/{errors,validated}.py`, `entrypoints/dependencies.py`, `entrypoints/main.py`, `entrypoints/cli/{dependencies,main}.py`, `Makefile`, `tests/unit/test_settings.py` | `make drift` passes. Tests: `test_missing_jwt_secret_is_an_error`; `test_missing_database_settings_is_an_error`; `test_database_url_or_db_parts_are_accepted` (parametrized); `test_cli_reports_missing_setting_by_name` (`capsys`). `grep -rn "os.environ\|getenv" backend/src` hits only the settings module. `make test-backend`. | | done |
| 5 | **D6 logging + HTTP test harness.** `main.py` calls `configure_logging(settings.log_level)` and adds `RequestIdMiddleware`. `basicConfig` and the `LOG_LEVEL` read go away; SQLAlchemy engine logs stay quiet below DEBUG. Add `tests/unit/test_api.py` (harness described in Approach). | `entrypoints/main.py`, `tests/unit/test_api.py`, `tests/unit/conftest.py` if needed | Tests: `test_responses_carry_a_request_id_header`; `test_access_line_names_the_request_id` (`caplog`); `test_health_writes_no_access_line`; `test_unexpected_error_is_logged_with_traceback_and_hidden` (500 `internal_error`). `make test-backend`. | | done (also installs the error handlers from task 6: its 500 test needs them) |
| 6 | **D2 conversation errors.** `main.py` sets `FastAPI(responses=ERROR_RESPONSES)` and calls `install_error_handlers(app)`. In `domain/conversation/model.py`, add `ConversationNotFound`, `MessageNotFound`, `AttachmentNotFound` (`NotFound`), `NothingToRegenerate` (`Conflict`) and `AttachmentTooLarge` (`PayloadTooLarge`). The get/update/delete/download/upload use cases raise them instead of returning `None` or raising the local classes; the local classes in `upload_attachment.py` go away. `routers/conversations.py` loses every `try/except` and `HTTPException`. Update the existing use-case tests to expect the errors. | `domain/conversation/model.py`, `services/conversation/{get,update,delete,download_attachment,upload_attachment}_*.py`, `entrypoints/main.py`, `entrypoints/routers/conversations.py`, `tests/unit/test_conversation_use_cases.py`, `test_attachments.py`, `test_api.py` | `test_api.py` (parametrized over the routes): unknown conversation → 404 `conversation_not_found`; another user's conversation → 404 too; unknown attachment → 404; oversized upload → 413 `attachment_too_large`; body is exactly `{code, message, field}`. Router `grep`s from the spec find nothing. `make test-backend`. | | done (handlers were installed in task 5) |
| 7 | **D2 auth errors + frontend shim.** In `domain/user/model.py`, add `UsernameTaken` (`Conflict`), `InvalidCredentials` (`Unauthorized`), `InvalidToken` (`Unauthorized`, codes `invalid_token`/`token_expired`) and `UserNotFound` (`NotFound`). Remove them from `services/user/_auth.py`; `/auth/me` raises `UserNotFound` without `try/except`. `get_current_user` raises `InvalidToken` and keeps chaining with `from`. Remove the custom 429 handler. `frontend/src/api/auth.ts` reads `err.message` (falling back to the current texts); its comment is updated. | `domain/user/model.py`, `services/user/{_auth,register_user,login_user}.py`, `entrypoints/{dependencies,main}.py`, `entrypoints/routers/auth.py`, `frontend/src/api/auth.ts` (+ `auth.test.ts`), `tests/unit/test_user_use_cases.py`, `test_api.py` | Tests: duplicate username → 409 `username_taken`; wrong password → 401 `invalid_credentials`; expired token → 401 `token_expired`; garbage token → 401 `invalid_token`; login over the limit → 429 `http_429` (limit lowered via settings); vitest `register_shows_server_message_on_conflict` / `login_falls_back_when_body_is_not_json`. `grep -rn "class .*Error" backend/src/chatbot/services` finds nothing. `make test-backend`, `make unit-frontend`. | | done |
| 8 | **SSE error codes.** Send/regenerate/edit yield `{"type": "error", "code": err.code, "message": err.message}` from the domain error instance, via one helper in `services/conversation/_streaming.py` (`ConversationNotFound`, `MessageNotFound`, `NothingToRegenerate`). `frontend/src/api/conversations.ts`'s event type gets an optional `code` (type only). The CLI rendering stays as is. Amend ADR-003's event list and CLAUDE.md's protocol line. | `services/conversation/{_streaming,send_message,regenerate_message,edit_message}.py`, `frontend/src/api/conversations.ts`, `docs/adr/003-typed-sse-event-protocol.md`, `CLAUDE.md` | Parametrized tests: each stream's error event for an unknown conversation/message carries `code` and `message`. Existing CLI rendering test still passes. `make test-backend`, `make unit-frontend`, `make typecheck`. | | done |
| 9 | **D1 validated domain.** `Attachment`, `Message`, `Conversation` and `User` mix in `Validated`, with types:<br>• `Role = Literal["user", "assistant"]`; `Language = Literal["en", "it", "de"]`;<br>• `NonBlankStr` for `filename`/`username`; `size: NonNegativeInt`; `temperature: confloat(0, 2) \| None`; `max_tokens: PositiveInt \| None`;<br>• `tool_events: list[ToolEvent] \| None`, where `ToolEvent` is a validated dataclass with every key the tool loop writes today (`id`, `tool`, `query`/`url`, `ok`, `summary`, `results`). Keys a row may lack are optional, so existing rows load.<br>The persistence `_to_domain`/save code converts JSON ↔ `ToolEvent` (no schema change). `tool_loop.py` builds `ToolEvent`s. `schemas.py` reuses `Role`/`Language`. `Conversation.add_message` stays the place where the title is set. | `domain/conversation/model.py`, `domain/user/model.py`, `services/conversation/tool_loop.py`, `adapters/persistence/postgres/{conversation_repository_impl,user_repository_impl}.py`, `entrypoints/schemas.py`, `tests/unit/test_model.py`, `tests/integration/test_conversation_repository.py` | Parametrized tests, each side of a rule: unknown `role` rejected on creation **and** on assignment; `language="fr"` rejected, `"it"` allowed; blank username rejected. Integration: `test_legacy_tool_events_row_loads` (a row written in today's JSON shape, incl. a failed fetch with no `results`, round-trips); `test_tool_events_round_trip`. `make test-backend`. | | done |
| 10 | **Full gate + docs.** Run `make test` (lint, typecheck, unit, integration, e2e; e2e is self-contained, checked 2026-11-19) and `make drift`. Update CLAUDE.md's `make lint`/`typecheck`/`test-backend` lines and settings notes, and the error-model sentence in the Architecture section. Then check by hand: `make backend` logs (request ids, no `/health` line); registering a taken username and a wrong login in the UI show a message; chat, upload and `make cli` work. | `CLAUDE.md` | `make test` green; `make drift` passes; the manual checks from the spec are ticked in the review. | | done (manual checks left for Jacopo: no dev servers) |

## Risks
- **No database migration.** The schema is unchanged.
- **D1 changes how existing rows load.** `_to_domain` builds entities through their
  constructors, so validation now runs on every row read. A historical row that breaks
  a new constraint would turn reading that conversation into a 500. Task 9 guards
  against this:
  - `ToolEvent` and the literals cover every value the code has ever written:
    roles `user`/`assistant`, languages `en`/`it`/`de`, and tool events with optional
    keys;
  - the legacy-row integration test.

  Before ship, run a read-only check on the mini-PC (see below). If it finds other
  values, widen the types rather than migrate.
- **Settings at startup.** `jwt_secret_key` and `DATABASE_URL` were already required by
  the API. Now the CLI needs `JWT_SECRET_KEY` too (it's in `.env`, so `make cli` is
  unaffected). Production sets `DATABASE_URL` in `deployment/docker-compose.yml`, so
  `AppSettings`' `DB_*` defaults are never used there. No new env vars on the mini-PC.
- **Behaviour users could notice.**
  - Register/login errors now show the backend's `message` (English, as before with
    `detail`).
  - Logs on the mini-PC change format.
  - API paths, request bodies and SSE event types are unchanged; error bodies change
    shape, and only `auth.ts` reads them.
  - A 401/403 still clears the token in `http.ts` (by status, unchanged).
- **Other apps.** Task 1 bumps two canonical files to v2. Famiglia (and any other
  adopter) shows `outdated` in `make -C shared drift`, which doesn't fail. Its upgrade
  is a later factory job.
- **Big mechanical diff.** Task 2's `ruff format` touches ~39 files. It is committed on
  its own, before any logic change, so the review can skip it as formatting only.
- **Pyright in CI** downloads its Node runtime on first run. If that's flaky, pin the
  `pyright` version in the `dev` group.

Read-only check before ship (Jacopo runs it on the mini-PC; it only reads):
```bash
docker exec shared_postgres psql -U postgres -d chatbot -c "select distinct role from messages; select distinct language from users; select count(*) from users where trim(username) = '';"
```

---
Approved by: Jacopo Grotti · Date: 2026-11-19
