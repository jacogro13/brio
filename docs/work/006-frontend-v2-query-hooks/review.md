# 006 — Review

Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md) · Reviewed: 2026-11-20 (round 2)

Round 2, after task 11 (*Fixes from review*: opening a chat does not retry). The whole
change was re-read and every check re-run. Branch `work/006-frontend-v2-query-hooks`:
13 commits on `main` (spec/plan, tasks 1–10, the round-1 review, task 11), 51 files,
+2573 / −1126. Frontend, e2e and docs only. No backend, migration, compose or env change.

## Automated checks
- `make lint typecheck` (Chatbot/): **pass**. ruff format/check clean, eslint clean,
  pyright 0 errors, `tsc -b` clean.
- `make unit` (Chatbot/): **pass**. Backend unit green. Frontend vitest: 13 files, 67 tests
  passed, including the new `hooks/useActiveConversation.test.tsx` ("failed open sends one
  request").
- `make -C shared drift APP=Chatbot` (Apps/): **pass**. Every canonical file is `ok current`,
  including `frontend/src/api/client.ts` and `messages.ts`.
- `make integration` (Chatbot/): **pass**. 29 passed (testcontainers).
- `make e2e` (Chatbot/): **pending — run by user**. `CLAUDE.md` says the e2e stack is
  self-contained, so I ran it, but it could not start. The `chatbot_e2e` frontend failed
  with `Bind for 0.0.0.0:120 failed: port is already allocated`. The dev stack
  (`chatbot-frontend-1`, project `chatbot`) holds host port 120, probably left up from the
  manual check. I did not touch the dev stack. The failed `up` left the e2e containers
  running, so I tore them down with `docker compose -p chatbot_e2e --profile app down -v`
  (see the backlog line on the `e2e` target). No spec ran. Round 1's e2e run (17 passed) was
  on the code before task 11. Task 11 changes only `select()`'s retry, but the suite has not
  run on the final branch. To run it:
  `cd Chatbot && docker compose stop frontend && make e2e` (or stop the whole dev stack
  first). Expect 17 passed.

## Against the spec
- [x] **`@tanstack/react-query` dependency + `QueryClientProvider` in `main.tsx`.** Met.
  `frontend/package.json:15` (`^5.108.1`). `src/main.tsx` wraps `LanguageProvider`/`App` in
  `QueryClientProvider` (queries `retry: 1`, mutations `retry: false`).
- [x] **No component imports `api/` (except types).** Met. The spec's grep over
  `src/components` and `src/App.tsx` finds nothing. `App.tsx` has no `./api/` import.
  Components import only `messageFor` from `api/errors`, which the grep allows.
  `api/conversations.ts` and `api/auth.ts` are deleted.
- [x] **No `useEffect` fetches server data.** Met. `grep -rn -A3 useEffect` shows no `api`
  call inside an effect. The only effect on server data is `App.tsx:79` (`syncLanguage`
  on `profile`), which reads data and does not fetch. The one in `hooks/useApi.test.tsx`
  only records the client.
- [x] **`console.error` only for `getMe` / post-stream refresh.** Met, and stricter than
  asked: the grep finds no `console.error` at all. The approved plan makes both silent
  (see the notes).
- [x] **No file over 250 lines.** Met. The largest are `hooks/useChatStream.ts` (236),
  `components/MessageBubble.tsx` (208), `ConversationSettings.tsx` (205) and
  `MessageInput.tsx` (198).
- [x] **vitest: failed list load / rename / delete show the `messageFor` text in the banner;
  a failed delete keeps the chat.** Met. `components/ErrorBanner.test.tsx` covers this:
  "failed action shows its text in the banner" is parametrized over list load (500), rename
  and delete (404), with the exact EN text. "failed delete keeps the chat in the sidebar",
  "dismiss hides the banner" and "banner text follows the ui language" also pass. All use
  `FakeServer`, with no network.
- [x] **vitest: a stream `error` event shows its text under the thread; a stop shows nothing;
  the next send clears it.** Met by `components/StreamErrors.test.tsx`. The stop case is
  parametrized over a stop after the first token and a stop before any response. The second
  is the path where `client.ts` raises `network_error`, which the `controller.signal.aborted`
  check at `hooks/useChatStream.ts:125` suppresses. `api/stream.test.ts` adds "broken
  connection becomes network error" and "abort is rethrown as is".
- [x] **vitest: a failed upload shows its text by the input and stages no chip.** Met by
  `StreamErrors.test.tsx` "failed upload shows its text and stages no chip".
- [ ] **e2e: an over-limit upload shows "too large" (EN, and IT in the i18n spec).**
  **User to verify** (e2e pending, see above). Both specs exist: `e2e/attachments.spec.ts:76`
  and `e2e/i18n.spec.ts:111`. They passed in round 1 but have not run on the final branch.
- [ ] **Existing e2e specs pass unchanged in behaviour.** **User to verify** (same e2e run).
  The diff leaves every existing spec unchanged. `e2e/helpers.ts` changes only a comment.
- [x] **`grep -rn "apiFetch\|genericError" .github e2e frontend/src` finds nothing.** Met
  (empty).
- [x] **`npm run lint && npm run build`, `make unit-frontend`, `make drift` pass.** Met
  (`make lint typecheck`, `make unit` and drift above; `tsc -b` is the build's type step).
- [ ] **Manual: with the UI in Italian, stop the backend, click another chat → Italian banner,
  dismissible; restart → the same click works.** **User to verify.** The first manual try
  found the slow banner that task 11 fixes. No record shows the check passing after the fix.
  Steps (local dev stack, after the e2e run):
  1. `docker compose --profile app up --build` (frontend on http://localhost:120), log in,
     have at least 2 chats, switch the UI to **IT**.
  2. `docker compose stop api`.
  3. Click the other chat. Expect: the current chat stays on screen. Within about a second
     (no retry now), a banner at the top of the chat area shows the Italian text: "Server non
     raggiungibile…" or "Errore del server…", depending on how nginx answers (see the
     backlog item on 502/503/504 mapping in `client.ts`).
  4. Click × ("Chiudi"): the banner goes away.
  5. `docker compose start api`, click the same chat again: it opens, with no banner.

## Blueprint
- **F2 layering (`api/` → `hooks/` → `components/`).** Holds. Every server read is a
  `useQuery` (or `fetchQuery` in `select`). Every write is a `useMutation`, except download,
  which is a plain function on `useApi()` (as planned). `useChatStream` uses the same client
  and cache. `useAuth.ts` keeps `api/session` out of `App`.
- **§3c/§4b errors.** Holds. Components store the caught `unknown` and render
  `messageFor[lang](error)`. No component inspects `status`, `code` or `err.message`.
  `readEvents` (`api/stream.ts`, not canonical) wraps a broken read as
  `ApiError(0, "network_error")` and rethrows an `AbortError` unchanged.
- **Canonical copies.** Unchanged (drift `ok current`). No `+ local:` needed.
- **Hexagonal / ORM / UoW / migrations / route `try/except`.** Not touched (no backend
  change).
- **UI text.** EN/IT/DE per ADR-007 (Chatbot's documented deviation). The one new string,
  `dismiss` ("Dismiss" / "Chiudi" / "Schließen"), has all three languages.
- **Secrets / env.** Nothing secret committed and no new environment variable. Nothing to set
  on the mini-PC.
- **Weakened checks.** None. No new `eslint-disable` / `@ts-ignore` / `@ts-expect-error` /
  `noqa` / `pyright: ignore`, no `.only` / `.skip`, no deleted tests. The one edited test
  (`ChatThread.test.tsx`) only changes a type import path. No `TODO`, `console.log` or
  `debugger`.
- **Pure moves (tasks 2–3).** Checked by diff: `MessageBubble` matches the old in-file
  function except for the added `onDownloadError` pass-through. `CodeBlock`, `ActionButton`,
  `AttachmentChips`, `TopBar`, `Greeting`, `SidebarDrawer`, `PendingChips` and
  `ComposerToggles` carry over the old markup and styles.
- **Test style.** Hand-written `FakeServer` / `SeenClient`, no `vi.mock`, no network. Test
  names state the behaviour, and variations use `test.each`.

## Findings
- **note**: `frontend/src/hooks/useActiveConversation.ts:42` (task 11). `select()` now passes
  `retry: false` to `fetchQuery`. This matches the plan's *Approach* and *Risks*, where
  opening a chat does not retry. The test `hooks/useActiveConversation.test.tsx` builds a
  `QueryClient` with the app's own defaults (`queries.retry: 1`), so it guards the
  regression. It copies `main.tsx`'s defaults rather than importing them, so the two could
  drift apart. That is acceptable at this size.
- **note**: `frontend/src/App.tsx:162`. The stream-error line is drawn inside `ChatThread`,
  and `ChatThread` only renders when the open chat has messages. Suppose a first send in a
  new chat fails *before* the backend saves the user turn, and the post-stream refetch
  succeeds with no messages. Then the Greeting replaces the thread and the error is not
  shown. I could not find a realistic trigger. A lost connection also fails the refetch, so
  the optimistic message stays. A deleted conversation gives an `error` event whose refetch
  404s, which also keeps the cache. Recorded for visibility only.
- **note**: `frontend/src/hooks/useApi.ts` + `hooks/ApiProvider.tsx`. The plan named one file,
  `hooks/useApi.tsx`. It is split in two because react-refresh allows only component
  exports from a `.tsx`. The split is documented in `CLAUDE.md`. The existing backlog line
  (*Factory / Blueprint*, from the 006 plan) still says `hooks/useApi.tsx`. Use the two-file
  shape when it goes into §4b.
- **note**: `frontend/src/hooks/useConversations.ts:243`. `useUploadAttachment()` takes the
  conversation id as a mutation variable instead of a hook argument (the plan said
  `useUploadAttachment(conversationId)`). The code explains why: a draft gets its id only
  after the file is picked. Behaviour is the same.
- **note**: `frontend/src/components/MessageInput.tsx:331`. When an upload in a draft fails
  to *create* the chat, the error shows by the input, not in the banner. The plan puts only
  "a failed create on first **send**" in the banner, so this is consistent.
- **note**: `frontend/src/i18n/index.tsx:69`. `LanguageProvider` calls `api.PATCH("/auth/me")`
  through `useApi()` rather than a mutation hook, and ignores a failure. This was planned
  (task 7) and is documented as silent. `i18n/` is not `components/`, so F2 holds as the
  spec defines it.
- **note**: the spec says `getMe` and the post-stream refresh are "silent (console only)".
  The approved plan makes them fully silent, with no console output, so a failure there
  leaves no trace in the browser console. This was a plan decision, recorded for visibility.
- **note** (outside this change, sent to the backlog): `Makefile:63` (`e2e`). The cleanup
  trap is set only *after* `up -d --build --wait` succeeds, so a failed `up` leaves the
  `chatbot_e2e` containers running. The e2e frontend also publishes host port 120, the same
  as the dev stack, so `make e2e` cannot run while the dev stack is up. Famiglia and
  Registro_Spese have the same target.

No must-fix or should-fix findings.

## Verdict
**ready to ship once confirmed**: confirm (1) `make e2e` passes on the final branch, with the
dev stack's frontend stopped first (`cd Chatbot && docker compose stop frontend && make e2e`,
expect 17 passed, including the two new over-limit upload specs); and (2) the manual
acceptance check: UI in Italian → `docker compose stop api` → click another chat → an Italian
error appears in the banner within about a second → × dismisses it → `docker compose start
api` → the same click works. Lint, typecheck, unit (67 frontend tests), drift and
integration all passed.

Confirmed by user, 2026-11-20: (1) `make e2e` 17 passed on the final branch; (2) the manual
acceptance check passes after task 11.

---
Shipped: merge of work/006-frontend-v2-query-hooks · Date: 2026-11-20
