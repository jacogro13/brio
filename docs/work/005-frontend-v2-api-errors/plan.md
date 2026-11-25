# 005 — Plan

Spec: [spec.md](spec.md) (approved 2026-11-20)

## Approach
Add the new layer next to the old one, then move callers over, then delete the old
files. First the backend startup follows D4 (BLUEPRINT §3a, like Famiglia's `main.py`),
so the app imports with no env vars. Then `make types` + the CI staleness check. Then the canonical `client.ts` /
`messages.ts` and Chatbot's per-language `errors.ts`. Then the auth wiring. Then the
callers in three steps: auth calls + `AuthPage`, the SSE reader, the conversation calls
(which removes `http.ts`/`apiFetch`). Finally `src/types/` goes, and the docs and e2e
are updated. BLUEPRINT §4, §4b (F1, F3), §8 (`types`), §12 and §15 /
`shared/README.md` apply, with Famiglia's frontend as the worked example. No new ADR:
ADR-007 gets the decision on error text per language (see below), and `CLAUDE.md`
records it as a deviation from "codes become Italian text". No API change except
`/health` leaving the schema. No migration. The only backend runtime change is task 1
(startup in `lifespan`, CORS removed).

Decisions taken here, from the spec and the code:
- **Startup follows D4.** `create_app()` stays (tests build fresh apps with it) but
  only builds the app: no `get_settings()`, no `configure_logging()`, no CORS. The
  `lifespan` does, in order, `settings = get_settings()` (a missing `JWT_SECRET_KEY` /
  `DATABASE_URL` stops startup here), `configure_logging(settings.log_level)`, the
  `sqlalchemy.engine` level tweak, the "Starting Chatbot" log line, `start_mappers()`.
  Nothing else reads settings at import (the rate limit is a callable, `dependencies.py`
  and the CLI call `get_settings()` inside functions). Unit tests' `TestClient(app)`
  without `with` doesn't run `lifespan`, so `test_api.py`'s `Api.app` calls
  `configure_logging()` itself to keep its access-line tests; `tests/unit/conftest.py`
  keeps its env defaults (dependencies still read settings) but its comment no longer
  says "at import time". `/health` gets `include_in_schema=False`.
- **Error text per language.** `api/errors.ts` exports
  `messageFor: Record<Lang, (error: unknown) => string>`, one `makeMessageFor(table)`
  per language. `en` and `de` override every common code (the canonical table is
  Italian); `it` overrides only where Chatbot needs different words. Chatbot's codes:
  `invalid_credentials`, `username_taken`, `attachment_too_large`,
  `attachment_not_found`, `conversation_not_found`, `message_not_found`,
  `nothing_to_regenerate`, `invalid_token`, `token_expired`, `http_429` (login rate
  limit, shown on the login page). English `invalid_credentials` stays
  "Invalid username or password." so `auth.spec.ts` keeps passing. An unknown code
  gives the canonical (Italian) fallback in every language. That is accepted by the spec.
- **Components keep the error, not its text.** `AuthPage` stores the caught error
  (`unknown`) and renders `messageFor[lang](error)`, so the text follows a language
  switch.
- **401/403 handling sits outside `client.ts`.** `api/session.ts` holds token storage
  and `getUsername` (moved from `http.ts`), plus `makeAuthMiddleware(onRejected)`: its
  `onRequest` adds `Authorization: Bearer …` when there is a token. Its `onResponse`
  calls `onRejected()` on 401/403 **only if the request carried a token**. A wrong
  password (401 `invalid_credentials` on `/auth/login`, no token) must reach the form.
  `main.tsx` registers it on the app-wide `api` with
  `onRejected = clearToken + location.reload`. openapi-fetch runs `onResponse`
  last-registered-first, so it runs before the canonical `throwOnError`.
- **Streams.** The SSE routes are called through `api.POST(…, { parseAs: 'stream',
  signal })`, so HTTP failures become `ApiError` like any call. A pure
  `api/stream.ts::readEvents(body)` parses `data:` frames into `StreamEvent` and throws
  `new ApiError(200, event.code ?? 'unknown', null, event.message, null)` on an `error`
  event. `StreamEvent` is frontend-only (SSE isn't in OpenAPI), so it lives in
  `stream.ts`. `useChatStream` drops its `error` branch: the thrown `ApiError` lands in
  its existing `catch`, which still only logs (spec: stream errors stay silent).
- **Uploads / downloads.** Upload: `api.POST(…, { body, bodySerializer: () => form })`.
  Download: `parseAs: 'blob'`.
- **Types.** Backend shapes are aliases of `components['schemas'][…]`, declared where
  they're used (or in `api/` when several modules share them). `DraftConversation` /
  `ActiveChat` move next to `App`/`useChatStream`; `ToolEvent` moves to
  `ToolActivity.tsx`. `MessageResponse.tool_events` is `list[dict]` in the backend, so
  it's generated as `Record<string, unknown>[]`. The one cast to `ToolEvent[]` happens
  in `api/conversations.ts`, with a comment, not in a component.
- **`make types` without `.env`.** The BLUEPRINT §4 snippet with the rich-form import
  (`from chatbot.entrypoints.main import app`), unchanged otherwise: after task 1,
  importing needs no env vars and prints nothing to stdout. `.env` is loaded only if
  present (`if [ -f .env ]; then set -a && . ./.env && set +a; fi`), so the CI `test`
  job, which has no `.env`, can run it. `openapi-typescript` is pinned to an exact
  version, so CI and the laptop generate the same bytes.
- **Thin call functions stay for now.** `api/auth.ts` and `api/conversations.ts` keep
  their exported functions, rewritten on `api`. 006 replaces them with hooks.

## Tasks
| # | Task | Files | Check | Status |
|---|------|-------|-------|--------|
| 1 | **Backend startup follows D4; CORS out; `/health` out of the schema.** `entrypoints/main.py`: move `get_settings()`, `configure_logging`, the sqlalchemy level and the start log line into `lifespan` before `start_mappers()` (see *Approach*); remove `CORSMiddleware` and its import; `/health` route with `include_in_schema=False`. `entrypoints/settings.py`: drop `cors_origins`, `cors_allow_lan`. Remove the `CORS_ALLOW_LAN` line from `deployment/docker-compose.yml` (api `environment:`), its comment + line from `.env.example`, its row from `README.md`. `tests/unit/test_api.py`: `Api.app` calls `configure_logging()` (docstring updated). `tests/unit/conftest.py`: comment only. New tests in `tests/unit/test_startup.py`: `test_importing_the_app_needs_no_env_vars` (a `subprocess` running `sys.executable -c "import chatbot.entrypoints.main"` with `env` holding only `PATH`/`HOME`; exit code 0, empty stdout); `test_startup_without_a_required_setting_fails`, parametrized over `JWT_SECRET_KEY` / `DATABASE_URL` (`monkeypatch.delenv`, `get_settings.cache_clear()`, `with TestClient(create_app())` raises `ValidationError`); `test_health_is_not_in_the_schema` (and still answers `{"status": "ok"}`). The existing startup test keeps passing (env present). | `backend/src/chatbot/entrypoints/{main,settings}.py`, `backend/tests/unit/{test_startup,test_api,conftest}.py`, `deployment/docker-compose.yml`, `.env.example`, `README.md` | `make lint typecheck unit-backend`; `grep -rni cors backend/src deployment .env.example README.md` finds nothing | done |
| 2 | **`make types` + CI check.** Add `openapi-fetch` `0.17.0` (as Famiglia) and `openapi-typescript` (exact version, as in Famiglia's lockfile) to `frontend/package.json`. Add a `types: sync frontend/node_modules` target: the BLUEPRINT §4 snippet, rich-form import, `.env` optional (see *Approach*); add `types` to `.PHONY`. Generate and commit `frontend/src/api/schema.d.ts`. If ESLint complains about it, add it to `globalIgnores`. CI `test` job: after `npm ci`, a step `make types && git diff --exit-code frontend/src/api/schema.d.ts`. Nothing imports `schema.d.ts` yet. | `frontend/package.json`, `frontend/package-lock.json`, `Makefile`, `frontend/src/api/schema.d.ts`, `frontend/eslint.config.js` (if needed), `.github/workflows/ci.yml` | `mv .env .env.bak; make types; mv .env.bak .env` works with no db or server running; running `make types` twice leaves `git diff` empty; temporarily add a field to `ProfileResponse` → `make types && git diff --exit-code …` exits 1, then revert; `make lint typecheck` | done |
| 3 | **Canonical client + messages, per-language `errors.ts` (not wired).** Copy `shared/frontend/src/api/{client,messages}.ts` verbatim (headers unchanged). New `api/errors.ts` (shape and codes in *Approach*), with EN/IT/DE text. New `api/errors.test.ts`: `test.each` over `en`/`it`/`de` × `invalid_credentials`, `username_taken`, `attachment_too_large`, `network_error` → that language's text; `unknown code gives the fallback` per language; `never shows the backend message`; English `invalid_credentials` matches `/invalid username or password/i`. | `frontend/src/api/{client,messages,errors,errors.test}.ts` | `make unit-frontend`; `make drift` shows `client.ts` and `messages.ts` `current`; `make lint typecheck` | done |
| 4 | **Session + auth middleware.** New `api/session.ts`: `TOKEN_KEY`, `getToken`/`setToken`/`clearToken`/`getUsername` (moved from `http.ts`; `http.ts` re-imports them so its callers don't change yet), and `makeAuthMiddleware(onRejected)` (rule in *Approach*). `main.tsx`: `api.use(makeAuthMiddleware(() => { clearToken(); window.location.reload() }))`. Tests in `api/session.test.ts` with `createApiClient({ baseUrl, fetch: fake })` + the middleware, and a counting `onRejected` fake: `token_is_sent_as_bearer`; `rejected_token_calls_onRejected`, parametrized 401/403; `401_without_a_token_does_not_call_onRejected` (the wrong-password case) and still throws `ApiError` `invalid_credentials`; `getUsername` reads the claim, and returns `null` for garbage. | `frontend/src/api/{session,session.test,http}.ts`, `frontend/src/main.tsx` | `make unit-frontend lint typecheck` | done |
| 5 | **Auth calls + `AuthPage` on the new client.** Rewrite `api/auth.ts` (`register`/`login`/`getMe`/`patchLanguage`) on `api`, with body and profile types from `schema.d.ts`. `login` returns `data.access_token`. No local error handling: `ApiError` propagates. `AuthPage` keeps `error: unknown` and renders `messageFor[lang](error)`. Delete `api/auth.test.ts` (it asserts the old server-text behaviour; `errors.test.ts` and `session.test.ts` cover the new one). `i18n/index.tsx` and `App.tsx` import token helpers from `session.ts`. | `frontend/src/api/auth.ts`, `frontend/src/api/auth.test.ts` (delete), `frontend/src/components/AuthPage.tsx`, `frontend/src/i18n/index.tsx`, `frontend/src/App.tsx` | `make unit-frontend lint typecheck`; `grep -nE "\.message\|\.status" frontend/src/components/AuthPage.tsx` finds nothing | done |
| 6 | **SSE reader (not wired).** New `api/stream.ts`: `StreamEvent` (moved from `conversations.ts`, which re-exports it for now) and `readEvents(body: ReadableStream<Uint8Array>)` (behaviour in *Approach*). Tests in `api/stream.test.ts` with a hand-built `ReadableStream`: `yields_events_in_order`; `frame_split_across_chunks_is_joined`; `non_data_lines_are_ignored`; `error_event_throws_ApiError_with_its_code`; `error_event_without_code_is_unknown`; `stream_error_and_http_error_with_the_same_code_give_the_same_text` (`messageFor[lang]` on both, for each language). | `frontend/src/api/{stream,stream.test,conversations}.ts` | `make unit-frontend lint typecheck` | done |
| 7 | **Conversation calls on the new client; remove `http.ts`.** Rewrite `api/conversations.ts` on `api`: list/get/create/update/delete; `uploadAttachment` (FormData via `bodySerializer`); `downloadAttachment` (`parseAs: 'blob'`); `sendMessage`/`regenerate`/`editMessage` (`parseAs: 'stream'`, `signal`, then `readEvents`). The `ToolEvent[]` cast happens here. `useChatStream`: drop the `error` branch (the `ApiError` reaches the existing `catch`, still `console.error`; the `AbortError` check stays). Delete `api/http.ts` and the `StreamEvent` re-export. | `frontend/src/api/conversations.ts`, `frontend/src/api/http.ts` (delete), `frontend/src/hooks/useChatStream.ts` | `make unit-frontend lint typecheck`; `grep -rn "fetch(" frontend/src --exclude-dir=api` and `grep -rn "apiFetch\|api/http" frontend/src` find nothing | done |
| 8 | **Remove `src/types/`.** Replace the hand-written backend types with `components['schemas'][…]` aliases (`ConversationResponse`, `ConversationSummaryResponse`, `MessageResponse`, `AttachmentResponse`). Move `DraftConversation`/`ActiveChat` next to `useChatStream` (App imports them from there) and `ToolEvent` to `ToolActivity.tsx`. Fix optimistic `Message` builders in `useChatStream` for any newly required fields. Update the imports in `App.tsx`, the components and `ChatThread.test.tsx`. Delete `src/types/`. | `frontend/src/types/index.ts` (delete), `frontend/src/api/conversations.ts`, `frontend/src/hooks/useChatStream.ts`, `frontend/src/App.tsx`, `frontend/src/components/{ChatThread,ChatThread.test,ConversationList,ConversationSettings,MessageInput,ToolActivity}.tsx` | `make unit-frontend lint typecheck`; `cd frontend && npm run build`; `test ! -e frontend/src/types`; `grep -rnE "\.status\|\.message\|includes\(" frontend/src/components` shows no error inspection | done |
| 9 | **e2e.** `auth.spec.ts`: `wrong password in Italian shows the Italian error` (click `IT` on the auth page, wrong password → `messageFor.it` text for `invalid_credentials`, still on the auth page); `rejected token drops back to the auth page` (`addInitScript` puts a garbage `chatbot_token`, `goto('/')` → the Log in button is visible). The existing English specs stay unchanged. | `e2e/auth.spec.ts` | `make e2e` green (self-contained, see `CLAUDE.md`) | done |
| 10 | **Docs.** ADR-007: replace "Server-returned error `detail` strings … stay English" with: errors are shown from their `code` via `api/errors.ts`, one `messageFor` per language. Unknown codes give the canonical Italian fallback, and upload/stream errors are not shown yet (006). `CLAUDE.md` frontend section: replace the `http.ts`, `auth.ts`, `conversations.ts` and `src/types/` paragraphs with the new layout (`schema.d.ts` + `make types`, `client.ts`/`messages.ts` canonical, `errors.ts` per language as a **deviation** from §4b's Italian-only text, `session.ts` + auth middleware with the "only if a token was sent" rule, `stream.ts`). Add `client.ts`/`messages.ts` to the canonical-copies line, and the CI `schema.d.ts` step. Backend `entrypoints/` paragraph: settings and logging set up in `lifespan` (D4), no CORS, `/health` not in the schema. | `docs/adr/007-multilanguage.md`, `CLAUDE.md` | `grep -n "http.ts\|apiFetch\|src/types\|stay English" CLAUDE.md docs/adr/007-multilanguage.md` finds nothing; review reading | done |
| 11 | **Full gate.** `make -C Chatbot test` (lint, typecheck, unit, integration, e2e), `make -C Chatbot drift`, `make -C shared test`, then `make types` again with an empty `git diff`. Then hand the user the manual checks, on the dev stack the user starts: with the UI in German, a wrong password and registering a taken username show German text; corrupting `chatbot_token` in localStorage and reloading drops back to the auth page; a normal chat (send, stop, regenerate, upload, download) still works. | — | all green; user confirms the manual checks | done |
| 12 | **Enter on the auth page keeps the language** (added at the user's request, 2026-11-20, after review). The EN·IT·DE buttons sit inside the login `<form>` with no `type`, so they default to `submit`: pressing Enter clicks EN and flips the UI (and the error text) to English. `LanguageSwitcher.tsx`: `type="button"`. New `LanguageSwitcher.test.tsx`: `choosing a language does not submit the surrounding form` (inside a form with a counting `onSubmit`). `e2e/auth.spec.ts`: the Italian wrong-password spec presses Enter again instead of clicking the submit button. | `frontend/src/components/{LanguageSwitcher,LanguageSwitcher.test}.tsx`, `e2e/auth.spec.ts` | `make unit-frontend lint typecheck`; `make e2e` green | done |

## Risks
- **Database**: no migration, no schema change.
- **Backend startup (task 1).** Settings are now checked in `lifespan`: a missing
  `JWT_SECRET_KEY`/`DATABASE_URL` still stops the container at boot (unit-tested), just
  one step later. If anything still needed settings at import, it would surface as a
  failing test or startup; `make e2e` and CI's e2e job start the real image.
- **CORS removal.** Only a browser page served from another origin would notice; none
  exists (Vite proxy in dev, nginx in prod, same-origin). The `CORS_ALLOW_LAN` line
  leaves `deployment/docker-compose.yml`; a leftover value in any env is ignored
  (`extra="ignore"`), so nothing to add or remove on the mini-PC. The Deployer push
  carries the compose change.
- **Getting stuck on the auth page or in a reload loop.** Today login/register avoid
  `apiFetch` so that a 401 doesn't reload. With one client, that has to come from the
  "only if a token was sent" rule. Both sides are unit-tested (task 4), and the e2e
  covers wrong password (still shows the error) and rejected token (drops back to login)
  (task 9).
- **Streaming regressions** (send/stop/regenerate/edit, thinking, web tools) from
  moving SSE onto openapi-fetch's `parseAs: 'stream'`. Stop must still abort the
  request (`signal`). Covered by the existing e2e specs (`interactions`, `thinking`,
  `web-tools`, `conversations`) and the manual check.
- **Users will notice**: login/register error wording changes in every language,
  including English (same meaning; the e2e regex keeps matching). An unknown error code
  shows the Italian fallback even in an English or German UI (accepted by the spec).
  Nothing else changes on screen.
- **CI**: the new `schema.d.ts` step fails the pipeline, and so blocks deploy, if
  `make types` output differs between laptop and CI (versions, environment). That's
  guarded by the exact `openapi-typescript` pin, the `uv.lock`-pinned backend, and task 2
  checking that a run with no `.env` works (no settings are read at import after task 1).
- **Other apps, `Infrastructure/`, secrets, mini-PC env vars**: none.
- **Working tree**: the blocked first build left task 2's dependency pins, CI step and a
  workaround `types` target uncommitted on `work/005-frontend-v2-api-errors`. Task 2
  replaces that target with the BLUEPRINT snippet; task 1 is built and committed first,
  without those files.

---
Approved by: Jacopo Grotti · Date: 2026-11-20
