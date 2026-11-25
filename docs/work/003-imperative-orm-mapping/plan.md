# 003 — Plan

Spec: [spec.md](spec.md) (approved 2026-11-19)

## Approach
Add `adapters/persistence/postgres/orm.py` next to the declarative `models.py`: a
`registry()`, four `Table`s copied column for column from `models.py`, a `ToolEventList`
`TypeDecorator`, and an idempotent `start_mappers()` like Famiglia's `domain_mapper()`.
Before any of that, add an integration test that migrates a Postgres container to `head`
and checks Alembic `compare_metadata` against the ORM metadata. It runs first against
`Base.metadata` and then against `orm.metadata`, and it is what proves "schema unchanged".
Then switch the two repositories to the mapped entities one at a time (the old `*Model`
classes are separate classes on the same tables, so both can live side by side), and
finally delete the declarative code. Ports, services and the domain stay untouched.
BLUEPRINT §3a/§3b ("Rules at a glance": mapping is imperative) and §14 apply. No ADR:
this follows an existing rule and decides nothing new. No API change, so no `make types`.
No canonical `shared/` file changes, so no `make drift`.

Mapping details the build must respect (domain classes can't change):
- `Message` has no `conversation_id` field. Map the column under the private property
  `_conversation_id`; `Validated` ignores `_` names. `save_message` sets it before
  `session.add`.
- Relationships `Conversation.messages` and `Message.attachments` (ordered by
  `created_at`) use `lazy="raise"` and `passive_deletes=True`. Every load says what it
  needs: `get` uses `selectinload` for messages → attachments, `list` uses `noload` for
  messages. A forgotten load then fails in tests instead of as `MissingGreenlet` in prod.
- `Attachment` maps `conversation_id`/`message_id` as plain columns, with no relationship
  back to `Message`.
- `tool_events`: `ToolEventList(TypeDecorator)` with `impl = JSONB`, using
  `ToolEvent.to_json`/`from_json`. `None` stays `None`. The stored shape is unchanged.
- Column types, nullability, `index=True`/`unique=True`, FK `ondelete="CASCADE"` and
  `server_default="en"` exactly as in `models.py`, so index names match the migrations.
  Plus `index=True` on `messages.conversation_id` (created by migration 0001, missing
  from `models.py` — found by task 1).

## Tasks
| # | Task | Files | Check | Status |
|---|------|-------|-------|--------|
| 1 | **Schema drift test (safety net).** New integration test: start the Postgres testcontainer, run `alembic upgrade head` through the Alembic command API (`DATABASE_URL` via `monkeypatch`), then assert `alembic.autogenerate.compare_metadata(ctx, Base.metadata) == []`. Use `parametrize` over the metadata objects so task 2 can add `orm.metadata`. If it is red now, the schema has already drifted: stop and report. *Amended:* it was red on one known drift — migration 0001 creates `ix_messages_conversation_id`, the model lacked it — so add `index=True` to `MessageModel.conversation_id` (ORM catches up with the DB; no migration). | `backend/tests/integration/test_migrations.py` (new) | `make integration`; `test_migrated_schema_matches_orm_metadata[declarative]` passes | done |
| 2 | **Add `orm.py` (not wired yet).** `mapper_registry`, `metadata`, tables `users`, `conversations`, `messages`, `attachments` as above, `ToolEventList`, and `start_mappers()` (idempotent through `sa_inspect`, as in Famiglia) mapping `User`, `Conversation`, `Message`, `Attachment` with the relationships and `_conversation_id` described in *Approach*. Add `orm.metadata` to task 1's parametrize. Unit tests for `ToolEventList`: `process_bind_param`/`process_result_value` round-trip a list of events, and `None` stays `None` (parametrize). | `backend/src/chatbot/adapters/persistence/postgres/orm.py` (new), `tests/integration/test_migrations.py`, `tests/unit/test_orm_types.py` (new) | `make lint typecheck unit-backend integration`; `test_migrated_schema_matches_orm_metadata[imperative]` passes | done |
| 3 | **Wire the mappers + switch the user repository.** Call `start_mappers()` in FastAPI `lifespan` (before `yield`), in the CLI's `build_context()`, and in the integration fixtures (`pg_session` in the three repository test files). Rewrite `PostgresUserRepository` on the mapped `User` (`select(User)`, `session.add(user)`, `update(User)…`), with no `_to_domain`. Unit test: running the app's lifespan (`with TestClient(create_app())`) leaves `User` mapped (`sa_inspect(User)` doesn't raise). | `entrypoints/main.py`, `entrypoints/cli/dependencies.py`, `adapters/persistence/postgres/user_repository_impl.py`, `tests/integration/test_*_repository.py`, `tests/unit/test_api.py` (or a new small test file) | `make lint typecheck unit-backend integration`; `test_user_repository.py` passes unchanged in what it asserts; `test_app_startup_maps_domain_entities` passes | done |
| 4 | **Switch the conversation repository.** Rewrite `PostgresConversationRepository` on the mapped `Conversation`/`Message`/`Attachment`: `get` with `selectinload`, `list` with `noload`, `add` = `session.add`, `save_message` sets `_conversation_id` and adds it, `update_title`/`update_settings`/`link_attachments` assign on the loaded entities, deletes and `claim_orphans` stay single statements. Remove `_to_domain`, `_to_domain_no_messages`, `_attachment_to_domain`. Port `test_legacy_tool_events_row_loads` from `MessageModel(...)` to a Core `insert(orm.messages)`. | `adapters/persistence/postgres/conversation_repository_impl.py`, `tests/integration/test_conversation_repository.py`, `tests/integration/test_attachments_repository.py` | `make lint typecheck unit-backend integration`; existing conversation/attachment repository tests pass | done |
| 5 | **New repository tests for the risky paths** (Postgres, same session as the services use): `test_list_returns_conversations_without_loading_messages` (empty `messages`, and a small hand-written statement recorder on the engine's `before_cursor_execute` event sees no `FROM messages`); `test_message_with_tool_events_and_attachment_round_trips` (save + link, reload in a **new** session, equal to what was saved, `tool_events` are `ToolEvent`s); `test_get_then_delete_messages_then_save_message_commits` (the edit/regenerate flow: `get` → `delete_messages` → `save_message` → commit, reload shows the right messages); `test_update_settings_on_loaded_conversation_persists` (`get` → `update_settings` → `setattr` like `UpdateConversationUseCase` → commit → reload). | `tests/integration/test_conversation_repository.py`, `tests/integration/test_attachments_repository.py` | `make integration`; the four tests pass | done |
| 6 | **Remove the declarative code.** Delete `models.py`; drop `Base`/`DeclarativeBase` from `database.py`; Alembic `env.py` gets `target_metadata = orm.metadata`; fixtures `create_all` on `orm.metadata`; remove the unused `in_memory_session` fixture in `tests/conftest.py` (sqlite, never used, can't create JSONB); task 1's parametrize keeps only `imperative`. | `adapters/persistence/postgres/{models.py (delete),database.py}`, `backend/alembic/env.py`, `backend/tests/conftest.py`, `tests/integration/*.py` | `make lint typecheck unit-backend integration`; `grep -rn "DeclarativeBase\|declarative\|_to_domain\|Model(" backend/src/chatbot/adapters` is empty; `models.py` gone; `git diff main -- backend/src/chatbot/domain backend/src/chatbot/services` is empty; `git status backend/alembic/versions` shows nothing new | done |
| 7 | **Docs.** BLUEPRINT §3b tree: `persistence/postgres/orm.py` instead of `models.py`, plus one line: "mapping is imperative, exactly as §3a (`orm.py` + `start_mappers()` in `lifespan`)". BLUEPRINT §14: Blibiobot maps declaratively; Chatbot is the rich-form example for this point. Chatbot `CLAUDE.md`: the `adapters/persistence/postgres/` bullet names `orm.py` (imperative `Table`s + `start_mappers()`, called in `lifespan` and the CLI). | `Apps/BLUEPRINT.md`, `Chatbot/CLAUDE.md` | `grep -n "models.py" BLUEPRINT.md Chatbot/CLAUDE.md` shows no rich-form/Chatbot mention; review reading | done |
| 8 | **Full gate.** `make -C Chatbot test` (lint, typecheck, unit, integration, e2e; e2e is recorded as self-contained in `CLAUDE.md`). Then hand the user the manual checks from the spec: web app (log in, open, send, upload, settings, rename, delete) and `make cli` (`/list`, `/switch`, send, then see it in the web app). Both run against the dev stack, which the user starts. | — | `make test` green; user confirms the manual checks | done (make test green 2026-11-19; manual checks handed to the user) |

## Risks
- **Database / migrations:** no migration is added, and the deploy runs `alembic upgrade
  head` as a no-op. Tasks 1, 2 and 6 prove with `compare_metadata` that the imperative tables
  equal the migrated schema, so existing rows are untouched. If task 1 shows drift that
  already exists, we stop rather than "fix" it here (out of scope).
- **Session side effects (new with mapping):** loaded entities are now tracked, so
  services that assign to a loaded `Conversation` (`UpdateConversationUseCase` `setattr`,
  `update_title`) produce UPDATEs on flush. They write the same values, so this is harmless.
  Removing a message from `conv.messages` would null its FK. No code does that, deletes
  are explicit statements, and `passive_deletes=True` keeps the ORM from touching children.
  Task 5 covers the edit/regenerate and settings flows.
- **Async lazy loads:** `lazy="raise"` makes any unplanned load fail in integration/e2e
  tests, not in production.
- **Global mapping:** `start_mappers()` instruments the domain classes for the whole process.
  Unit tests that start the app (task 3) map them too. Entities still construct and compare
  normally (as in Famiglia), and the call is idempotent.
- **Users:** no visible change. `main` deploys within ~5 min of the push; e2e plus the
  manual checks in task 8 cover the flows before that. No other app, `Infrastructure/`,
  env var or secret is affected. BLUEPRINT edits only change docs for future apps.

---
Approved by: Jacopo Grotti · Date: 2026-11-19
Amendment (index on `messages.conversation_id`, tasks 1–2) approved by Jacopo Grotti in chat · 2026-11-19
