# 003 — Review

Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md) · Reviewed: 2026-11-19

Branch `work/003-imperative-orm-mapping` (commits `d6eee8b`…`9f005fd`, tasks 1–8, all `done`),
reviewed against `main` with `git diff main...work/003-imperative-orm-mapping`, every file.

## Automated checks
All run by the reviewer on the branch, clean working tree.
- `make lint typecheck` (Chatbot/): pass. ruff format + check "All checks passed!", pyright
  0 errors, `tsc -b` clean.
- `make unit` (Chatbot/): pass. Backend 151 passed (the 2 warnings are the existing
  `InsecureKeyLengthWarning` in `test_user_use_cases.py`, not from this change). Frontend 14 passed.
- `make integration` (Chatbot/): pass. 29 passed, including
  `test_migrated_schema_matches_orm_metadata[imperative]` and the four new task 5 tests.
- `make e2e` (Chatbot/, run because `CLAUDE.md` says `E2E self-contained: yes`): pass,
  13 passed. The stack was torn down with `down -v`.
- `make -C shared drift APP=Chatbot` (Apps/): pass. All 5 canonical backend files are `current`.
  The frontend `client.ts` and `messages.ts` are "not adopted", which was already so.

## Against the spec
- [x] **No declarative code left.** Met.
  `grep -rn "DeclarativeBase\|declarative\|_to_domain\|Model(" backend/src/chatbot/adapters`
  is empty, and `adapters/persistence/postgres/models.py` no longer exists.
- [x] **Alembic finds no schema changes, no new migration.** Met.
  `tests/integration/test_migrations.py` migrates a fresh Postgres to `head` and asserts
  that `compare_metadata(…, orm.metadata) == []`. This is the same comparison `alembic check`
  makes, because `env.py` sets `target_metadata = orm.metadata` with default compare options.
  `git diff main...HEAD -- backend/alembic/versions` is empty.
- [x] **Domain and services untouched.** Met.
  `git diff main...HEAD -- backend/src/chatbot/domain backend/src/chatbot/services` is empty.
- [x] **Full test suite green, existing repository tests unchanged.** Met.
  Lint, typecheck, unit, integration and e2e are all green (see above). The existing
  repository tests changed only in fixtures and imports (`orm.metadata`, `start_mappers()`).
  The two tests that used `MessageModel` now use a raw `table("messages", …)` with JSONB
  (`test_save_message_round_trips_tool_events`, `test_legacy_tool_events_row_loads`).
  No assertion was removed or loosened.
- [x] **Conversation list does not load messages.** Met.
  `test_list_returns_conversations_without_loading_messages` asserts that `messages == []` and
  that a `before_cursor_execute` recorder sees no `FROM messages`.
- [x] **Message with tool events and an attachment round-trips.** Met.
  `test_message_with_tool_events_and_attachment_round_trips` reloads in a new session,
  checks equality with what was saved, and checks that the events are `ToolEvent`s.
- [ ] **Web app works as before. User to verify.** Start the dev stack, log in, open an existing
  conversation, send a message, upload an attachment and send it with a message, change the
  conversation settings (temperature / max tokens / system prompt), rename the conversation,
  then delete it. Each step should behave as before, with no 500s in the API log.
- [ ] **CLI works as before. User to verify.** Run `make cli`, then `/list` and `/switch` to
  an existing conversation, then send a message. Reload the conversation in the web app and
  the message should be there.
- [x] **BLUEPRINT updated. Met in the working tree, not committed.** §3b now shows `orm.py`
  plus the line "Mapping is imperative, exactly as §3a…", and §14 lists Blibiobot's
  declarative mapping. Both edits are uncommitted changes to `Apps/BLUEPRINT.md`
  (see finding S1).

## Blueprint
- **Imperative mapping (hard rule):** holds. `orm.py` has `registry()`, `Table`s, and
  `map_imperatively` in an idempotent `start_mappers()`. It is called in `lifespan`
  (`entrypoints/main.py`), in `build_context()` (`entrypoints/cli/dependencies.py`) and in
  the integration fixtures.
- **Layering:** holds. `orm.py`, an adapter, imports the domain. Domain and services import
  nothing new. The entrypoints import `start_mappers` from the adapter layer, as they already
  did for `database.py`.
- **Unit of Work:** unchanged. `expire_on_commit=False` is still set in
  `make_session_factory`, so entities returned after commit are safe to read in async code.
- **Canonical copies:** none changed. Drift is clean.
- **Routes and components:** not touched. No frontend change, so the Italian UI-text rule
  doesn't apply.
- **Migrations:** none added. In production, `alembic upgrade head` in `entrypoint.sh` is a
  no-op, so existing rows are untouched. The `index=True` on `messages.conversation_id` only
  catches the ORM up with `ix_messages_conversation_id`, which migration 0001 already creates
  (the approved amendment).
- **Secrets and config:** no new environment variables and nothing secret committed.
- **Weakened checks:** no new `noqa`, `type: ignore`, `pyright: ignore`, skip or xfail. The
  deleted `tests/conftest.py` held only the unused sqlite `in_memory_session` fixture, and
  plan task 6 asked for its removal.

## Findings
- **should-fix S1:** the task 7 BLUEPRINT edits are not committed. They exist only as
  uncommitted changes in the `Apps/` repo: `Apps/BLUEPRINT.md:248`, `:256` and `:748`.
  `Apps/factory/BACKLOG.md:71` is also uncommitted (the "→ Chatbot 003" marker). This is a
  different repo from the work branch, so nothing in `work/003-*` carries them. Commit them
  in `Apps/` at ship time, or they can be lost or swept into an unrelated commit.
- **note N1:** `backend/tests/unit/test_startup.py:11` calls `orm.mapper_registry.dispose()`
  to unmap the domain classes before starting the app. This works, and `lifespan` maps them
  again, but it changes process-wide state. Unit tests that run after it, or after any
  `TestClient(create_app())`, see instrumented domain classes. Entities still construct and
  compare normally, and all 151 tests pass, so nothing needs to change.
- **note N2:** `test_migrations.py` uses `compare_metadata` with default options, so server
  defaults are not compared. `users.language server_default="en"` is checked only by reading:
  `orm.py:101` is identical to the deleted `models.py`.
- **note N3:** `update_title` and `update_settings` use `session.get(Conversation, id)` with
  no `user_id` filter (`conversation_repository_impl.py:94`, `:103`). This is unchanged from
  before: callers always `get(id, user_id)` first.
- **note N4:** `docs/IMPROVEMENT_PLAN.md:107` and `:190` still describe the declarative
  `models.py` / `UserModel`. That is historical planning text, not reference docs, so it can
  stay. `CLAUDE.md` is updated.

## Verdict
ready to ship once confirmed — the user confirms the web-app checks and the `make cli` checks
listed under *Against the spec*, and commits the BLUEPRINT.md edits in `Apps/` (S1).

Confirmed by user, 2026-11-19: web-app and `make cli` checks pass; BLUEPRINT.md committed in `Apps/` (534a4e1).

---
Shipped: merge of work/003-imperative-orm-mapping · Date: 2026-11-19
