# 005 — Review

Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md) · Reviewed: 2026-11-20 (round 2)

Branch `work/005-frontend-v2-api-errors` (12 task commits, d9d8d58..ff60ea4), compared
with `git diff main...work/005-frontend-v2-api-errors`. All 12 plan tasks are `done`.
Round 2 because task 12 (`ff60ea4`, the Enter key on the auth page) was added after the
first review (`3eb6fad`). The whole diff was read again, not just task 12.

## Automated checks
- `make lint typecheck` (Chatbot): **pass**. Ruff format/check clean, eslint clean, pyright 0 errors, `tsc -b` clean.
- `make unit` (Chatbot): **pass**. Backend 158 passed. Frontend vitest 44 passed (6 files, including the new `LanguageSwitcher.test.tsx`).
- `make -C shared drift APP=Chatbot` (from `Apps/`): **pass**. All 10 canonical copies are `current`, including `frontend/src/api/client.ts` and `frontend/src/api/messages.ts`.
- `make integration` (Chatbot, testcontainers): **pass**. 29 passed.
- `make e2e` (Chatbot, self-contained per `CLAUDE.md`): **pass**. 15 passed, stack torn down with `down -v`.
- `cd frontend && npm run build`: **pass** (only the usual >500 kB chunk warning).
- Offline type generation, run by the reviewer: exported OpenAPI under `env -i PATH HOME` (no `.env`, no db, no server), ran `openapi-typescript` into the scratchpad, and compared with `cmp`. The result is byte-identical to the committed `frontend/src/api/schema.d.ts`.
- Task 12's test checks the fix, verified by the reviewer: in a scratch copy of `frontend/` with `type="button"` removed from `LanguageSwitcher.tsx`, `LanguageSwitcher.test.tsx` fails (the form gets submitted). With the fix it passes.

## Against the spec
- [x] Import with no env vars works; startup fails if a required setting is missing. **Met**: `backend/tests/unit/test_startup.py::test_importing_the_app_needs_no_env_vars` and `test_startup_without_a_required_setting_fails[JWT_SECRET_KEY|DATABASE_URL]` both pass.
- [x] `grep -rni cors backend/src deployment .env.example README.md` finds nothing. **Met**: the reviewer ran it and got empty output.
- [x] `/health` answers and is not in the schema. **Met**: `test_health_is_not_in_the_schema_but_still_answers`, and the api healthcheck went green in `make e2e`.
- [x] `make types` works offline without `.env` and gives the same output twice. **Met**: the `types` target loads `.env` only if it exists. The reviewer's run with an empty environment was byte-identical to the committed file. `openapi-typescript` is pinned to `7.13.0`.
- [x] `src/types/` is gone and there is no `fetch(` outside `src/api/`. **Met**: `frontend/src/types` does not exist, and the grep finds nothing.
- [x] No error inspection in components. **Met**: `grep -rnE "\.status|\.message|includes\(" frontend/src/components` finds nothing.
- [x] vitest: per-language text for each code, plus the fallback. **Met**: `frontend/src/api/errors.test.ts`.
- [x] vitest: a stream error gives the same text as an HTTP error. **Met**: `frontend/src/api/stream.test.ts`.
- [x] drift lists `client.ts` and `messages.ts` as adopted and unedited. **Met** (see *Automated checks*).
- [x] lint, build and `make unit-frontend` pass. **Met.**
- [x] `make e2e` passes, including the new Italian wrong-password spec. **Met**: `e2e/auth.spec.ts` `wrong password in Italian shows the Italian error` now submits with Enter, so it also covers task 12. The existing English specs are unchanged.
- [x] An invalid token drops back to the auth page. **Met**: `e2e/auth.spec.ts` `rejected token drops back to the auth page`. Unit side: `session.test.ts` covers 401/403 with a token and 401 without one.
- [x] CI check for a stale schema. **Met**: the `.github/workflows/ci.yml` step "Generated API types are up to date" runs after `npm ci`. In round 1 the reviewer showed that a changed schema makes it fail. Nothing in that path has changed since.
- [ ] German text in the app for a wrong password and a taken username. **User to verify** (steps under *Verdict*). The texts are unit-tested (the `de` rows in `errors.test.ts`).

## Blueprint
- **D4 startup (§3a)**: holds. `create_app()` only builds the app. `lifespan` runs `get_settings()` → `configure_logging` → `start_mappers()`.
- **F1 / F3 (§4, §4b)**: hold. There is one client, every failure is an `ApiError`, and `AuthPage` renders `messageFor[lang](error)`. The per-language `errors.ts` is a documented deviation (ADR-007, `CLAUDE.md`), which the spec accepted.
- **Canonical copies (§15)**: unchanged; drift reports `current`.
- **Layering, imperative ORM, UoW, no `try/except` in routes**: no backend domain or route code changed apart from `main.py` / `settings.py`.
- **Italian UI text**: Chatbot is EN/IT/DE by ADR-007. Task 12 adds no UI text.
- **Migrations**: none.
- **Secrets / env**: none added. `CORS_ALLOW_LAN` is removed from compose, and a leftover value is ignored. Nothing to set on the mini-PC.
- **Weakened checks**: `frontend/src/api/auth.test.ts` is deleted, as task 5 planned. The diff adds no `noqa`, `pyright: ignore`, `eslint-disable`, `@ts-ignore` or skipped tests.
- **Scope**: every changed file is listed in the plan.

## Findings
- **note**: Task 12 (`frontend/src/components/LanguageSwitcher.tsx:18`, `type="button"`) was added after the first review. `plan.md` marks it "added at the user's request". The reviewer cannot check that request. The fix is small and serves the spec's main goal: before it, pressing Enter on the login form clicked "EN", so an Italian or German user saw the error in English. The tab buttons in `AuthPage.tsx` already had `type="button"`. Nothing else in the change moved.
- **note** (carried over from round 1, already in the backlog): stopping a stream before the response headers arrive is logged as `network_error`, not ignored. The cause is `frontend/src/api/client.ts:55` (canonical); the `AbortError` check at `frontend/src/hooks/useChatStream.ts` no longer matches in that window. Today it only means a `console.error`. It must be fixed in `shared/` before 006 shows stream errors.
- **note** (carried over): stale comments mention the removed `apiFetch` at `.github/workflows/ci.yml:71` and `e2e/helpers.ts:29`; `ci.yml:70` still says "all 12 specs". Fix them in 006.
- **note** (carried over): the `genericError` UI string (`frontend/src/i18n/strings.ts:36,112,180`) has no users any more. Remove it, or reuse it in 006.
- **note** (carried over): `uploadAttachment` passes a placeholder `body: { file: "" }` and the real `FormData` through `bodySerializer` (`frontend/src/api/conversations.ts:48`). This is the documented openapi-fetch workaround, with a comment, and the upload e2e covers it.

No must-fix or should-fix findings.

## Verdict
**ready to ship once confirmed**

To confirm, on the dev stack the user starts (`make backend` / `make frontend`, or the usual dev compose):
1. On the auth page, switch the UI to **DE**. Enter a wrong password and press **Enter**. Expected: "Ungültiger Benutzername oder ungültiges Passwort.", and the UI stays in German. On the register tab, try an existing username. Expected: "Dieser Benutzername ist bereits vergeben."
2. (Plan task 11 manual check, also covered by e2e) After logging in, send a message, stop it mid-stream, regenerate, then upload a file and download it again. Everything should work as before.

No new review round is needed once these are confirmed.

Confirmed by user, 2026-11-20 (items 1 and 2).

---
Shipped: merge of work/005-frontend-v2-api-errors · Date: 2026-11-20
