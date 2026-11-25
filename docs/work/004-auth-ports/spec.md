# 004 — Auth behind ports

App: Chatbot · Created: 2026-11-19
Status: shipped
<!-- draft → approved → building → in review → shipped | abandoned -->

## Why
Blueprint v2 decision D7 says services and the domain never import `bcrypt` or `jwt`.
Chatbot breaks that rule:
- `services/user/_auth.py` hashes passwords with `bcrypt` and mints tokens with `jwt`
  directly, and the login and register use cases import it.
- `entrypoints/dependencies.py` decodes the JWT inline in `get_current_user`.

Two behaviours also come with that code. Nobody has reported them yet:
- bcrypt runs on the event loop. Each register or login (~300 ms at the default cost)
  stalls every other request, including chat streams.
- A password longer than 72 bytes makes bcrypt ≥ 4.1 raise, so register/login
  answers 500.

Chatbot is the first app with users to be migrated to v2. So, as D5/D7 plan, it is
also the first app to put the canonical auth adapters into `shared/`. Other apps
(Blibiobot, Learn_German, Diario) will copy them later. Ports stay each app's own, as
D5 and BLUEPRINT §15 require ("never shared: domain models, ports, …"). This is the
fourth Chatbot Blueprint v2 change, after 001–003.

## What changes
Users see almost no difference: register, login, the language setting, chat and the CLI
work as before. Existing accounts keep their passwords, and tokens issued before the
deploy stay valid until they expire.

- **Ports** (Chatbot's own, in `domain/user/ports/`): `PasswordHasher` (async `hash` /
  `verify`) and `TokenService` (`issue` / `decode`), following Blibiobot's structure.
  They speak in plain values, not in Chatbot's `User`:
  - `issue` takes a subject (the user id) and extra claims (Chatbot: `username`) and
    returns a signed token;
  - `decode` returns the subject, or raises `TokenExpired` / `InvalidToken`;
  - the token errors stay in Chatbot's domain with their codes.
- **Adapters**: `adapters/security/bcrypt/`, `adapters/security/jwt/` (pyjwt) and
  `adapters/security/fake/` (an instant fake hasher, for tests only). They are wired in
  `entrypoints/dependencies.py`. The app always uses the real bcrypt adapter, never the
  fake.
- **Services see only a `user_id`**: the login and register use cases get the ports
  injected. `services/user/_auth.py` goes away. `get_current_user` asks the
  `TokenService` and gets back a `user_id`.
- **Token errors keep both codes**: an expired token is still 401 `token_expired`, and
  a malformed or badly signed one is still 401 `invalid_token`. The API answers exactly
  as today.
- **Behaviour fixes** (from Blibiobot's bcrypt adapter):
  - Hashing and verifying run in a worker thread, so a login no longer blocks other
    requests.
  - Passwords are cut to bcrypt's 72-byte limit instead of crashing, so a long
    passphrase can register and log in.
  - A stored hash that isn't valid bcrypt counts as a failed login (401), not a 500.
- **`shared/`**: only the bcrypt, pyjwt and fake **adapters** become canonical v1 files
  in `shared/backend/`. The ports do not. Each adapter subclasses the app's own port
  (only its import lines differ per app, which the drift check allows). The adapters
  have their own tests in `shared/tests/` and rows in `shared/README.md`. The README's
  "Planned" note for auth adapters is removed. Chatbot's copies carry the
  `# canonical:` headers.
  - The canonical adapters must not depend on any app's `User` type; they work with
    the subject and claims described above.
  - The canonical token adapter tells an expired token from a bad one, so Chatbot keeps
    both codes.
- **BLUEPRINT §3c (Auth)**: the "canonical auth files will be added to `shared/`" note
  now names the canonical adapters in `shared/`, and says the ports stay per app (in
  the shape above).

## Out of scope
- Blibiobot, Learn_German and Diario: none of them copies the canonical files now (each
  one does it when it is next migrated).
- Any change to token claims (they stay `sub`, `username`, `exp`), token lifetime, the
  signing algorithm or settings names (`JWT_SECRET_KEY` etc.), or to API paths and
  response shapes.
- Sharing the ports or the token errors through `shared/`: they stay per app (D5, §15).
- Admin roles, logout or token revocation, changing a password, rate-limit changes.
- The CLI's user resolution (`CHATBOT_CLI_USER`). The CLI has no tokens or passwords.
- Frontend changes, and Frontend v2 (the next backlog item).
- A database migration.

## Acceptance checks
- [ ] `grep -rnE "import (bcrypt|jwt)|from (bcrypt|jwt)" backend/src/chatbot` finds
      matches only under `adapters/security/`. `services/user/_auth.py` no longer
      exists.
- [ ] `make -C ../shared test` passes. It includes the tests of the new auth adapters:
      - hash then verify works;
      - a wrong password fails;
      - a malformed hash fails without raising;
      - a password over 72 bytes hashes and verifies;
      - an issued token decodes to the same user id;
      - an expired token and a tampered token raise the matching errors.
- [ ] `make -C ../shared drift APP=Chatbot` (or `make drift`) is clean, and the new auth
      adapter files are present in Chatbot with their `# canonical:` headers. No file
      under `domain/` carries a `# canonical:` header for auth.
- [ ] A token issued before this change (claims `sub`, `username`, `exp`, same secret)
      is accepted by the new `TokenService`: a unit test builds one the old way and
      calls an authenticated route.
- [ ] Unit tests use the fake hasher and a fake (or real, fixed-key) token service, and
      show:
      - a successful login returns a token;
      - a wrong password → 401 `invalid_credentials`;
      - an expired token → 401 `token_expired`;
      - a tampered token → 401 `invalid_token`.
- [ ] A unit test shows the API registers and logs in a user whose password is over
      72 bytes (no 500).
- [ ] `make test` passes (lint, typecheck, unit, integration, e2e).
- [ ] In the app (`make backend` + `make frontend`, or the dev stack): an account
      created **before** this change still logs in with its old password, and chat works.
- [ ] After deploy, `chatbot_api` is `healthy` on the mini-PC. You can log in with your
      existing account and send a message.

## Open questions
<!-- none -->

---
Approved by: Jacopo Grotti · Date: 2026-11-19
