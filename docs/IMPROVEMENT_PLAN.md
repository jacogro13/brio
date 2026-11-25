# Chatbot → Claude.ai-like chat experience

> Implementation plan approved 2026-07-12. Phases are independently shippable and meant
> to be implemented in order, one or more per session. Check off phases as they land.
>
> - [x] Phase 1 — Typed SSE protocol + core interactions
> - [x] Phase 2 — Rendering polish
> - [x] Phase 3 — Thinking display
> - [x] Phase 4 — Per-conversation params
> - [x] Phase 5 — File uploads (Garage + attachments)
> - [x] Phase 6 — Web access (tool loop)
>
> Round 2 approved 2026-07-13:
>
> - [x] Phase 7 — Multiuser (JWT bearer + bcrypt)
> - [x] Phase 8 — Draft-chat homepage (lazy creation)
> - [x] Phase 9 — Paper × Claude theme

## Context

The Chatbot app (`Apps/Chatbot`, hexagonal rich-form §3b, FastAPI + async SQLAlchemy backend, React 19 frontend) already has SSE token streaming, markdown+GFM rendering, and a conversation sidebar with create/select/delete + auto-titles. Goal: close the gap to Claude.ai's chat UI. Approved scope (user choices): **core interactions** (stop, retry, edit, rename), **rendering polish** (highlighting, copy), **thinking display**, **per-conversation model params**, **web access** (tool loop + DDGS), **file uploads** (text/PDF/images stored in the shared Garage, referenced from Postgres). UI text stays **English**.

Six independently shippable phases. The SSE wire protocol changes once (Phase 1) and the `ChatLLM` port changes once (Phase 3) because thinking/tools/uploads all extend them. Migrations: `0002` thinking, `0003` conversation settings, `0004` attachments, `0005` tool_events.

Key existing files: `backend/src/chatbot/services/conversation/send_message.py` (two-UoW streaming), `domain/conversation/ports/chat_llm.py`, `adapters/llm/openai/openai_llm_adapter.py`, `entrypoints/routers/conversations.py`, `frontend/src/App.tsx`, `frontend/src/api/conversations.ts`, components `ChatThread/MessageInput/ConversationList`.

---

## Phase 1 — Typed SSE protocol + core interactions

**Protocol.** Replace `{"token"}/{"done"}/{"error"}` with a typed union: `{"type":"token","content"}`, `{"type":"done","message_id"}`, `{"type":"error","message"}` (later: `thinking`, `tool_start`, `tool_end`). No version field — frontend, CLI, backend ship together. Move SSE framing out of the use case into a new `entrypoints/routers/sse.py::sse_stream()` helper; use cases yield plain event dicts (refactor pre-authorized by Chatbot/CLAUDE.md). Update `cli/rendering.py` (`stream_sse_tokens` → `stream_events`, consume dicts) in the same commit.

**Backend.**
- Repo port + impl: add `delete_messages(conversation_id, message_ids)` — delete by explicit id list computed from the ordered `conv.messages` (never `created_at >=` — timestamp ties).
- New use cases (one file each in `services/conversation/`): `rename_conversation.py` (uses existing repo `update_title`), `regenerate_message.py` (UoW#1 deletes trailing assistant message(s), rebuild history; then stream+persist), `edit_message.py` (UoW#1 deletes target user message + everything after, saves new user message; then stream+persist). Share the stream/persist tail in `services/conversation/_streaming.py`.
- Routes: `PATCH /conversations/{id}` `{title}`; `POST /conversations/{id}/messages/regenerate` → SSE; `POST /conversations/{id}/messages/{message_id}/edit` `{content}` → SSE.

**Frontend.**
- `api/conversations.ts`: typed `StreamEvent` union; `renameConversation/regenerate/editMessage`; all stream generators take an `AbortSignal`.
- New `src/hooks/useChatStream.ts`: streaming state machine extracted from `App.tsx` (isStreaming, buffer, AbortController, post-stream refetch). **Stop = client-side abort** — the backend `finally`-UoW already persists partials; after abort, refetch the conversation. **Post-stream refetch replaces the fake-UUID assistant message** (real ids needed for edit/regenerate).
- `MessageInput`: Send ⇄ Stop toggle. `ChatThread`: hover actions — Edit on user messages (inline textarea), Retry on last assistant message. `ConversationList`: ✎ rename inline input.

**Gotcha.** If partial-persist proves flaky on disconnect, wrap the `finally` persist in `asyncio.shield`.

## Phase 2 — Rendering polish

- Deps: `rehype-highlight` + `highlight.js` (plugs into existing react-markdown; streams incrementally). Dark theme CSS imported in `main.tsx`, background overridden in `index.css`.
- `ChatThread`: custom `pre` renderer — header bar with language label + per-block Copy button ("Copied ✓" flash); Copy-message action in hover row (raw markdown).
- `src/utils/clipboard.ts` with `execCommand` fallback (app runs on plain HTTP LAN — `navigator.clipboard` unavailable).
- Pre-first-token indicator: pulsing dots; keep blinking caret while streaming.

## Phase 3 — Thinking display

- `ChatLLM` port changes once: `stream_chat(...) -> AsyncIterator[LlmChunk]`; frozen dataclass `LlmChunk(kind: "token"|"thinking"|"tool_call", content, tool_call=None)` in `ports/chat_llm.py` (`tool_call` reserved for Phase 6). Update all call sites (services, CLI) in one commit.
- OpenAI adapter: read `delta.reasoning_content` → `thinking` chunks. Mock adapter: emit deterministic thinking first (powers unit/e2e tests; Gemma 4 26B-A4B is itself a reasoning model that emits `reasoning_content` when thinking is on, so this path is exercised in prod too — Gemma 3 did not).
- Caveat to verify at implementation time: some models emit reasoning as inline `<think>…</think>` tags in `content` instead of `reasoning_content` (depends on llama.cpp's `--reasoning-format` flag). If the host llama.cpp doesn't separate them, add an inline-tag splitter fallback in the adapter.
- Persist in nullable `messages.thinking` column (migration `0002`); **never sent back to the LLM as history**. Expose on `MessageResponse`.
- Frontend: `ThinkingBlock.tsx` — collapsible, auto-expanded while streaming, collapses when first answer token arrives; `useChatStream` tracks `streamingThinking`.

## Phase 4 — Per-conversation params

- Migration `0003`: nullable `temperature FLOAT`, `max_tokens INT`, `system_prompt_override TEXT`, `enable_thinking BOOLEAN` on `conversations`; NULL = server default.
- Fold rename into one `update_conversation.py` use case; `PATCH /conversations/{id}` partial update (`exclude_unset`).
- Frozen `ChatParams(temperature, max_tokens, enable_thinking)` next to the port; adapter sends only non-None keys. **`enable_thinking` moves from adapter-construction time to a per-call `ChatParams` field** — today it's baked into the `_llm` singleton (`LLM_CHAT_ENABLE_THINKING`); Phase 4 already makes `stream_chat` take per-call params, so thread it through there. Streaming use cases resolve each param `conv.<x> if conv.<x> is not None else settings.<default>` (system prompt: `conv.system_prompt_override` else `settings.system_prompt`; thinking: `conv.enable_thinking` else `settings.llm_chat_enable_thinking`).
- Per-conversation, not per-message (rides the settings popover; flip once, sticky for the chat). Rationale: thinking adds latency + burns the `max_tokens` budget on reasoning models (Gemma 4 26B-A4B), so an off-switch for quick Q&A is worthwhile.
- Frontend: `ConversationSettings.tsx` gear popover (temperature slider, max-tokens input, system-prompt textarea, **thinking on/off toggle**, Reset-to-defaults → null). Distinguish `null` vs `0`/`false` — never `||`.

## Phase 5 — File uploads (Garage + attachments)

- **Two-step upload**: `POST /conversations/{id}/attachments` (multipart) uploads to Garage + extracts text immediately, returns metadata; `SendMessageRequest.attachment_ids` links at send time. `attachments.message_id` nullable (pending), `conversation_id` NOT NULL.
- Migration `0004`: `attachments(id, conversation_id FK cascade, message_id FK cascade NULL, filename, content_type, size, s3_key, extracted_text NULL, created_at)` + indexes.
- New port `domain/conversation/ports/attachment_storage.py` (`upload_file/get_file/delete_prefix`); adapter `adapters/storage/garage/garage_storage_adapter.py` — **copy Blibiobot's shape verbatim** (boto3 + `functools.partial` + `anyio.to_thread.run_sync`, cf. `Blibiobot/.../adapters/storage/garage/garage_storage_adapter.py`). Keys: `conversations/{cid}/{attachment_id}/{filename}`. Null/mock storage when `GARAGE_ENDPOINT` unset (mirrors LLM mock fallback).
- Extraction at upload (`adapters/extraction/text_extraction.py`): text/code/md as UTF-8, PDF via `pypdf`, images → `extracted_text=NULL` (stored only; UI badge "not visible to the model yet"). Caps: `ATTACHMENT_MAX_BYTES` 10 MB, `ATTACHMENT_MAX_EXTRACTED_CHARS` 40k.
- History builder injects `[Attached file: {name}]\n{extracted_text}` per user message (pure function in `_streaming.py`).
- **Downloads stream through the backend** (`GET /conversations/{cid}/attachments/{id}`) — no presigned URLs (browser can't reach Garage in prod). `delete_conversation` best-effort `delete_prefix` after DB delete.
- Infra: dev compose gains `garage` + `garage-init` services (copy Pasti's template: `garage/garage.toml`, `scripts/garage_init.sh`; host port **3907**, no `container_name`); e2e override `!reset`s the port; `deployment/docker-compose.yml` sets `GARAGE_ENDPOINT=http://garage:3900` (**alias, never `shared_garage`** — underscore breaks boto3); add `chatbot` to `GARAGE_BUCKETS` in `Infrastructure/deployment/.env(.example)`; raise nginx `client_max_body_size` to ~25m.
- Deps: `boto3`, `anyio`, `pypdf`; dev `moto` (integration test copies Blibiobot's).
- Frontend: 📎 button + pending chips in `MessageInput`; attachment chips on user messages in `ChatThread` (click = download).

## Phase 6 — Web access (tool loop)

- **Prompted-JSON protocol, not native `tools`** — Gemma 4 26B-A4B *does* have native function calling (unlike Gemma 3), but llama.cpp's OpenAI `tools` bridge doesn't have a native format handler for Gemma 4 (falls back to the generic Jinja handler, needs `--jinja`, and had parser/tokenizer/streaming bugs fixed only very recently), so native tool calls stay unreliable on our llama.cpp host. Prompted-JSON is model-agnostic and robust here. When web access is on, a system-prompt block instructs the model to emit a fenced ```` ```tool_call {"name","arguments"} ```` block. Protocol isolated in `services/conversation/tool_loop.py` (application policy, not adapter) so a native-`tools` impl can swap in later once llama.cpp's Gemma 4 tool support matures.
- **Thinking interaction (new with Gemma 4).** Gemma 4 is a reasoning model with thinking on by default; llama.cpp routes output into `reasoning_content` (→ our `thinking` chunks) unless thinking is off. To keep the fenced ```` ```tool_call ```` block landing in `content` where the buffering parser sees it, the tool loop should run with thinking disabled — resolve `enable_thinking=False` (Phase 4 per-conversation field / `--chat-template-kwargs '{"enable_thinking":false}'`) whenever `web_access` is on. Verify at implementation time whether the tool_call block otherwise leaks into `thinking`.
- Ports `domain/conversation/ports/web_tools.py`: `WebSearch.search(query, max_results) -> list[SearchResult]`, `PageFetcher.fetch(url) -> str`. Adapters: `ddgs` search + `trafilatura` page extraction (house convention — Pasti/Blibiobot use it), both sync-wrapped in `anyio.to_thread`; mock adapters for tests. Caps: `WEB_TOOL_MAX_ITERATIONS` 4, `WEB_FETCH_MAX_CHARS` 20k.
- Loop: buffer stream; on detected tool_call block suppress its tokens, emit `{"type":"tool_start",...}`, execute, append result as a `user` turn (`[tool_result web_search]…` — gemma has no tool role), emit `tool_end`, re-invoke. Protocol prompt includes a one-shot example. **Buffering heuristic (hold back possible tool_call openings, flush if false alarm) is the hairiest code — unit-test it thoroughly.**
- Persist `messages.tool_events JSONB` (migration `0005`) so chips re-render on reload; excluded from LLM history. `SendMessageRequest.web_access: bool` (per-message toggle, sticky via localStorage).
- Guardrails: `fetch_page` rejects non-http(s) and private-network hosts (SSRF — backend sits next to Postgres/Garage); ddgs errors become error tool_results, never stream failures. Mock LLM emits a tool_call when message contains `[use web]` (test hook).
- Frontend: 🌐 toggle in composer; `ToolActivity.tsx` chips ("Searching: …", "Reading domain…", collapsed summaries from `tool_events`).
- Deps: `ddgs`, `trafilatura`.

---

# Round 2 — Multiuser, draft-chat homepage, paper theme

> Approved 2026-07-13. Three independently shippable phases, in order 7 → 8 → 9.
> Per user preference: implementation first, tests/e2e/docs as a final pass per phase.
> UI text stays **English**.

## Round 2 context & decisions

1. **Phase 7 — Multiuser**: JWT bearer + bcrypt auth, copying Diario's pattern (`Apps/Diario`, the only app with auth — see `Diario/backend/services/services.py`, `Diario/backend/entrypoints/main.py:46-63`, `Diario/frontend/src/api/diaryService.ts`, `Diario/docs/adr/004-jwt-bearer-auth.md`). **Open self-registration** (login/register tabs). Existing conversations are **adopted by the first registered user**. Cross-user access = 404.
2. **Phase 8 — Homepage starts in a new chat**: today `App.tsx` shows an empty-state hint and "+ New chat" *eagerly* POSTs a DB row. Switch to a lazy **draft chat**: full composer UI on load, row created on first send (avoids orphan rows on every page load).
3. **Phase 9 — Theme restyle**: mix of Blibiobot reader's paper look and Claude web UI: bg `#FAF7F2`, surfaces `#FFFFFF`/hover `#F3EDE5`, border `#E8E0D5`, text `#2D2013`, muted `#9E8E7E`, accent `#D97757` (terracotta), Lora serif headings + sans body. Colors are currently hardcoded inline in 7 components → introduce CSS custom properties.

## Round 2 gotchas (verified in code, 2026-07-13)

- `adapters/persistence/postgres/models.py` is **declarative** (`Mapped`/`mapped_column`) despite the Apps-wide imperative rule — the new `UserModel` follows the app's declarative style.
- **Makefile `env` sed trap** (Makefile:8): the `changeme` sed replaces *every* occurrence with the same value → `JWT_SECRET_KEY` must get its **own** sed line (mirror the GARAGE lines, Makefile:9–10): `@sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$$(openssl rand -hex 32)|" .env`. `.env.example` gets `JWT_SECRET_KEY=` (empty, **not** `changeme`). Existing dev `.env` won't regenerate — document the append one-liner (`echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" >> .env`) in README.
- **CI writes `.env` via heredoc** (`.github/workflows/ci.yml` ~line 32) → add `JWT_SECRET_KEY=e2e-test-secret` there or the CI e2e stack won't boot.
- **Login rate limit vs e2e**: make the slowapi limit an env setting (`LOGIN_RATE_LIMIT`, default `5/minute`), override to `100/minute` in `docker-compose.e2e.yml`; the e2e helper also logs in via API + localStorage injection (belt and braces).
- **SSE + Bearer works**: `streamSSE` uses `fetch`, not `EventSource`, so an `Authorization` header rides the streaming routes fine.
- **Draft-promotion remount trap**: `App.tsx` uses `key={activeConversation.id}` on `MessageInput` (~line 253) — promoting a draft to a real conversation would remount it and wipe the textarea/pending chips. Use a separate stable `threadKey` state, regenerated only on select/new/delete — **not** on promotion.
- **`MessageInput` uploads on file pick** → the draft must be materialized on first upload too (`ensureConversation`).
- Only repo `get`/`list`/`delete` (+ new `claim_orphans`) need `user_id`; `update_title`/`update_settings`/`link_attachments` always run after a scoped `get` in the same UoW, so their signatures stay unchanged.
- `index.css` already has `.bubble .hljs { background: transparent }` → swapping `github-dark.css` → `github.css` in `main.tsx` is safe; only the `.codeblock` chrome (`rgba(0,0,0,…)` overlays) needs light-theme values.
- Blibiobot reader loads **Lora via Google Fonts `<link>` in index.html** with Georgia fallback (`Blibiobot/frontend-reader/index.html:7-10`) — copy that (degrades gracefully offline on LAN).
- Attachment chips are `<a href>` to the download URL — can't carry a Bearer header → switch to fetch→blob→objectURL download (Diario images pattern).

## Phase 7 — Multiuser (JWT + bcrypt, Diario pattern)

**Deps** (`backend/pyproject.toml`): `bcrypt>=4.0`, `pyjwt>=2.8`, `slowapi>=0.1.9`.

**Domain.** New `domain/user/`: `model.py` (dataclass `User(id, username, hashed_password, created_at)`), `ports/user_repository.py` (`AbstractUserRepository`: `get_by_username`, `add`, `count`, `list`), `ports/user_unit_of_work.py` (`AbstractUserUnitOfWork` exposing `users` **and** `conversations` repos so first-user adoption is atomic; `UserUnitOfWorkFactory`).

- **UoW decision: one shared concrete UoW, two ports.** `SqlAlchemyConversationUnitOfWork` (adapters/persistence/postgres/unit_of_work.py) implements both ABCs and sets `self.users = PostgresUserRepository(self._session)` in `__aenter__`. No second session/UoW.

**Conversation ownership.** `Conversation.user_id: UUID | None` in `domain/conversation/model.py`; port changes: `get(id, user_id)`, `list(user_id)`, `delete(id, user_id)`, new `claim_orphans(user_id) -> int` (`UPDATE … SET user_id WHERE user_id IS NULL`).

**Persistence.** Declarative `UserModel` (`users`: id UUID PK, username unique, hashed_password, created_at tz); `ConversationModel.user_id` nullable FK `users.id ondelete=CASCADE` + index; new `user_repository_impl.py`; scope predicates in `conversation_repository_impl.py` (`get`/`list`/`delete`). **Migration `0006_add_users_and_conversation_owner.py`** (style of 0001–0005): create `users`, add nullable `conversations.user_id` FK + index.

**Services.** New `services/user/`: `_auth.py` (bcrypt `hash_password`/`verify_password`, pyjwt `create_access_token` `{sub, username, exp}` HS256; `UsernameAlreadyExistsError`, `InvalidCredentialsError` — adapted from `Diario/backend/services/services.py`), `register_user.py` (duplicate → error; if `users.count()==0` → `claim_orphans(new_user.id)` in the same UoW), `login_user.py` (verify → token).

**Thread `user_id` through every conversation use case** (`services/conversation/*`): `create` (sets owner), `list`, `get`, `delete`, `update`, `upload_attachment`, `send_message`/`regenerate_message`/`edit_message` (first-UoW `get` only — `_streaming.py` untouched), `download_attachment` (ownership check via scoped `get` → `None` → 404). Cross-user access = 404 for free via scoped `get` returning `None`.

**Entrypoints.** `Settings` gains `jwt_secret_key` (required), `jwt_algorithm="HS256"`, `jwt_access_token_expire_minutes=43200` (30 days, LAN app), `login_rate_limit="5/minute"`. `get_current_user` dependency (HTTPBearer + pyjwt decode → UUID, 401 on invalid/expired — copy `Diario/backend/entrypoints/main.py:46-63`). New `routers/auth.py`: `POST /auth/register` (201/409), `POST /auth/login` (`TokenResponse {access_token, token_type}`, 401, slowapi-limited). Wire limiter + router in `main.py`. Every route in `routers/conversations.py` adds `Depends(get_current_user)`. Schemas: `RegisterRequest`, `UserResponse`, `TokenResponse`.

**CLI** (`entrypoints/cli/`): no JWT — `CHATBOT_CLI_USER` env var resolved at startup in `cli/dependencies.py`/`main.py`: named user → use it; unset + exactly one user → use it; unset + several → exit listing usernames; zero users → exit with "register via the web UI first". `user_id` rides `CliContext` into `app.py`/`commands.py` calls.

**Frontend.**
- New `src/api/http.ts`: `TOKEN_KEY="chatbot_token"`, get/set/clear, `apiFetch()` injecting `Authorization: Bearer` + central 401/403 → clear token + reload (Diario `diaryService.ts` pattern). New `src/api/auth.ts` (`register`, `login`). New `src/components/AuthPage.tsx` (login/register tabs, English).
- `src/api/conversations.ts`: route all ~9 raw `fetch` calls (incl. `streamSSE`) through `apiFetch`; replace `attachmentDownloadUrl` with `downloadAttachment(...) -> Blob`.
- `ChatThread.tsx`: attachment chip → fetch blob → `URL.createObjectURL` → programmatic download → revoke.
- `App.tsx`: gate on token (no token → `<AuthPage/>`); top bar username + Logout.

**Config/deploy.** `.env.example` + Makefile `env` (dedicated sed, see gotchas); `deployment/.env.example` += `JWT_SECRET_KEY`; CI heredoc += `JWT_SECRET_KEY`; `docker-compose.e2e.yml` += `LOGIN_RATE_LIMIT=100/minute`.

**Phase 7 final pass (tests/e2e/docs).**
- `tests/unit/fakes.py`: scoped fake repo + `FakeUserRepository`; thread a `user_id` fixture through existing unit tests; new `test_user_use_cases.py` (hash, duplicate, **first-user adoption**, login token round-trip, bad creds).
- Integration: user scoping (cross-user `get` → None), `claim_orphans`, new `test_user_repository.py`.
- e2e: new `e2e/helpers.ts` (register via `page.request` + localStorage token injection before `goto('/')`), prepend to all 5 specs; new `auth.spec.ts` (register/login/logout, wrong password, user isolation: user B doesn't see user A's conversations).
- Docs: `docs/adr/006-multiuser-jwt-auth.md`, architecture, api-reference, CLAUDE.md, README env table.

**Verify 7**: `make unit-backend && make integration`; `make backend` + curl register/login/401-without-token; register first user against a DB with legacy conversations → adopted; `CHATBOT_CLI_USER=x make cli`; `make e2e`.

## Phase 8 — Draft-chat homepage (lazy creation)

Frontend-only; backend unchanged (`POST /conversations/` still used, just later).

- `App.tsx`: `ActiveChat = Conversation | draft {id:null, messages:[]}`; start on a **draft** on mount; `handleNew` resets to draft (no POST); delete-of-active → draft; separate `threadKey` state as `MessageInput` key (regenerated on select/new/delete only — **not** on promotion). Empty-thread draft shows a centered Claude-style greeting ("What can I help you with?") above the composer. `ConversationSettings` gear hidden while draft (`id === null`).
- New `ensureConversation(): Promise<string>` in App: returns existing id, else `createConversation()` → prepend sidebar summary → promote draft in place → return new id (use the returned value, never read React state after set).
- `useChatStream.ts`: `send()` awaits `ensureConversation()` when `activeRef.current.id === null` before the optimistic append/stream; guard `regenerate`/`edit` on null id.
- `MessageInput.tsx`: props `conversationId: string | null` + `ensureConversation`; `handleFiles` materializes the draft before the first upload.

**Phase 8 final pass.**
- `e2e/conversations.spec.ts:29-30`: delete-last-conversation now lands on the draft (assert composer/greeting, not "select or start a conversation"); assert "+ New chat"/page-load creates **no sidebar row until send**. Sweep other specs for pre-send row assumptions. Optional spec: reload → draft → send → exactly one conversation.
- Docs: CLAUDE.md frontend section, architecture (draft lifecycle).

**Verify 8**: load app → composer visible, `select count(*) from conversations` unchanged; "+ New chat" ×5 without sending → no rows; send → one row + auto title; attach file in draft → row created once; delete active → draft. `make e2e`.

## Phase 9 — Paper × Claude theme

- **Tokens** in `frontend/src/index.css` `:root`: `--bg:#FAF7F2; --surface:#FFFFFF; --surface-hover:#F3EDE5; --border:#E8E0D5; --text:#2D2013; --text-muted:#9E8E7E; --accent:#D97757; --accent-hover:#C4653F; --accent-soft:#F7E8E1; --danger:#B3452E; --font-serif:"Lora",Georgia,serif; --font-sans:"Inter",system-ui,sans-serif; --font-mono:ui-monospace,monospace`. Rework existing `index.css` rules (`.codeblock*` light chrome `#F6F1E9` + `var(--border)`; blockquote/links/table borders/dots → tokens); `.bubble h1..h6 { font-family: var(--font-serif) }`; `body { font-family: var(--font-sans); color: var(--text); background: var(--bg) }`.
- **Fonts** (`frontend/index.html`): Google Fonts `<link>` for Lora (400/500/600) + Inter — same approach as `Blibiobot/frontend-reader/index.html:7-10`; Georgia/system-ui fallbacks cover offline LAN.
- **Highlight** (`frontend/src/main.tsx`): `github-dark.css` → `github.css`.
- **Component sweep** — replace every inline hex with `var(--…)` in the 7 components (hex counts: App 7, ConversationList 11, ChatThread 11, MessageInput 21, ConversationSettings 13, ThinkingBlock 3, ToolActivity 4). Mapping: dark bgs → `--bg`/`--surface`/`--surface-hover`; borders → `--border`; text → `--text`/`--text-muted`; Send button + user bubble + links + focus → `--accent` (white text on terracotta); web-toggle active → `--accent-soft`/`--accent`; Stop → `--danger`. Serif on top-bar title, brand, draft greeting. Restyle `AuthPage` (paper card, serif heading, terracotta button) and the Phase-8 greeting in the same sweep.

**Phase 9 final pass.**
- e2e asserts text/roles, not colors → run `make e2e` to confirm; keep the `+ New chat` label, `.bubble*` classes, `title="Delete"` untouched. `npm run lint && npm run build`. Docs: CLAUDE.md frontend section (tokens, fonts, light hljs theme).

**Verify 9**: visual pass in `make frontend` (code-block contrast, white-on-terracotta legibility, auth page, greeting, mobile backdrop); `grep -rn "#[0-9a-fA-F]\{3,6\}" frontend/src --include='*.tsx'` → empty; offline font fallback renders Georgia.

## Phase 10 — Multilanguage (EN / IT / DE)

UI chrome i18n **and** assistant reply language. Preference is **per-user, persisted** (`users.language`); switcher offers **English (default/fallback), Italian, German**. Depends on Phase 7 (per-user storage, `get_current_user`) — done; adds the `/auth/me` pair that Phase 7 didn't ship.

### 10a — Persist the preference (backend data layer)

- **Migration `0007_add_user_language.py`**: `users.language` — `String`, `nullable=False`, `server_default='en'` (existing rows adopt `en`).
- **Domain** (`domain/user/model.py`): `language: str = "en"` on `User`.
- **ORM** (`adapters/persistence/postgres/models.py`): map the column on `UserModel`; carry it through the `User`↔model translations in `user_repository_impl.py`.
- **Repo port** (`domain/user/ports/user_repository.py`): add `get_by_id(id) -> User | None` and `set_language(id, language) -> None`; implement in `user_repository_impl.py`; add to the fake in `tests/unit/fakes.py`.

### 10b — Assistant replies in the user's language

- New `services/conversation/language.py`: code → directive appended to the resolved system prompt — `en` → (none), `it` → `"Rispondi sempre in italiano."`, `de` → `"Antworte immer auf Deutsch."`.
- Thread `language: str` into `_streaming.resolve_chat_config` (appends the directive **after** the resolved prompt, so a per-conversation `system_prompt_override` still wins on tone; skipped for `en`) and through its three callers: `SendMessageUseCase.stream`, `RegenerateMessageUseCase`, `EditMessageUseCase`.
- New `get_current_language` dependency (`entrypoints/dependencies.py`): decode JWT `sub` → `get_by_id` → `user.language`; inject into the three message-producing routes in `routers/conversations.py`. One extra indexed PK read per send.
- **CLI**: `CHATBOT_LANGUAGE` env (fallback `en`) in `cli/dependencies.py`, same directive.

### 10c — Profile endpoints

- `GET /auth/me` → `{ username, language }` (fresh source of truth on app load).
- `PATCH /auth/me` `{ language }` → validate against `{en,it,de}`, `set_language`, return updated profile.
- New `schemas.py` models; wire into `routers/auth.py`; register accepts an optional initial `language` (browser-detected, sent by the frontend; default `en`).

### 10d — Frontend i18n (tiny homegrown, no new dep)

- `src/i18n/strings.ts`: typed `Record<Lang, Record<Key, string>>`, `Lang = 'en'|'it'|'de'`. `src/i18n/index.tsx`: `LanguageProvider` context + `useT()` → `t(key)` (fallback to `en` for missing keys); initial value = user profile → localStorage cache → `navigator.language` → `en`; `setLanguage()` updates context + localStorage + fires `PATCH /auth/me`.
- **String sweep** — replace hardcoded English with `t(...)` across all 8 components (`App`, `AuthPage`, `ConversationSettings` (10 labels), `MessageInput`, `ConversationList`, `ChatThread`, `ThinkingBlock`, `ToolActivity`) + the draft greeting.
- **Switcher**: compact `EN · IT · DE` selector in the top bar (next to username/Logout) and on `AuthPage` (drives detection + register payload).
- `api/auth.ts`: `getMe()`, `patchLanguage()`; `App.tsx` fetches `/auth/me` on mount to seed the provider.

### 10e — Final pass (tests / e2e / docs)

- **Unit backend**: register-with-language + `set_language`; `resolve_chat_config` appends the right directive per lang, skips `en`, composes with `system_prompt_override`.
- **Integration**: `get_by_id` / `set_language` round-trip; `0007` upgrade on a populated db.
- **Unit frontend**: `t()` `en` fallback; provider seeding precedence.
- **e2e**: `i18n.spec.ts` — switch to IT changes top-bar/composer strings, reload persists (via `/auth/me`); make the other specs language-agnostic (assert `data-testid`/roles, audit `conversations.spec.ts` for English literals).
- **Docs**: new `docs/adr/007-multilanguage.md`; update `CLAUDE.md` (i18n module, `/auth/me`, language directive), `architecture.md`, api-reference, README env table (`CHATBOT_LANGUAGE`).

**Verify 10**: `make unit-backend && make integration && make unit-frontend`; `make backend` + curl `/auth/me`, PATCH language, send a message → IT/DE reply; `make frontend` (switcher, persists after reload); `make e2e`.

---

## Docs (with each phase)

Update `Chatbot/CLAUDE.md` (event union, routes, Garage section, web tools), `docs/architecture.md` + api-reference; new ADRs `003-typed-sse-event-protocol`, `004-attachments-in-garage`, `005-prompted-json-tool-protocol`. README env-var table.

## Tests & verification

Per user preference, test/e2e fixes are a final pass per phase, implementation first.

- Unit (fakes in `tests/unit/fakes.py`): send/regenerate/edit/rename event shapes + truncation + partial-persist (`aclose()` mid-stream); text_extraction; tool_loop parser/buffering. Integration: repo `delete_messages` + attachments; Garage adapter via moto.
- Per phase: `make unit-backend`, `make integration`, `make unit-frontend`, `cd frontend && npm run lint && npm run build`.
- Full pass: fresh `make clean && make env && make migration` (0001→0005) **and** in-place upgrade of the existing dev db; `make backend`+`make frontend` manual flows (stop mid-stream → partial persists after reload; edit truncates; retry replaces; rename; code copy; temperature 0 vs default; upload .md/.pdf/.png + download; 🌐 with real LLM; thinking with mock); `make cli` still streams; `docker compose --profile app up --build` (garage-init completes).
- E2E final pass: keep `conversations.spec.ts` green; add `interactions.spec.ts`, `attachments.spec.ts`, `thinking.spec.ts`, `web-tools.spec.ts` (mock adapters + `[use web]` hook). `make e2e`, then `make test`.
- Deploy prep: shared garage_init must re-run once with `chatbot` in `GARAGE_BUCKETS` before first prod deploy.
