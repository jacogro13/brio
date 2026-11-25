# 003 — Imperative ORM mapping

App: Chatbot · Created: 2026-11-19
Status: shipped
<!-- draft → approved → building → in review → shipped | abandoned -->

## Why
BLUEPRINT's hard rule says ORM mapping is always imperative, but Chatbot's
`adapters/persistence/postgres/` uses `DeclarativeBase`: separate `UserModel`,
`ConversationModel`, `MessageModel`, `AttachmentModel` classes, plus hand-written
`_to_domain` / `_attachment_to_domain` copies in the repositories. Every new column
has to be added in three places (domain entity, `*Model`, copy function), and the
copies are easy to get wrong. Famiglia already maps its `Validated` entities
imperatively (`adapters/orm.py`), so the pattern is proven.

BLUEPRINT §3b makes it worse: its rich-form tree lists `persistence/postgres/models.py`
and names Blibiobot (declarative too) as the reference, so the next rich-form app would
copy the same thing.

## What changes
Nothing visible to users: same API, same behaviour, same database.

- Chatbot maps its domain entities (`User`, `Conversation`, `Message`, `Attachment`)
  directly onto `Table(...)` definitions with `map_imperatively` (Cosmic Python
  classical mapping, like Famiglia's `adapters/orm.py`), set up once at startup in
  `lifespan`, and also for the CLI (`make cli` talks to Postgres in-process, with no
  FastAPI `lifespan`) and wherever tests/Alembic need it.
- Chatbot's `CLAUDE.md` describes `orm.py` (imperative) instead of `models.py`.
- `models.py` with its `*Model` classes, the `DeclarativeBase` in `database.py`, and the
  `_to_domain*` copy functions are gone. Repositories return the mapped entities.
- Alembic's `env.py` targets the new `Table` metadata.
- The database schema is unchanged (tables, columns, types, defaults, indexes, FKs):
  no new migration.
- Repository and Unit of Work ports stay exactly as they are; services and their unit
  tests don't change. The conversation list still loads without messages.
- BLUEPRINT §3b: the tree shows `persistence/postgres/orm.py` instead of `models.py`,
  with a note that rich form maps imperatively exactly as §3a. Blibiobot's declarative
  mapping is recorded in §14 Known drift (Chatbot is the example for this point).

## Out of scope
- Any schema change or new Alembic migration.
- Changing repository / UoW ports, services, routes or the frontend.
- Fixing Blibiobot's (or any other app's) declarative mapping — only recorded as drift.
- Making Chatbot the overall §3b reference app instead of Blibiobot.
- Auth behind D7 ports, Frontend v2, docs cleanup (separate backlog items).

## Acceptance checks
- [ ] `grep -rn "DeclarativeBase\|declarative\|_to_domain\|Model("`
      finds nothing (run on `Chatbot/backend/src/chatbot/adapters`), and
      `adapters/persistence/postgres/models.py` no longer exists.
- [ ] Alembic autogenerate against a DB at `head` produces no changes
      (`alembic check` reports "No new upgrade operations detected"); no new file in
      `alembic/versions/`.
- [ ] `git diff main -- Chatbot/backend/src/chatbot/domain Chatbot/backend/src/chatbot/services`
      is empty: no port, service or entity changes (the domain doesn't know it is
      mapped).
- [ ] `make -C Chatbot test` (lint, typecheck, unit, integration, e2e) is green; the
      existing integration tests for the user, conversation and attachment repositories
      pass unchanged in what they assert.
- [ ] An integration test shows the conversation list returns conversations with empty
      `messages` without loading the messages table.
- [ ] A message with tool events and an attachment round-trips through the repository
      (saved, reloaded, equal to what was saved, `tool_events` as `ToolEvent` objects).
- [ ] In the running app: log in, open an existing conversation, send a message,
      upload an attachment, change conversation settings, rename and delete a
      conversation — all behave as before.
- [ ] `make cli`: `/list` and `/switch` show existing conversations, and sending a
      message in the CLI persists it (visible in the web app).
- [ ] BLUEPRINT §3b shows `orm.py` and says rich form maps imperatively; §14 lists
      Blibiobot's declarative mapping as known drift.

## Open questions

---
Approved by: Jacopo Grotti · Date: 2026-11-19
