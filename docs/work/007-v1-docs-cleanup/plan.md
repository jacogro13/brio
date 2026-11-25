# 007 — Plan

Spec: [spec.md](spec.md) (approved 2026-11-20)

## Approach
Docs and docs-tooling only (BLUEPRINT §10, §11): no code, schema or API changes, so no
ADR, no `make types`, no `make drift`. Same order as Famiglia 003 + 007. First remove
the tooling and the dead pages. Then rewrite `docs/architecture.md` section by section
from the code as it is today (backend, then frontend). Then add the two Mermaid
diagrams. Only then shrink CLAUDE.md's *Architecture*, so every fact has landed in
architecture.md before it leaves CLAUDE.md. The diagrams are C4-style `flowchart`s
(plain nodes and subgraphs, not Mermaid's experimental `C4Container` syntax), copying
the look of `Famiglia/docs/architecture.md`. Sections that repeat ADR-002…007 shrink to
one sentence and a link. CLAUDE.md's "the streaming request errors cleanly when it's
down" is false today (backlog item *A stopped LLM cuts the stream off…*), so it is
**left out** of architecture.md rather than copied (the spec allows either).

## Tasks

| # | Task | Files | Check | Status |
|---|------|-------|-------|--------|
| 1 | **Remove the docs tooling.** Delete `mkdocs.yml`. Drop the `docs` group from `backend/pyproject.toml` and run `cd backend && uv lock` (removes the mkdocs packages from `uv.lock`). Delete the `kroki` service (and its `docs` profile) from `docker-compose.yml`. Delete the `docs:` target and its `.PHONY` entry from the `Makefile`. In CLAUDE.md, drop the `make docs` line under *Aggregates* and make the *Documentation* paragraph say only that docs are plain Markdown in `docs/` (it is rewritten in task 9). | `mkdocs.yml`, `backend/pyproject.toml`, `backend/uv.lock`, `docker-compose.yml`, `Makefile`, `CLAUDE.md` | `make docs` → "No rule to make target"; `docker compose config --services` and `docker compose --profile docs config --services` don't list `kroki`; `cd backend && uv sync --locked`; `make lint typecheck unit` | done |
| 2 | **Remove the dead pages, rename the ADR list.** Delete `docs/api-reference/` (4 mkdocstrings stubs), `docs/index.md` and the empty `docs/diagrams/`. Before deleting `docs/development.md`, move what README.md/CLAUDE.md don't already say into README.md: the prerequisites (Python 3.12 + uv, Node 20 + npm, Docker Compose v2) and *Adding a new LLM provider* (3 steps). `git mv docs/adr/index.md docs/adr/README.md` and fix ADR-002's title in its table only if the file's title differs (the list stays a table of 001–007). Fix every link to the removed or renamed files (`grep -rn 'index.md\|development.md\|api-reference' --exclude-dir={node_modules,.venv,.git,work}`). | `docs/api-reference/`, `docs/index.md`, `docs/development.md`, `docs/diagrams/`, `docs/adr/index.md` → `README.md`, `README.md` | `ls docs/` = `adr/ architecture.md work/` + the four `*_PLAN.md`; link check passes | done |
| 3 | **architecture.md: intro and *Backend layers*.** Replace the PlantUML page. Intro: what Chatbot is (multi-conversation chat over a local LLM, web UI + CLI), rich form (§3b). *Backend layers*: a `text` block of the four layers (`entrypoints/`, `services/`, `adapters/`, `domain/`), a link to ADR-001, then one bullet per layer from today's code: `domain/` (`conversation/` and `user/` packages, their `ports/`, `Validated` entities, the `DomainError` family next to the entities); `services/` (one module per use case in `conversation/` and `user/`, `_streaming.py`, `tool_loop.py`, `language.py`); `adapters/` (persistence: imperative `orm.py` + `start_mappers()` run from `lifespan` and the CLI, `lazy="raise"`, repositories, `SqlAlchemyConversationUnitOfWork` implementing both UoW ports; llm: openai + mock fallback; storage: Garage + null fallback; extraction; web: ddgs + trafilatura with the SSRF guard, mock; security: canonical bcrypt/jwt/fake); `entrypoints/` (routers, `sse.py`, `schemas.py`, `dependencies.py`, `error_handlers.py` → `{code, message, field}`, `settings.py` as the only env reader, logging with request id, `/health`, `create_app()`/`lifespan` per D4, the `cli/` adapter). Canonical copies named once with a pointer to `make drift`. | `docs/architecture.md` | no ` ```plantuml `; every name grep-found in `backend/src/chatbot` | done |
| 4 | **architecture.md: *Model* and *Streaming*.** *Model*: `Conversation` (title from the first message, nullable settings overrides, `None` = server default), `Message` (`thinking`, `attachments`, `tool_events`; never replayed as history), `Attachment` (pending until linked, `extracted_text`, key layout; one line + ADR-004), `User` (`language`; open self-registration; first user claims orphans; one line + ADR-006/007). Ownership is a scoped repository predicate (other user's chat → `ConversationNotFound` → 404). Generation params as per-call `ChatParams`, resolved by `resolve_chat_config` (+ `apply_language`). *Streaming*: the event union with today's `error` shape (`code`, `message`), `sse_stream()` framing, the two-UoW stream-then-persist tail with `aclosing`, client-side stop, web access = prompted-JSON tool loop with thinking forced off (one line + ADR-005), attachment text inlined only into LLM history. No "errors cleanly when it's down". | `docs/architecture.md` | `grep -n '"type":"error","message"' docs/architecture.md` empty; names grep-found | done |
| 5 | **architecture.md: *Frontend* layers.** `api/` → `hooks/` → `components/`: generated `schema.d.ts` (`make types`), canonical `client.ts`/`messages.ts` → `ApiError`, `errors.ts` `messageFor[lang]` (EN/IT/DE deviation, ADR-007), `session.ts` + auth middleware, `stream.ts::readEvents`; the hooks (`useApi` context and why it deviates from Famiglia, `useConversations`, `useActiveConversation`, `useChatStream`, `useProfile`, `useAuth`, `useMobileLayout`; detail queries never refetch on their own); the component tree after the 006 split; test fakes in `src/test/` in two lines. | `docs/architecture.md` | every name grep-found in `frontend/src` | done |
| 6 | **architecture.md: frontend topics.** Short sections moved from CLAUDE.md, corrected against the code: *Draft chat* (`activeId === null`, `ensureConversation`, `threadKey` remount trap), *Where errors show* (banner / under the thread / by the input / silent), *i18n* (catalog, `LanguageProvider`, initial language, `PATCH /auth/me`), *Look and rendering* (paper palette as CSS vars, fonts, responsive classes in `index.css` at 640px, markdown + highlight, `CodeBlock`, clipboard fallback, `ThinkingBlock`), and the nginx `/api/` proxy with `proxy_buffering off`. | `docs/architecture.md` | names grep-found in `frontend/src` / `frontend/nginx.conf`; link check passes | done |
| 7 | **Container diagram.** A `flowchart LR` under *Containers*, after the intro, in Famiglia's style: user (browser) → `chatbot_ui` (nginx + React, port 120) → `/api/*` → `chatbot_api` (FastAPI + Alembic) on the mini-PC → `shared_postgres` (role `chatbot_app`, `shared_network`), shared Garage (`garage` alias, bucket `chatbot`), host `llama.service` (llama.cpp at `10.100.0.1:8080`), and the internet (DuckDuckGo search, fetched pages); GitHub Actions → GHCR (`chatbot-api`, `chatbot-frontend`) ← `docker-autoupdate` pulls and restarts. Prose under it: migrations at every start; the `garage` alias gotcha; `chatbot` in Infrastructure's `GARAGE_BUCKETS`; locally (`--profile app`, `chatbot_e2e`) its own `db` and Garage, mock LLM when `LLM_BASE_URL` is empty, mock web tools when `WEB_TOOLS_ENABLED=false`; the CLI talks to the db and LLM in-process. Facts from `deployment/docker-compose.yml`, `Infrastructure/deployment/systemd/`. No CPU architecture. | `docs/architecture.md` | Mermaid parse passes; `grep -nE 'arm64\|amd64\|QEMU\|\bPi\b' docs/architecture.md` empty | done |
| 8 | **Component diagram.** A `flowchart TB` of the backend hexagon under *Backend layers*, like Famiglia's: `entrypoints/` (routers + `sse.py`, `cli/`, `dependencies.py`, `error_handlers.py`) → `services/` (conversation, user) → `domain/` (entities + errors, ports); `adapters/` (persistence + UoW + `orm.py`, llm, storage, extraction, web, security) implement the ports (dotted `implements`); Postgres, Garage, LLM, web outside. Arrows = import direction; a sentence under it says so. | `docs/architecture.md` | Mermaid parse passes; exactly two ` ```mermaid ` blocks, both `flowchart` | done |
| 9 | **Shrink CLAUDE.md.** *Documentation*: Famiglia's paragraph (plain Markdown: `architecture.md` with container and component diagrams, `adr/` listed in `adr/README.md`, `work/`). *Architecture*: two or three sentences + link to `docs/architecture.md` + *Gotchas while coding*: `MessageInput` keyed by `threadKey`, not bumped on draft promotion; detail queries never refetch on their own (optimistic stream writes); empty settings inputs → `null`, never `\|\|`; run `make types` after a backend schema change and commit `schema.d.ts`; hooks get the client from `useApi()`, tests wrap in `ApiProvider`, no `vi.mock`, `afterEach(cleanup)`; components never call `api`/`fetch` or read status codes, they show `messageFor[lang]`; add a UI string with at least its English entry; `navigator.clipboard` is missing over LAN HTTP → `utils/clipboard.ts`; CSS vars only, no inline hex; boto3 only via the anyio thread pool. Remove the *Backend*, *Frontend* and *Deployment* subsections (now in architecture.md); keep *Commands* (minus `make docs`), *E2E*, *Test strategy*, *CI/CD*, *Conventions to keep* byte-identical. Before deleting, check each removed fact is in architecture.md or the gotchas. | `CLAUDE.md` | `git diff CLAUDE.md` (since task 1) touches only *Documentation* and *Architecture* down to *E2E*, plus the removed *Deployment*; `grep -niE '\bpi\b\|mkdocs\|make docs' CLAUDE.md` empty; link check passes | done |
| 10 | **Spec checks and full gate.** Run every acceptance check: spec grep, `ls docs/`, Mermaid parse, link check (incl. `README.md` and `docs/adr/*.md`), names check (each backticked identifier in architecture.md grep-found in `backend/` or `frontend/`), `make docs`, compose `--services`, `uv sync --locked`. Then `make test` (incl. e2e — self-contained, checked 2026-11-19). Ask Jacopo to read both pages for the "stated in one place" check and to confirm the container diagram. | — | all spec checks pass; `make test` passes | done |

**Link check** (tasks 2, 6, 9, 10), from `Chatbot/`:
`for f in README.md CLAUDE.md docs/architecture.md docs/adr/*.md; do grep -oE '\]\([^)#:]+\)' "$f" | sed -E 's/^\]\((.*)\)$/\1/' | while read -r l; do [ -e "$(dirname "$f")/$l" ] || echo "BROKEN $f → $l"; done; done`
prints nothing.

**Mermaid parse** (tasks 7, 8, 10): extract each block to a scratch file and run
`npx -y @mermaid-js/mermaid-cli@11 -i <block>.mmd -o <block>.svg`; it must exit 0. If
the CLI can't start (it needs Puppeteer's Chromium), fall back to Jacopo opening the
GitHub preview and say so in the review.

**Notes on two spec checks.** The spec's `grep -ni 'pi\b' CLAUDE.md` also matches `api`,
so it is run as `grep -niE '\bpi\b'` (the intent: no Pi deployment text). The spec's grep
for `8004|8005` also scans `uv.lock`; a hit there inside a `sha256` hash is not a
leftover, and review says so if it happens.

## Risks
- **Production:** none. No migrations, no API, no frontend or image change, no env vars
  or secrets on the mini-PC. Removing the `docs` group changes `uv.lock`, but only dev
  tooling: the image installs without it (`uv sync --locked` + `make test` guard it).
  The push still triggers CI and a redeploy of equivalent images.
- **Facts lost from CLAUDE.md:** agents load CLAUDE.md automatically, but not
  architecture.md. A trap that moves out silently stops guiding them. Task 9 keeps
  coding-time gotchas in CLAUDE.md and checks each removed line before deleting it.
- **architecture.md grows long** (Chatbot is rich form, with more topics than
  Famiglia). Sections that repeat an ADR stay at one sentence + link to keep it readable.
- **Container diagram vs reality:** written from `deployment/docker-compose.yml` and
  `Infrastructure/`, not the running mini-PC (never SSH'd). Jacopo confirms it in
  task 10.
- **Backlog item *A stopped LLM…*** asks to fix CLAUDE.md's "errors cleanly when it's
  down". That line disappears here. The item's code change is unaffected, and its last
  sentence becomes moot (`/ship` can note it).

---
Approved by: Jacopo Grotti · Date: 2026-11-20
