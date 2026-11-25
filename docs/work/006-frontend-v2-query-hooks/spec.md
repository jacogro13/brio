# 006 — Frontend v2: query hooks, visible errors, smaller components

App: Chatbot · Created: 2026-11-20
Status: shipped
<!-- draft → approved → building → in review → shipped | abandoned -->

## Why
005 gave every failure an `ApiError` with a code and a translated text (`messageFor`),
but only login and register show it. Everything else is swallowed: listing chats,
opening one, renaming, deleting, downloading or uploading an attachment, and a stream
that fails mid-reply all end in `console.error`. The user sees nothing happen, or a
reply that just stops, and can't tell whether to retry.

The frontend still fetches the v1 way: `useEffect` + `useState` in `App.tsx`
(`listConversations().then(setConversations)`), hand-kept copies of the list after
every rename/delete/create, and components importing `api/` directly. BLUEPRINT F2
wants `api/` → `hooks/` (TanStack Query) → `components/`, with components never calling
`api`. And `App.tsx` (403 lines) and `ChatThread.tsx` (427 lines) mix layout, data
loading and behaviour, so they're hard to change safely.

This is part 2 of 2 of Chatbot's Frontend v2 migration (part 1 = 005).

## What changes
For users, screens and flows stay the same, except that **failures now show on screen
in the user's language (EN/IT/DE)**, near where they happened:
- **Stream fails mid-reply** (an `error` event or a broken connection): the thread
  reloads from the server as today, keeping whatever reply part was saved, and an error
  line appears under it. Regenerate still works. The line goes away on the next send.
  Stopping a reply on purpose shows no error.
- **Upload fails** (e.g. file too large): the error shows by the message input; the
  failed file is not left staged as if it were attached.
- **List, open, rename, delete, download fail**: the error shows in one dismissible
  banner at the top of the chat area. A failed rename or delete leaves the sidebar as
  the server has it (no chat disappears or is renamed that wasn't).
- Loading the language preference at startup (`getMe`) and the thread refresh right
  after a stream stay silent (console only): the first falls back to the local
  language, and the second only matters when the stream itself failed.

Behind the scenes:
- **TanStack Query (F2).** Server data (conversation list, the open conversation,
  profile) is read through query hooks in `src/hooks/`, and changes (create, rename,
  delete, settings, upload) go through mutation hooks that update or invalidate those
  queries. No `useEffect` fetches server data, and components never import `api/`.
  Streaming keeps its own hook, built on the same layer.
- **Smaller components.** `App.tsx`, `ChatThread.tsx` and `MessageInput.tsx` are split by
  responsibility; no hand-written file in `frontend/src` is over 250 lines.
- **005 leftovers (from the backlog).** The comments in `.github/workflows/ci.yml` and
  `e2e/helpers.ts` that still name the removed `apiFetch` are updated, and the unused
  `genericError` string is removed from `i18n/strings.ts`.
- `CLAUDE.md`'s frontend section describes the hooks layer.

## Out of scope
- Backend changes. In particular, a stopped LLM still cuts the stream off with no
  `error` event (backlog: *A stopped LLM cuts the stream off…*, the natural next spec);
  this change shows whatever error the frontend does get.
- New features, visual redesign, or new strings beyond what showing errors needs.
- Changing shared `client.ts` / `messages.ts`.
- Retry buttons or automatic retries for failed actions (TanStack's default query
  retries may stay; no new retry UI).
- Showing the `getMe` and post-stream refresh failures.
- The v1 docs cleanup (MkDocs, trimming `CLAUDE.md`) — its own backlog item.

## Acceptance checks
- [ ] `@tanstack/react-query` is a frontend dependency, and `QueryClientProvider` wraps
      the app in `main.tsx`.
- [ ] No component imports `api/` (except types):
      `grep -rnE "from \"\.\./api/(conversations|auth|session|stream|client)\"" frontend/src/components frontend/src/App.tsx`
      finds nothing.
- [ ] No `useEffect` fetches server data:
      `grep -rn -A3 "useEffect" frontend/src --include=*.tsx --include=*.ts` shows no
      call into `api/` inside an effect.
- [ ] `grep -rn "console.error" frontend/src` finds only the `getMe` and post-stream
      refresh calls.
- [ ] `find frontend/src -name '*.ts*' ! -name schema.d.ts ! -path '*/i18n/strings.ts' | xargs wc -l`
      shows no file over 250 lines.
- [ ] vitest (with a fake API, no network): a failed list load, a failed rename and a
      failed delete each show the `messageFor` text in the banner, and after a failed
      delete the chat is still in the sidebar.
- [ ] vitest: a stream that ends with an `error` event shows that code's text under the
      thread; a stopped stream (abort) shows nothing; the next send clears the line.
- [ ] vitest: a failed upload shows its text by the input and leaves no staged chip.
- [ ] e2e: uploading a file over the size limit shows the "too large" text in the UI
      (in English, and in Italian in the i18n spec).
- [ ] Existing e2e specs pass unchanged in behaviour (`make e2e`), selectors adjusted
      only where the split moved elements.
- [ ] `grep -rn "apiFetch\|genericError" .github e2e frontend/src` finds nothing.
- [ ] `cd frontend && npm run lint && npm run build`, `make unit-frontend` and
      `make drift` pass.
- [ ] In the app, with the UI in Italian: stop the backend (`docker compose stop api`),
      click another chat → an Italian error appears in the banner and can be dismissed;
      start it again and the same click works.

## Open questions
<!-- none -->

---
Approved by: Jacopo Grotti · Date: 2026-11-20
