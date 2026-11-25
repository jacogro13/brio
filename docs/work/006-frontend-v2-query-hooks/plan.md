# 006 — Plan

Spec: [spec.md](spec.md) (approved 2026-11-20)

## Approach
Frontend-only. No backend, API, migration or env change. The order:
1. Add TanStack Query and a way for tests to inject a fake client.
2. Split the big components with no behaviour change, so the data rewrite touches small files.
3. Add the query hooks, then move callers onto them in three steps. The last step deletes
   the hand-written wrappers `api/conversations.ts` and `api/auth.ts`.
4. Make the errors visible: the banner, then the stream and upload errors.
5. Docs, the 005 leftovers, and the full gate.

BLUEPRINT §4 and §4b (F2, F3: the ~250-line split rule) apply. Famiglia's
`hooks/useMembers.ts` and `main.tsx` are the worked example. ADR-003 (stream protocol)
and ADR-007 (per-language error text) are unchanged. No canonical file changes: `make drift`
must stay green. No new ADR; the one local deviation (below) goes in `CLAUDE.md`.

Decisions taken here, from the spec and the code:
- **Client injection (local deviation from Famiglia).** Famiglia's hooks import `api`
  directly. Chatbot's spec wants component tests with a fake API. openapi-fetch captures
  `fetch` when the client is created, so a test can't swap it afterwards. So
  `hooks/useApi.tsx` exports `ApiProvider` and `useApi()`. The context's **default value
  is the app-wide `api`**, so production needs no provider and the auth middleware in
  `main.tsx` stays as it is. Tests wrap in
  `<ApiProvider client={createApiClient({ baseUrl: "http://test/api", fetch: server.fetch })}>`.
  Every hook gets its client from `useApi()`.
- **QueryClient** (in `main.tsx`, as in Famiglia): queries `retry: 1`, mutations
  `retry: false`. Conversation detail queries use `staleTime: Infinity` and
  `refetchOnWindowFocus: false`. The streaming hook writes optimistic messages into that
  cache entry, and a background refetch must not overwrite them mid-stream. The hook
  refreshes the entry itself when a stream ends.
- **Types move to hooks.** The spec's grep also matches `import type … from "../api/conversations"`.
  So the backend type aliases (`Attachment`, `ConversationSummary`, `Message`,
  `Conversation`, `ConversationSettings`) and `toConversation` (the one `ToolEvent[]`
  cast) move to `hooks/useConversations.ts`, and components import types from there.
  `StreamEvent` stays in `api/stream.ts`, since only hooks use it.
- **A draft is just `activeId === null`.** Today `send` and upload both await
  `ensureConversation()` before they touch messages, so a draft never holds any.
  `DraftConversation`/`ActiveChat` go away. `hooks/useActiveConversation.ts` owns:
  - `activeId` and `threadKey` (bumped on select/new/delete, **not** on promotion, so the
    remount trap is unchanged);
  - `select(id)`: `qc.fetchQuery` with `staleTime: 0`, then set `activeId`. If the load
    fails, the current chat stays on screen (as today) and the error goes to the banner;
  - `startNew()`, and the effect of deleting the active chat;
  - `ensureConversation()`: create mutation, de-duplicated by the existing `creatingRef`
    promise. It seeds `conversationKey(id)` with `{...summary, messages: []}` so the
    thread renders at once, and invalidates the list.
- **Which errors show where.**
  - Banner: `select` (open), rename, delete, settings save, download, and a failed create
    on first send.
  - List load: shows in the banner only when there is no list data. A refetch that fails
    after an invalidate stays silent.
  - Silent (no UI, no `console.error`): `getMe` becomes a `useProfile` query, and a
    small effect syncs its `data.language` (an effect on data, not a fetch). The
    post-stream refresh becomes `qc.refetchQueries`, which doesn't throw. Zero
    `console.error` calls left satisfies the spec's grep.
  - Settings save is not in the spec's list. Today it is an unhandled rejection, and
    showing it costs one line, so it goes to the banner too.
  - Banner state is one `unknown` error in `App`, shown as `messageFor[lang](error)`. A
    newer error replaces it, and × dismisses it. A dismissed list-load error stays hidden
    until the query fails again (compare `errorUpdatedAt`).
  - No optimistic updates for rename/delete, so after a failure the sidebar shows what the
    server has.
- **Stream errors.** `useChatStream` keeps `{conversationId, error}` and sets it in its
  `catch` unless **its own `controller.signal.aborted` is true** (stop). It doesn't check
  the error's type. The canonical `client.ts` turns an abort before the response headers
  arrive into `ApiError(0, "network_error")` (backlog: *Factory / Blueprint*, Chatbot 005
  review). An abort while reading the body is a `DOMException` instead. Only the signal
  tells both cases apart from a real failure, with no change to `client.ts`. It clears it when the next
  send/regenerate/edit starts. `ChatThread` shows the line only when the error belongs to
  the open chat, so switching chats hides it.
  - `api/stream.ts::readEvents` (not canonical) wraps a failed `reader.read()` that is not
    an abort as `ApiError(0, "network_error", …)`. Then a dropped connection shows
    "can't reach the server" instead of the generic fallback.
- **Upload errors.** `MessageInput` keeps the last upload error and shows it by the
  input. It clears when files are picked again or a message is sent. A failed file is
  never added to `pending` (already true; now tested).
- **New strings.** Only a `dismiss` label (EN/IT/DE) for the banner's ×. All error texts
  already exist in `api/errors.ts`.
- **Test infra.** `src/test/fakeServer.ts`: a hand-written `FakeServer` with routes keyed
  `"GET /conversations/"` → status + JSON body or an SSE text body, plus two route kinds
  for the stop tests: one streams a token and then waits until the request's `signal`
  aborts, the other never answers until the signal aborts. It records requests. `src/test/render.tsx`: `renderApp(server)` sets a token,
  then renders `<App/>` inside `QueryClientProvider` (fresh client, `retry: false`),
  `ApiProvider` and `LanguageProvider`. No `vi.mock`, no network.

## Tasks
| # | Task | Files | Check | Status |
|---|------|-------|-------|--------|
| 1 | **TanStack Query + client injection + test infra.** Add `@tanstack/react-query` (^5, as Famiglia). `main.tsx`: `QueryClientProvider` with the defaults above (comment as Famiglia's). New `hooks/useApi.tsx` (`ApiProvider`, `useApi`, default = `api`). New `src/test/fakeServer.ts` and `src/test/render.tsx` (see *Approach*). `App` still calls the global `api` here, so `renderApp` can't be used yet. The first test is a probe: `hooks/useApi.test.tsx`, `test_use_api_returns_the_provided_client` (a probe component calls `useApi().GET("/auth/me")` → the `FakeServer` records the request), and `test_use_api_defaults_to_the_app_client`. | `frontend/package.json`, `package-lock.json`, `src/main.tsx`, `src/hooks/useApi.tsx`, `src/hooks/useApi.test.tsx`, `src/test/{fakeServer.ts,render.tsx}` | `cd frontend && npm run lint && npm run build`; `make unit-frontend` | done |
| 2 | **Split `App.tsx` (no behaviour change).** Move the top bar to `components/TopBar.tsx` (☰, title, settings gear slot, username, `LanguageSwitcher`, logout). Move the draft greeting to `components/Greeting.tsx`. Move the mobile backdrop + sidebar wrapper to `components/SidebarDrawer.tsx`. Move the resize effect and `mobile`/`sidebarOpen` state to `hooks/useMobileLayout.ts` (no server data, so it's allowed in hooks/). Same DOM, same text, same handlers passed down. | `src/App.tsx`, `src/components/{TopBar,Greeting,SidebarDrawer}.tsx`, `src/hooks/useMobileLayout.ts` | `npm run lint && npm run build`; `make unit-frontend`; `wc -l src/App.tsx` < 250 | done |
| 3 | **Split `ChatThread.tsx` and `MessageInput.tsx` (no behaviour change).** ChatThread: `MessageBubble.tsx`, `AttachmentChips.tsx`, `CodeBlock.tsx` (with `nodeToText`), `ActionButton.tsx`. MessageInput: `PendingChips.tsx` (pending chips + "uploading…") and `ComposerToggles.tsx` (📎 🌐 🧠 buttons + send/stop). Styles move with the code that uses them. The existing `ChatThread.test.tsx` (KaTeX/GFM) passes unchanged. | `src/components/{ChatThread,MessageBubble,AttachmentChips,CodeBlock,ActionButton,MessageInput,PendingChips,ComposerToggles}.tsx` | `npm run lint && npm run build`; `make unit-frontend`; every file listed < 250 lines | done |
| 4 | **Conversation query hooks.** New `hooks/useConversations.ts`: the type aliases + `toConversation` moved from `api/conversations.ts` (which re-exports them for now, so nothing breaks); `conversationsKey`, `conversationKey(id)`; `useConversationList()`, `useConversation(id \| null)` (`enabled: id !== null`, staleTime/refocus as above), `useCreateConversation`, `useRenameConversation` (on success: set the title in the detail cache, invalidate the list), `useDeleteConversation` (on success: remove the detail, invalidate the list), `useUpdateSettings` (on success: merge only the settings into the detail cache, keeping messages). New `hooks/useProfile.ts` (`useProfile` query on `/auth/me`). All use `useApi()`. Tests `hooks/useConversations.test.tsx` (`renderHook` + `FakeServer`): `test_rename_refreshes_the_list_with_the_server_title`; `test_failed_rename_leaves_the_list_unchanged`; `test_delete_removes_the_chat_from_the_list`; `test_failed_delete_keeps_the_chat`; `test_settings_update_keeps_the_messages`. | `src/hooks/{useConversations,useProfile}.ts`, `src/hooks/useConversations.test.tsx`, `src/api/conversations.ts` | `npm run lint && npm run build`; `make unit-frontend` incl. the new tests | done |
| 5 | **Sidebar data and profile on hooks.** `App`: the list comes from `useConversationList()` (no `useState` copy, no `listConversations` effect). Rename/delete use the mutation hooks. `ensureConversation` uses `useCreateConversation` and invalidates the list instead of prepending by hand. `syncSummary` becomes a list invalidate. `getMe` becomes `useProfile()` + an effect calling `syncLanguage(data.language)` when data arrives. The open chat still lives in `App` state in this task: rename/delete still patch it as today. | `src/App.tsx`, `src/App.test.tsx` | `npm run lint && npm run build`; `make unit-frontend` incl. a first `renderApp` test, `test_app_lists_conversations_from_the_server` (fake list with one title → it shows in the sidebar) | done |
| 6 | **Open chat and stream on the query cache.** New `hooks/useActiveConversation.ts` (see *Approach*: `activeId`, `threadKey`, `select` via `fetchQuery`, `startNew`, `ensureConversation`, delete handling). `useChatStream` takes `activeId` + `ensureConversation`. It writes optimistic user messages and truncations with `qc.setQueryData(conversationKey(id), …)`. It calls the three stream routes through `useApi()` (`parseAs: "stream"`, then `readEvents`). After every stream it does `qc.refetchQueries(conversationKey(id))` + invalidates the list. `DraftConversation`/`ActiveChat` and the `activeRef` mirrors it no longer needs are removed. `App` reads the open chat with `useConversation(activeId)`; settings use `useUpdateSettings`. Remove the stream and conversation functions from `api/conversations.ts` that nothing calls any more. Test (`hooks/useChatStream.test.tsx` or via `renderApp`): `test_send_shows_the_user_message_then_the_saved_reply` (fake SSE tokens + `done`, then the refetched conversation). | `src/hooks/{useActiveConversation,useChatStream}.ts`, `src/App.tsx`, `src/api/conversations.ts`, test file | `npm run lint && npm run build`; `make unit-frontend`; `grep -rn "useEffect" -A3 src` shows no `api` call in an effect | done |
| 7 | **Remaining callers; wrappers gone.** `hooks/useAuth.ts`: `useLogin` (on success `setToken`), `useRegister`. `AuthPage` uses them (its error display is unchanged). `useConversations.ts`: `useUploadAttachment(conversationId)` (mutation) and `useDownloadAttachment()`, which returns a function `(cid, id) => Promise<Blob>` on `useApi()`. `MessageInput` and `AttachmentChips` use them (their errors are still logged; shown in task 9 / task 8). `i18n/index.tsx` calls `api.PATCH("/auth/me", …)` itself for `patchLanguage`. Delete `api/conversations.ts` and `api/auth.ts`. Components and `App` import types from `hooks/`. | `src/hooks/{useAuth,useConversations}.ts`, `src/components/{AuthPage,MessageInput,AttachmentChips}.tsx`, `src/i18n/index.tsx`, `src/api/{conversations,auth}.ts` (deleted), tests' type imports | `npm run lint && npm run build`; `make unit-frontend`; the spec's grep `grep -rnE "from \"\.\./api/(conversations\|auth\|session\|stream\|client)\"" src/components src/App.tsx` finds nothing (`App.tsx` imports from `./api/…`: check `"\./api/(conversations\|auth\|stream\|client)"` too; `session` stays allowed there only for logout/`getUsername`, else move both into `useAuth`) | done |
| 8 | **Error banner.** New `components/ErrorBanner.tsx`: `role="alert"`, the `messageFor[lang](error)` text, a × button with `aria-label={t("dismiss")}`, at the top of the chat area. Add `dismiss` to `i18n/strings.ts` (EN/IT/DE). `App` keeps one banner error and feeds it from `select`, rename, delete, settings, download and a failed create on first send (`useChatStream` takes an `onError` for that), plus the list-load rule (*Approach*). Tests `components/ErrorBanner.test.tsx` via `renderApp` + `FakeServer`: `test_failed_action_shows_its_text_in_the_banner`, parametrized over list load (500 → `internal_error`), rename and delete (404 `conversation_not_found`), with the expected EN text; `test_failed_delete_keeps_the_chat_in_the_sidebar`; `test_dismiss_hides_the_banner`; `test_banner_text_follows_the_ui_language` (IT). | `src/components/ErrorBanner.tsx`, `src/components/ErrorBanner.test.tsx`, `src/App.tsx`, `src/hooks/useChatStream.ts`, `src/components/AttachmentChips.tsx`, `src/i18n/strings.ts` | `npm run lint && npm run build`; `make unit-frontend` incl. the new tests | done |
| 9 | **Stream and upload errors on screen + e2e.** `useChatStream`: `{conversationId, error}` as in *Approach*, exposed as `streamError`. `ChatThread` renders it under the last message (`role="alert"`, `messageFor[lang]`). `readEvents`: a failed `reader.read()` that is not an abort becomes `network_error`. `MessageInput`: `uploadError` shown by the input. Tests: in `api/stream.test.ts`, `test_broken_connection_becomes_network_error` and `test_abort_is_rethrown_as_is`. In a `renderApp` test file: `test_stream_error_event_shows_its_text_under_the_thread` (SSE `error` with `nothing_to_regenerate`); `test_stopped_stream_shows_no_error`, parametrized over stop after the first token (the waiting-stream route) and stop before any response (a route that never answers until its signal aborts, so `client.ts` reports `network_error`); `test_next_send_clears_the_stream_error`; `test_failed_upload_shows_its_text_and_stages_no_chip` (413 `attachment_too_large`). e2e: in `attachments.spec.ts`, `uploading a file over the limit shows an error` (an 11 MB buffer → "The file is too large."); in `i18n.spec.ts`, the same in Italian ("Il file è troppo grande."). | `src/hooks/useChatStream.ts`, `src/components/{ChatThread,MessageInput}.tsx`, `src/api/{stream,stream.test}.ts`, new test file under `src/components/`, `e2e/{attachments,i18n}.spec.ts` | `npm run lint && npm run build`; `make unit-frontend`; `grep -rn "console.error" frontend/src` finds nothing outside allowed spots | done |
| 10 | **Docs, 005 leftovers, full gate.** Update `.github/workflows/ci.yml` and `e2e/helpers.ts` comments ("the auth middleware" instead of `apiFetch`). Remove `genericError` from `i18n/strings.ts`. `CLAUDE.md` frontend section: the hooks layer (`useApi` + its default-client deviation, `useConversations`/`useActiveConversation`/`useChatStream`/`useProfile`/`useAuth`, query keys and why detail queries never refetch on their own), where errors show, `src/test/` fakes, file list updated. Remove the "not shown until 006" comments. Then run every spec check. | `.github/workflows/ci.yml`, `e2e/helpers.ts`, `src/i18n/strings.ts`, `CLAUDE.md` | `make test` (lint, typecheck, unit, integration, e2e) green; `make drift`; `grep -rn "apiFetch\|genericError" .github e2e frontend/src` empty; the spec's `find … \| xargs wc -l` shows nothing over 250; the spec's manual check (IT UI, `docker compose stop api`, click another chat → banner) is left for the user at review | done |

## Fixes from review
Found in the manual acceptance check after the review (2026-11-20, asked for by the user):
with the api stopped, opening another chat took ~7–10 s before the banner showed, because
`select()`'s `fetchQuery` inherits the app-wide `retry: 1` (TanStack only defaults
`fetchQuery` to no retry when no global default is set). *Approach* says opening a chat does
not retry.

| # | Task | Files | Check | Status |
|---|------|-------|-------|--------|
| 11 | **Opening a chat does not retry.** `useActiveConversation.select`: pass `retry: false` to `fetchQuery`. Test `hooks/useActiveConversation.test.tsx`, on a `QueryClient` with the app's defaults (`queries.retry: 1`): `test_failed_open_sends_one_request` (502 → `select` rejects, one `GET /conversations/c2`, `activeId` unchanged). | `src/hooks/useActiveConversation.ts`, `src/hooks/useActiveConversation.test.tsx` | `npm run lint && npm run build`; `make unit-frontend` incl. the new test, which fails without the fix | done |

## Risks
- **No database, API or environment change.** Only the frontend image changes. Nothing
  to add on the mini-PC, and no other app or `Infrastructure/` is touched.
- **Behaviour users will notice.** Errors now appear (that's the point). Reads retry once
  before an error shows, so a down server shows the banner after a short delay on list
  load. Opening a chat (`fetchQuery`) does not retry. Screens are otherwise meant to stay
  identical: tasks 2–3 are pure moves, and the e2e suite (run in task 10) is the guard.
- **Optimistic messages vs. refetches.** If the open conversation were refetched in the
  background mid-stream, the optimistic user message and the truncation from
  edit/regenerate would flicker or vanish. Guard: detail queries never refetch on their
  own (`staleTime: Infinity`, no refocus refetch). Only `select` and the end of a stream
  refresh them.
- **Draft promotion remount trap.** Moving state into `useActiveConversation` must keep
  `threadKey` unchanged on promotion, or staged text and attachments are wiped on first
  send or upload. The existing e2e (`attachments.spec.ts` attaches in a draft, then sends)
  covers it.
- **Size of tasks 6–7.** These are the biggest rewrites. If either goes well past ~150
  lines, `/build` should split it (e.g. stream vs. select/settings) rather than land one
  large diff.
- **`main` deploys within ~5 minutes.** The full gate (`make test` incl. e2e) runs before
  any push. A bad frontend can be rolled back by pinning the previous `sha-…` image tag.

---
Approved by: Jacopo Grotti · Date: 2026-11-20
