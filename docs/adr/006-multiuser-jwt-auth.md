# ADR-006: Multiuser with JWT bearer + bcrypt

**Status**: Accepted
**Date**: 2026-07-13

## Context

Through Phase 6 the Chatbot was single-user: every conversation was globally
visible and any client could read or mutate any conversation. Phase 7 makes it a
multiuser app on the LAN — each person sees only their own conversations — while
keeping the deployment simple (no external identity provider, no cookies/CSRF
machinery). The app already ships frontend + CLI + backend together, and Diario
(`Apps/Diario`) is the one existing app with auth, using JWT bearer + bcrypt.

## Decision

**JWT bearer + bcrypt, copying Diario's pattern.** `POST /auth/register`
(open self-registration) and `POST /auth/login` (returns an HS256 access token,
`{sub, username, exp}`). Passwords are bcrypt-hashed. Every `/conversations`
route depends on `get_current_user`, which decodes the bearer token to a
`user_id` (401 on invalid/expired). Tokens live 30 days — this is a LAN app.

- **Ownership is a scoped repository predicate.** `Conversation.user_id` is a
  nullable FK. The repo's `get`/`list`/`delete` all take `user_id` and filter on
  it, so a cross-user (or missing) conversation reads as `None` → **404**. There
  is no separate authorization layer; scoping *is* the authorization.
- **First-registered user adopts legacy conversations.** Rows created before
  Phase 7 have `user_id IS NULL`. `register_user`, when it sees `users.count() ==
  0`, calls `claim_orphans(new_user.id)` in the **same transaction** — so the
  first account atomically inherits the pre-multiuser history. Later registrants
  start empty.
- **One concrete UoW, two ports.** `SqlAlchemyConversationUnitOfWork` implements
  both `AbstractConversationUnitOfWork` and the new `AbstractUserUnitOfWork`
  (exposing `users` **and** `conversations` on one session), so register +
  adoption commit atomically without a second session.
- **CLI has no JWT.** The terminal REPL resolves its acting user from
  `CHATBOT_CLI_USER` (explicit), or the sole existing user (implicit), or exits
  with guidance. Registration is web-only.
- **An unauthenticated `/health` route** backs the container healthcheck, since
  every `/conversations` route now requires a token.

## Consequences

- SSE streaming is unaffected: the frontend uses `fetch` (not `EventSource`), so
  the `Authorization` header rides the streaming routes. Attachment downloads
  switch from `<a href>` to `fetch → blob → objectURL` for the same reason (a
  plain link can't carry a bearer header).
- `JWT_SECRET_KEY` is **required** — the api won't start without it. Rotating it
  invalidates every issued token (all users re-login). `make env` generates it.
- `POST /auth/login` is slowapi rate-limited (`LOGIN_RATE_LIMIT`, default
  `5/minute` per IP; e2e raises it to `100/minute`).
- Persistence stays declarative (`models.py`), matching the app's existing
  deviation from the Apps-wide imperative-mapping rule — `UserModel` follows suit.

## Migration

`0006_add_users_and_conversation_owner` creates `users` (id, username unique,
hashed_password, created_at) and adds the nullable `conversations.user_id` FK
(`ondelete=CASCADE`) + index. Existing conversations stay ownerless until the
first user registers.
