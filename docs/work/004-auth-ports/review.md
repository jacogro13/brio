# 004 — Review

Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md) · Reviewed: 2026-11-19

Branch `work/004-auth-ports` (commits `d0aa439`…`c3ba4cf`, tasks 1–7, all `done`), reviewed
against `main` with `git diff main...work/004-auth-ports`, every file. The `shared/` and
BLUEPRINT parts are in the `Apps/` repo, committed directly on its `main` (`556258d`,
`1571c4f`, `c744fcc`, 3 ahead of `origin/main`, not pushed); read in full with `git show`.

## Automated checks
All run by the reviewer on the branch, clean working tree.
- `make lint typecheck` (Chatbot/): pass. ruff "124 files already formatted", "All checks
  passed!"; eslint clean; pyright 0 errors; `tsc -b` clean.
- `make unit` (Chatbot/): pass. Backend 153 passed (2 warnings: the existing
  `InsecureKeyLengthWarning` from a 16-byte test key). Frontend 14 passed.
- `make integration` (Chatbot/): pass, 29 passed.
- `make e2e` (Chatbot/, run because `CLAUDE.md` says `E2E self-contained: yes`): pass,
  13 passed; stack torn down with `down -v` (no `chatbot_e2e` containers left).
- `make -C shared test` (Apps/): pass. Python 71 passed (ruff, pyright clean), vitest 13 passed.
- `make -C shared drift APP=Chatbot` (Apps/): exit 0. The three security adapters and the
  five earlier backend files are `current`; frontend `client.ts`/`messages.ts` "not
  adopted" as before.
- `make -C shared drift` (all apps): exit 0; other apps show the new adapters only as
  "not adopted".

## Against the spec
- [x] **No `bcrypt`/`jwt` outside `adapters/security/`; `_auth.py` gone.** Met.
  `grep -rnE "import (bcrypt|jwt)|from (bcrypt|jwt)" backend/src/chatbot` matches only
  `adapters/security/bcrypt/bcrypt_password_hasher.py:11` and
  `adapters/security/jwt/pyjwt_token_service.py:11`. `services/user/` holds only
  `login_user.py` and `register_user.py`.
- [x] **`make -C ../shared test` passes, with the auth adapter tests.** Met.
  `shared/tests/test_security_password_hashers.py` (verify, wrong password, malformed hash
  → `False`, 100-byte password, hash ≠ plain, `$2b$04$` cost; parametrized over bcrypt and
  fake) and `shared/tests/test_security_token_service.py` (subject round-trip, exactly
  `sub`/`username`/`exp`, expired → `TokenExpired`, tampered / wrong key / garbage / no
  `sub` → `InvalidToken` and not `TokenExpired`).
- [x] **Drift clean, adapters carry `# canonical:` headers, none in `domain/` for auth.**
  Met. Drift output above; `grep -rn canonical backend/src/chatbot/domain` finds only
  `errors.py` and `validated.py`. Chatbot's copies differ from `shared/` only in import lines.
- [x] **Token issued the old way is accepted.** Met.
  `backend/tests/unit/test_api.py:248` `test_token_issued_by_the_old_code_is_accepted`
  builds `{sub, username, exp}` with `jwt.encode` and the app settings, calls
  `GET /conversations/` → 200.
- [x] **Unit tests with fake hasher / real fixed-key token service.** Met.
  `test_user_use_cases.py` uses `FakePasswordHasher` and `PyJwtTokenService(SECRET, …)`;
  `test_api.py`'s `Api` overrides `get_password_hasher` with the fake. Login returns a token
  (`test_user_use_cases.py:99`, `test_api.py` login tests); wrong password → 401
  `invalid_credentials` (`test_bad_login_is_401`, `test_api.py:215`); expired → 401
  `token_expired` and tampered → 401 `invalid_token` (`test_bad_token_is_401`,
  `test_api.py:279`, new tampered case).
- [x] **Password over 72 bytes registers and logs in.** Met.
  `test_api.py:228` `test_password_over_72_bytes_registers_and_logs_in` (real
  `BcryptPasswordHasher(rounds=4)`, 90 bytes) → 201 then 200 with a token. Chatbot locks
  bcrypt 5.0.0, which raised on this input before.
- [x] **`make test` passes.** Met: lint, typecheck, unit, integration, e2e all green above.
- [ ] **Account created before this change still logs in; chat works. User to verify.**
  Before switching: on `main`, start the dev stack (or `make backend` + `make frontend`) and
  make sure you have an account. Then `git switch work/004-auth-ports`, restart the backend,
  log in with that account and its old password, send a message in a conversation, and
  register a new account and log in with it. All should work, the username should show in
  the header, and the API log should show no 500.
- [ ] **After deploy, `chatbot_api` healthy and login + message work on the mini-PC. User
  to verify** after `/ship`: `docker ps` shows `chatbot_api` `healthy`; log in with your
  existing account (you should not even be logged out, as the token stays valid) and send a
  message.

## Blueprint
- **Hexagonal layering:** holds. Ports in `domain/user/ports/` import nothing from outer
  layers; services import only the ports and domain errors; adapters import the domain;
  wiring is in `entrypoints/dependencies.py`.
- **D7 (auth):** holds. Services see only a `user_id`; `get_current_user` turns the
  `TokenService` subject into a `UUID` and raises `InvalidToken` otherwise.
- **Canonical copies (§15, D5):** holds. Three new canonical v1 adapters, copied with
  headers unchanged; ports and token errors stay per app. The reference ports in `shared/`
  have no header and say so in their docstrings and the README.
- **Routes don't catch domain errors:** holds. `get_current_user` catches `ValueError` from
  `UUID()` to raise a domain error. That is a translation in the dependency, not a route
  catching a domain error.
- **UoW / imperative mapping:** untouched. Login and register still run inside the UoW.
- **Migrations:** none. Stored hashes stay `$2b$` at cost 12. Truncating to 72 bytes can't
  change any stored account: bcrypt 5.0 refused longer passwords, so none were stored.
- **Secrets / config:** nothing secret committed; no new environment variables
  (`JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` unchanged).
- **Italian UI / frontend:** no frontend change.

## Findings
- **should-fix S1:** `backend/tests/unit/test_user_use_cases.py:99-106`. The login test no
  longer checks that the token carries `username`. Before, it asserted
  `payload["username"] == "alice"`; now it checks only the subject. No other Chatbot test
  (unit or e2e) checks the claim. The frontend reads it to show who is logged in
  (`frontend/src/api/http.ts:16-23`, `App.tsx:148`), and the plan's *Risks* relies on it. If
  `login_user.py:27` stopped passing `{"username": …}`, every test would still pass. The
  shared test only proves the adapter writes whatever claims it is given. Fix within the
  spec: assert the claim again, e.g. a small recording fake `TokenService` in
  `test_login_returns_valid_token`, or decode with `jwt` there and check `username`. Not
  blocking.
- **note N1:** `Apps/BLUEPRINT.md` §14 (*v2 migration state*) was also edited (`c744fcc`):
  "Chatbot and Diario import bcrypt/jwt" → "Diario imports … (Chatbot fixed in its 004)".
  Plan task 6 named only §3c, but the edit keeps the known-defects list accurate. Accepted.
- **note N2:** the three `shared/`/BLUEPRINT commits are on `Apps/` `main` and not pushed
  (3 ahead of `origin/main`), as in Chatbot 003. `/ship` must push `Apps/` together with
  the Chatbot merge. Otherwise `make drift` on another checkout sees the Chatbot copies as
  unknown canonical files.
- **note N3:** `services/user/login_user.py:25`: an unknown username skips the bcrypt
  verify, so it answers ~300 ms faster than a wrong password. That timing shows whether a
  username exists. This was already so before the change, and registration's 409 reveals the
  same thing. No action.
- **note N4:** `get_token_service` builds a new `PyJwtTokenService` per request (cheap, no
  state); `get_password_hasher` caches one. Both fine.

## Verdict
**ready to ship once confirmed**: no must-fix findings, all automated checks green
(including e2e). The user has to confirm:
1. on the dev stack, an account created before this change logs in with its old password,
   chat works, and a new account registers (steps above);
2. after deploy, `chatbot_api` is `healthy` on the mini-PC and login + a message work.

Item 1 confirmed by user, 2026-11-19. Item 2 is checked after the deploy.

S1 (should-fix) doesn't block shipping; it is worth a one-test fix before or right after
the merge.

---
Shipped: merge of work/004-auth-ports · Date: 2026-11-19
