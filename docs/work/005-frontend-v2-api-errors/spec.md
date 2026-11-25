# 005 — Frontend v2: API layer and errors

App: Chatbot · Created: 2026-11-19
Status: shipped
<!-- draft → approved → building → in review → shipped | abandoned -->

## Why
Since 002 the backend answers every failure with a stable `{code, message, field}`,
and stream `error` events carry the same `code`. The frontend ignores the codes. It
shows the backend's English `message` (e.g. a wrong password on the login page), or a
hard-coded English string. So an Italian or German user (ADR-007) reads English
errors in an otherwise translated UI.

The frontend is still v1. Backend types are copied by hand into `src/types/`, and
calls go through hand-written `api/http.ts` / `api/conversations.ts` / `api/auth.ts`
with `throw new Error("Failed to …")`. Components read `err.message`.

Generating types offline (`make types`) needs the app to import with no env vars
(BLUEPRINT §3a, D4: settings are checked in `lifespan`, not at import). Chatbot's
`create_app()` breaks that: it reads settings and configures logging when the module
is imported, and it needs settings there only for CORS, which the browser never uses
(it always reaches the API same-origin through the Vite proxy or nginx).

This is part 1 of 2 of Chatbot's Frontend v2 migration (BLUEPRINT F1 + F3 errors).
Part 2 (006) does TanStack Query hooks (F2) and splits `App.tsx` / `ChatThread.tsx`.

## What changes
For users, screens and flows stay the same. The visible difference: **login and
register failures now appear in the user's language (EN/IT/DE)**, not as English server
text. These are the only errors the app shows on screen today.

Upload, download and stream failures are only logged to the console today, and they
stay that way. They still become `ApiError`s with a code, and `errors.ts` already has
their text (e.g. `attachment_too_large`), so 006 only has to show them.

Behind the scenes:
- **Backend startup follows D4 (like Famiglia's `main.py`).** Importing the app needs
  no env vars; settings are validated and logging configured in `lifespan`, so a
  missing setting still stops the app at boot. CORS is removed, together with its
  settings (`cors_origins`, `cors_allow_lan`) and the `CORS_ALLOW_LAN` lines in
  `deployment/docker-compose.yml`, `.env.example` and the README. `GET /health` stays
  but leaves the OpenAPI schema (`include_in_schema=False`, BLUEPRINT §7).
- **Generated types (F1).** `make types` exports the OpenAPI schema offline (no server,
  no database) and generates `src/api/schema.d.ts`. Hand-written copies of backend types
  are gone. Frontend-only types live next to the code that uses them.
- **One client (F1).** The canonical `api/client.ts` is adopted unedited. Chatbot's own
  wiring (Bearer token, a 401 dropping back to the auth page) sits outside it. Every
  failure, including stream failures, becomes an `ApiError` with a code.
- **Errors shown, not parsed (F3).** The canonical `api/messages.ts` is adopted unedited.
  Chatbot's `api/errors.ts` builds one `messageFor` per language (EN/IT/DE) with
  `makeMessageFor`, covering Chatbot's codes and overriding the common ones. Components
  show the text for the current UI language. They never read `err.message`, status codes
  or server text.
- **CI catches a stale `schema.d.ts`.** A CI step runs `make types` and fails if
  `frontend/src/api/schema.d.ts` changes (backlog: *Factory / Blueprint*, done here for
  Chatbot only).
- ADR-007's note that "server error text stays English" is updated. `CLAUDE.md`'s
  frontend section describes the new layout.

## Out of scope
- TanStack Query hooks, removing `useEffect` fetching, splitting `App.tsx` /
  `ChatThread.tsx` (that is 006).
- Showing failures that are only logged to the console today (list, load, rename,
  delete, upload, download, stream errors): they stay silent until 006.
- Other backend changes: no new error codes, no server-side translation, no API
  change beyond `/health` leaving the schema. In particular, a
  stopped LLM still cuts the stream off with no `error` event; an `llm_unavailable`
  stream error is a later spec.
- Changing shared `client.ts` / `messages.ts`. In particular, the fallback text for an
  *unknown* code stays the canonical Italian one in every language, and a 502/503/504
  from the proxy still shows as `internal_error` (backlog: *Factory / Blueprint*).
- Any visual or behavioural change beyond the error texts.
- The same D4 / CORS check in the other apps.
- The CI check for the other apps.

## Acceptance checks
- [ ] Backend unit test: importing `chatbot.entrypoints.main` with no env vars set
      succeeds; starting the app (`lifespan`) with a required setting missing fails.
- [ ] `grep -rni "cors" backend/src deployment .env.example README.md` finds nothing.
- [ ] `/health` still answers `{"status": "ok"}` (healthchecks green in `make e2e`)
      and is not in `app.openapi()["paths"]`.
- [ ] `make types` runs with no server, no database and no `.env`, and regenerates
      `frontend/src/api/schema.d.ts`; running it again leaves `git diff` empty.
- [ ] `frontend/src/types/` no longer holds hand-written backend types, and no file in
      `frontend/src` outside `src/api/` calls `fetch(`
      (`grep -rn "fetch(" frontend/src --exclude-dir=api`).
- [ ] `grep -rnE "\.status|\.message|includes\(" frontend/src/components` finds no
      error inspection.
- [ ] vitest: for each of `en`, `it`, `de`, `messageFor` gives Chatbot's text for
      `invalid_credentials`, `username_taken`, `attachment_too_large`, and a common code
      (`network_error`). An unknown code gives the fallback.
- [ ] vitest: a stream `error` event with a code becomes an `ApiError` with that code,
      so `messageFor` gives it the same text as the HTTP error with that code.
- [ ] `make -C shared drift` lists Chatbot's `client.ts` and `messages.ts` as adopted
      and unedited.
- [ ] `cd frontend && npm run lint && npm run build` and `make unit-frontend` pass.
- [ ] `make e2e` passes (existing English specs unchanged). A new e2e spec shows that a
      wrong password with the UI in Italian shows the Italian error text.
- [ ] An invalid or expired token still drops back to the auth page (existing e2e, or
      in the app: clear/corrupt `chatbot_token` in localStorage and reload).
- [ ] CI check: after changing a backend response model without running `make types`,
      `make types && git diff --exit-code frontend/src/api/schema.d.ts` fails locally,
      and the CI workflow runs that step.
- [ ] In the app, with the UI in German: a wrong password and registering a taken
      username each show German text.

## Open questions
<!-- none -->

---
Approved by: Jacopo Grotti · Date: 2026-11-20
