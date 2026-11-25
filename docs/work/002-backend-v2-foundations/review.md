# 002 — Review

Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md) · Reviewed: 2026-11-19

Reviewed on branch `work/002-backend-v2-foundations` (head `6aa4e60`), full diff
`git diff main...work/002-backend-v2-foundations` (92 files). Task 1 (shared v2) is commit
`64a5fef` in the `Apps/` repo.

## Automated checks
- `make lint typecheck` (Chatbot/): **pass**. ruff format: 114 files already formatted;
  ruff check: all checks passed; eslint clean; pyright 0 errors; `tsc -b` clean.
- `make unit` (Chatbot/): **pass**. Backend 147 passed (2 `InsecureKeyLengthWarning`s from
  test-only short JWT keys); frontend vitest 14 passed (3 files).
- `make -C shared drift APP=Chatbot` (Apps/): **pass**. The five backend files are `ok current`
  (errors/error_handlers at v2); `client.ts`/`messages.ts` not adopted (Frontend v2, out of scope).
- `make integration` (Chatbot/, testcontainers): **pass**. 24 passed.
- `make e2e` (Chatbot/, self-contained per CLAUDE.md, checked 2026-11-19): **pass**.
  13 passed, stack torn down with `down -v`.

## Against the spec
- [x] **Drift clean, five canonical files present with headers**: met. Drift output above;
  headers `# canonical: … v1/v2` on `domain/{errors,validated}.py`,
  `entrypoints/{error_handlers,logging_setup,settings_base}.py`.
- [x] **No try/except / HTTPException in routers**: met. `grep -rn "except .*Error"` and
  `grep -rn "HTTPException"` on `backend/src/chatbot/entrypoints/routers` return nothing.
- [x] **No error classes in services**: met. `grep -rn "class .*Error" backend/src/chatbot/services`
  returns nothing; errors live in `domain/conversation/model.py` and `domain/user/model.py`.
- [x] **Error bodies `{code, message, field}`**: met, `backend/tests/unit/test_api.py`:
  unknown conversation 404 `conversation_not_found` (`test_unknown_conversation_is_404`, 4 routes,
  exact body); duplicate username 409 (`test_duplicate_username_is_409`); wrong password 401
  (`test_bad_login_is_401`, exact body); oversized attachment 413 (`test_oversized_upload_is_413`,
  exact body); expired token 401 `token_expired` (`test_bad_token_is_401`); rate limit 429
  `http_429` with exactly those three keys (`test_login_over_the_rate_limit_is_429`).
- [x] **SSE error event carries code and message**: met,
  `tests/unit/test_conversation_use_cases.py:292`
  `test_stream_error_for_unknown_conversation_carries_code_and_message`.
- [x] **Entity rejects invalid field on creation and on assignment**: met,
  `tests/unit/test_model.py:63` / `:72` (unknown role), `:88` (language), `:101` (blank username),
  plus out-of-range conversation settings on assignment.
- [x] **Missing required setting fails at startup naming it; no env reads outside settings**:
  met. `tests/unit/test_settings.py` (`test_missing_jwt_secret_is_an_error`,
  `test_missing_database_settings_is_an_error`, `test_cli_reports_missing_setting_by_name` asserts
  `JWT_SECRET_KEY` in the CLI's output and exit 1). The API builds settings in `create_app()` at
  import, so a missing one stops uvicorn with a pydantic error naming the field.
  `grep -rn "os.environ\|getenv" backend/src` returns nothing (the settings module reads the
  environment through pydantic-settings).
- [x] **`make lint` / `make typecheck` run ruff + pyright; CI runs them**: met. Makefile `lint` /
  `typecheck`; `.github/workflows/ci.yml` gains "Lint (ruff)" and "Type check (pyright)" steps.
- [x] **`make test` passes**: met. Its parts were run one by one above: lint, typecheck,
  unit, integration, e2e all pass.
- [ ] **Logs with `make backend`**: **user to verify**. Covered in-process by
  `test_access_line_names_the_request_id`, `test_health_writes_no_access_line`,
  `test_unexpected_error_is_logged_with_traceback_and_hidden` (same `create_app()`, TestClient,
  not uvicorn). To try: `make backend`, open the app, and check that each access line has `req=<id>`,
  that `GET /health` (`curl -s localhost:5004/health`) writes no line, and that uvicorn's own access
  lines don't show up twice.
- [ ] **In the app (register/login errors, chat, upload, CLI)**: **user to verify**. The e2e suite
  passes (chat, stream, attachments, i18n, web tools), and `src/api/auth.test.ts` covers the message
  shim. To try: `make backend` + `make frontend`, register an existing username (expect "Username
  '…' is already taken"), log in with a wrong password (expect "Invalid username or password"), send
  a message, upload a file, then `make cli` and send one message.
- [ ] **After deploy, `chatbot_api` healthy, log in, send a message**: **user to verify** after the
  push (on the mini-PC: `docker ps --filter name=chatbot` shows `healthy`; log in and send).

## Blueprint
- **Layering**: holds. `domain/` and `services/` import no `adapters`/`entrypoints` (grep).
  Domain imports pydantic only through the `Validated` pattern (D1 as designed).
- **Canonical copies**: unchanged, drift `ok current`; only import lines differ (allowed by §15).
- **Routes never try/except domain errors (§3c)**: holds; one handler via `install_error_handlers`.
- **Components never inspect status codes / error text (§4b)**: unchanged by this change;
  `auth.ts` (an api module, not a component) now reads `message` only. Status-based token
  clearing in `http.ts` is untouched.
- **Unit of Work**: unchanged; `get_user_uow_factory` returns the same UoW typed for the user ports.
- **Imperative ORM mapping**: still declarative. Out of scope by the spec; already on the backlog.
- **Italian UI text**: no new UI text (Chatbot's UI is i18n EN/IT/DE per ADR-007). Error messages
  from the server are English, as before with `detail`.
- **Migrations**: none added. The eight existing Alembic files are changed by `ruff format` /
  pyupgrade only (typing imports, line wrapping); `revision`/`down_revision` values and operations
  are identical, so nothing changes for production.
- **Secrets / config**: nothing secret committed (`tests/unit/conftest.py` sets throwaway test
  values with `setdefault`). No new environment variables for the mini-PC; `DATABASE_URL` and
  `JWT_SECRET_KEY` were already required there.
- **Weakened checks**: no tests deleted or skipped. `test_update_unknown_conversation_returns_none`
  was renamed and now expects `ConversationNotFound` (the behaviour the plan asked for). One new
  suppression, `entrypoints/settings.py:71` `# pyright: ignore[reportCallIssue]`, with a reason,
  as the plan allows.

## Findings
- **should-fix** — `backend/src/chatbot/domain/conversation/model.py:21` (`MaxTokens = PositiveInt`)
  with `adapters/persistence/postgres/conversation_repository_impl.py:213-221`. The plan's pre-ship
  read-only check (plan.md, *Risks*) looks only at roles, languages and blank usernames, but D1 also
  makes every stored `max_tokens` and `temperature` pass validation on read. A stored
  `max_tokens <= 0` is possible: the settings input only has an HTML `min={1}`
  (`frontend/src/components/ConversationSettings.tsx:167`, the number can still be typed) and the old
  API accepted any int. Such a row makes `_to_domain_no_messages` raise `InvalidInput`, so
  `GET /conversations/` answers 422 for that user and the whole sidebar is empty.
  **Resolution: before shipping, run the extended read-only check below.** If it finds rows, widen the
  type (or decide on a data fix) before shipping; if it returns zeros, nothing to change.
- **note** — `backend/src/chatbot/entrypoints/schemas.py:11-12`: an orphan comment
  ("Supported UI + assistant languages; keep in sync with …") is left behind where `Language` used
  to be defined; it now describes nothing.
- **note** — Behaviour tightened by D1/D4, as intended: `PATCH /conversations/{id}` now answers 422
  for `max_tokens < 1` or `temperature` outside 0–2 (previously stored), and an unknown
  `CHATBOT_LANGUAGE` now stops the CLI at startup with a named error instead of falling back to English.
- **note** — `backend/src/chatbot/services/conversation/_streaming.py:153`: the `finally` that
  persists the assistant reply now runs `ToolEvent.from_json` on the tool records. A record failing
  validation there would lose the reply. The records are built by `tool_loop.py` in the right shape,
  so the risk is low; worth remembering if the tool protocol grows.
- **note** — `shared/` v2 of `errors.py` / `error_handlers.py` (commit `64a5fef` in `Apps/`) leaves
  Famiglia `outdated` in the drift check. The plan left the upgrade for later; added to the backlog.

## Verdict
**ready to ship once confirmed**: items 1 and 2 confirmed by user, 2026-11-19 (item 3 is after the push)

Confirm before `/ship`:
1. The extended read-only check on the mini-PC (it only reads) returns no bad rows, i.e. roles only
   `user`/`assistant`, languages only `en`/`it`/`de`, and the four counts all `0`:
   ```bash
   docker exec shared_postgres psql -U postgres -d chatbot -c "select distinct role from messages; select distinct language from users; select count(*) as blank_usernames from users where trim(username) = ''; select count(*) as bad_max_tokens from conversations where max_tokens is not null and max_tokens < 1; select count(*) as bad_temperature from conversations where temperature is not null and (temperature < 0 or temperature > 2); select count(*) as blank_filenames from attachments where filename = '';"
   ```
2. The manual checks under *Against the spec*: `make backend` logs (request ids, no `/health` line);
   taken username and wrong password show a message in the UI; chat, upload and `make cli` work.
3. After the push: `chatbot_api` healthy on the mini-PC, log in and send a message.

---
Shipped: merge of work/002-backend-v2-foundations · Date: 2026-11-19
