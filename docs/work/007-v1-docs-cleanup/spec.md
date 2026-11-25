# 007 — Remove v1 docs leftovers and refresh the architecture page

App: Chatbot · Created: 2026-11-20
Status: shipped
<!-- draft → approved → building → in review → shipped | abandoned -->

## Why
Chatbot still carries the v1 docs stack: MkDocs, a generated API reference, a Kroki
diagram container and `make docs`. BLUEPRINT §10 replaces all of it with plain
Markdown read in the editor or on GitHub. The leftovers cost a dependency group, an
extra compose service and two ports, and they mislead: CLAUDE.md says "serve locally
with `make docs`", `mkdocs.yml`'s nav lacks ADR-006/007, and `docs/architecture.md`'s
only diagram is PlantUML that renders only through Kroki. The page is also out of
date: no users/auth, attachments or web tools, and the old `{"type":"error","message"}`
event. Meanwhile CLAUDE.md is 212 lines: the whole layer-by-layer architecture lives
there, against BLUEPRINT §11.

This change brings Chatbot's docs to the same end state as Famiglia's (Famiglia 003
*v1 docs cleanup* + 007 *architecture refresh*), in one change.

## What changes
- **Tooling removed**: `mkdocs.yml`; the `docs` dependency group in
  `backend/pyproject.toml` (and its packages in `backend/uv.lock`); the `kroki` service
  (and its `docs` profile) in `docker-compose.yml`; the `make docs` target (and its
  `.PHONY` entry).
- **Pages removed**: `docs/api-reference/` (4 pages), `docs/index.md`,
  `docs/development.md` (anything in them that README.md/CLAUDE.md don't already say
  moves there first), and the empty `docs/diagrams/`.
- **ADR list renamed**: `docs/adr/index.md` → `docs/adr/README.md` (§10), with any
  links to it fixed.
- **`docs/architecture.md` is the one overview of the app**, laid out like Famiglia's
  and matching the code today: intro (what the app is, rich form), *Containers*,
  *Backend layers*, the model (conversations/messages/attachments, users), the
  streaming flow (ADR-003, two-UoW pattern), *Frontend* (api → hooks → components),
  and the frontend's own topics (draft chat, where errors show, i18n, theme/rendering).
  It contains facts moved over from CLAUDE.md, corrected where the code differs. A
  section that repeats an ADR becomes one sentence and a link.
- **Two C4-style Mermaid `flowchart` diagrams** in that page, the same levels and
  style as Famiglia's:
  - *Container*: browser → `chatbot-frontend` (nginx + React) → `chatbot-api`
    (FastAPI + Alembic) → `shared_postgres` (as `chatbot_app`), shared Garage (via the
    `garage` alias), the host LLM service on the mini-PC, and the web (search + page
    fetch); CI → GHCR → how images reach the mini-PC. A short paragraph covers the
    local/e2e differences (own `db` and Garage, mock LLM). No CPU architecture
    details.
  - *Component*: the backend hexagon: entrypoints (routers, SSE framing, the CLI) →
    services (conversation, user) → domain (entities, ports, errors), and the adapters
    implementing the ports (persistence/UoW/imperative ORM, LLM, storage, extraction,
    web, security).
  - The PlantUML block is gone.
- **CLAUDE.md shaped like Famiglia's**: the *Documentation* paragraph points to
  `docs/architecture.md`, `docs/adr/` and `docs/work/` as plain Markdown. *Architecture*
  shrinks to two or three sentences, a link to `docs/architecture.md` and a
  *Gotchas while coding* list (app-specific traps an agent needs, e.g. the
  `MessageInput` remount trap, detail queries never refetch, `null` vs `0` settings,
  `make types` after schema changes, the `useApi` deviation, plain-HTTP clipboard).
  *Commands*, *E2E*, *Test strategy*, *CI/CD* and *Conventions to keep* stay. No
  mention of MkDocs, Kroki, `make docs`, the API reference, the deleted pages, or the
  Pi.

## Out of scope
- The four planning docs (`docs/APP_TOOLS_PLAN.md`, `CODE_ASSISTANT_PLAN.md`,
  `IMPROVEMENT_PLAN.md`, `MOBILE_UX_PLAN.md`) are not changed or moved.
- Context and Code level C4 diagrams; the fleet-wide picture at `Apps/` level.
- Rewriting ADRs (beyond fixing links), README.md beyond docs-tooling mentions, or any
  code. ADR-002's Pi-era title stays.
- CLAUDE.md's "errors cleanly when it's down" claim: it is fixed with the backlog item
  *A stopped LLM cuts the stream off with no `error` event*, and it is copied over to
  architecture.md as is or left out, not rewritten here.
- The other apps' docs stacks.

## Acceptance checks
- [ ] `grep -rniE 'mkdocs|kroki|make docs|api-reference|plantuml|8004|8005' --exclude-dir={node_modules,.venv,.git,work} --exclude='*_PLAN.md' .`
      in `Chatbot/` finds nothing (this covers `backend/uv.lock` too).
- [ ] `ls docs/` shows only `adr/`, `architecture.md`, `work/` and the four
      `*_PLAN.md` files; `docs/adr/README.md` exists, lists ADR 001–007, and
      `docs/adr/index.md` doesn't exist.
- [ ] `docs/architecture.md` has exactly two ` ```mermaid ` blocks, both `flowchart`,
      and `npx @mermaid-js/mermaid-cli` parses them without error (or they render in
      GitHub's preview).
- [ ] Every relative Markdown link in `README.md`, `CLAUDE.md`, `docs/architecture.md`
      and `docs/adr/*.md` points to a file that exists.
- [ ] Every class, function, file and table name in `docs/architecture.md` exists in
      the code (checked by grep in review).
- [ ] CLAUDE.md links to `docs/architecture.md`; its *Architecture* section doesn't
      list the layers' files one by one or the entities' fields; `grep -ni 'pi\b' CLAUDE.md`
      finds no Pi deployment text.
- [ ] `make docs` fails with "No rule to make target"; `docker compose config --services`
      doesn't list `kroki` (also with `--profile docs`).
- [ ] `cd backend && uv sync --locked` succeeds.
- [ ] `make test` passes.
- [ ] Jacopo reads CLAUDE.md and `docs/architecture.md` and agrees each fact is stated
      in one place.

## Open questions

---
Approved by: Jacopo Grotti · Date: 2026-11-20
