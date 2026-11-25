# 004 — Plan

Spec: [spec.md](spec.md) (approved 2026-11-19)

## Approach
First build the three canonical adapters in `shared/` with their own tests (bcrypt +
fake hasher, then pyjwt). Then copy them into Chatbot next to Chatbot's own ports, and
switch the app over in two steps: the hasher first, then the token service. Finally
delete `services/user/_auth.py`, update the docs and run the full gate.
BLUEPRINT §3c (Auth, D7), §3b (rich-form ports under `domain/<aggregate>/ports/`) and
§15 / `shared/README.md` (D5: ports are never shared) apply. No ADR: this follows D7
and decides nothing new. No API change, so no `make types`. No migration.

How the canonical adapters fit apps whose ports differ (decided here, from the spec):
- **Paths in `shared/`** (canonical sources; the header names this path):
  `backend/adapters/security/bcrypt/bcrypt_password_hasher.py`,
  `backend/adapters/security/fake/fake_password_hasher.py`,
  `backend/adapters/security/jwt/pyjwt_token_service.py`. Chatbot copies them to the same
  paths under `backend/src/chatbot/`. Each package gets an empty `__init__.py`, which is
  not canonical.
- **Reference ports in `shared/` are scaffolding, not canonical.** The adapters must
  import a port and the token errors in order to be tested, so `shared/backend/domain/`
  gets `ports/password_hasher.py`, `ports/token_service.py` and `auth_errors.py`, with
  **no** `# canonical:` header. Their docstring says: "Reference shape for the
  canonical security adapters. Not canonical: each app writes its own port (D5, §15)."
  The README lists them under *Not canonical*. Only the adapters' import lines point
  to them, and the drift check ignores import lines.
- **Port shapes**:
  - `PasswordHasher`: `async hash(plain) -> str`, `async verify(plain, hashed) -> bool`.
  - `TokenService`: `issue(subject: str, claims: Mapping[str, str | int | bool]) -> str`
    and `decode(token: str) -> str` (the subject).
  - `decode` raises `TokenExpired` for an expired token (a subclass of `InvalidToken`)
    and `InvalidToken` for anything else (bad signature, garbage, missing `sub`).
  - Chatbot keeps both errors in `domain/user/model.py`, with codes `token_expired` and
    `invalid_token`.
- **Adapter behaviour**:
  - `BcryptPasswordHasher(rounds=12)` (same cost as today's `gensalt()`) runs in
    `anyio.to_thread`, truncates the password to 72 UTF-8 bytes, and `verify` returns
    `False` (with a warning log) on a malformed hash.
  - `PyJwtTokenService(secret_key, algorithm, expiry_minutes)` writes exactly
    `sub` + the given claims + `exp`, with no `iat`, so the claims are unchanged.
  - `FakePasswordHasher` uses `fake-hash:<plain>`, as in Blibiobot.
- **Chatbot ports** are new files in `domain/user/ports/` with the shape above. The
  canonical adapters' import lines point to them and to `domain/user/model.py`.
  `get_current_user` turns the subject into a `UUID`, and a non-UUID subject is still
  `InvalidToken`.

## Tasks
| # | Task | Files | Check | Status |
|---|------|-------|-------|--------|
| 1 | **Shared: password hashers.** Add `bcrypt` to `shared/pyproject.toml` dependencies (`uv lock`). Reference port `backend/domain/ports/password_hasher.py` (scaffolding, see *Approach*). Canonical v1 `BcryptPasswordHasher` and `FakePasswordHasher`. Tests in `tests/test_security_password_hashers.py`, using `BcryptPasswordHasher(rounds=4)` to keep them fast: `test_hashed_password_verifies`, `test_wrong_password_does_not_verify`, `test_malformed_hash_does_not_verify` (no exception), `test_password_over_72_bytes_hashes_and_verifies`, `test_hash_is_not_the_plain_password`, and the fake's round-trip, with `parametrize` over both hashers where the behaviour is the same. | `shared/pyproject.toml`, `shared/uv.lock`, `shared/backend/domain/ports/{__init__,password_hasher}.py`, `shared/backend/adapters/security/{bcrypt,fake}/*.py`, `shared/tests/test_security_password_hashers.py` | `make -C shared test`; `make -C shared drift` still exits 0 | done |
| 2 | **Shared: token service + README.** Add `pyjwt` to the shared dependencies. Reference port `backend/domain/ports/token_service.py` and `backend/domain/auth_errors.py` (`InvalidToken(Unauthorized)` code `invalid_token`, `TokenExpired(InvalidToken)` code `token_expired`). Both are scaffolding. Canonical v1 `PyJwtTokenService`. Tests in `tests/test_security_token_service.py`: `test_issued_token_decodes_to_its_subject`; `test_issued_token_carries_exactly_sub_claims_and_exp` (decode with `jwt` in the test); `test_expired_token_is_token_expired` (`expiry_minutes=-1`); `test_bad_token_is_invalid_token`, parametrized over tampered signature, wrong key, garbage and no `sub`, and also checking it is *not* `TokenExpired`. `shared/README.md`: three rows (Decision D7, copy as `adapters/security/{bcrypt,fake,jwt}/…`), the reference ports and `auth_errors.py` under *Not canonical*, and "auth ports + adapters (D7)" removed from *Planned*. | `shared/pyproject.toml`, `shared/uv.lock`, `shared/backend/domain/{ports/token_service.py,auth_errors.py}`, `shared/backend/adapters/security/jwt/*.py`, `shared/tests/test_security_token_service.py`, `shared/README.md` | `make -C shared test`; `make -C shared drift` still exits 0 (other apps only show the new files as *not adopted*) | done |
| 3 | **Chatbot: ports + adapter copies (not wired).** New `domain/user/ports/password_hasher.py` and `token_service.py` (shape in *Approach*, Chatbot's own, no canonical header). Copy the three adapters into `backend/src/chatbot/adapters/security/{bcrypt,fake,jwt}/` with headers unchanged; fix only the import lines (ports → `chatbot.domain.user.ports.*`, errors → `chatbot.domain.user.model`). | `backend/src/chatbot/domain/user/ports/{password_hasher,token_service}.py`, `backend/src/chatbot/adapters/security/**` | `make drift` shows the three as `current`; `make lint typecheck unit-backend` | done |
| 4 | **Chatbot: switch to `PasswordHasher`.** `dependencies.get_password_hasher()` (cached `BcryptPasswordHasher()`), injected into `RegisterUserUseCase` and `LoginUserUseCase`, which now `await hasher.hash/verify`. `_auth.py` keeps only `create_access_token` for now. Tests: `test_user_use_cases.py` uses `FakePasswordHasher` (remove `test_hash_roundtrip`, now covered in `shared/`); `test_api.py`'s `Api` overrides `get_password_hasher` with the fake. New `test_password_over_72_bytes_registers_and_logs_in` overrides it with a real `BcryptPasswordHasher(rounds=4)` instead and expects 201, then 200 with a token. | `services/user/{register_user,login_user,_auth}.py`, `entrypoints/dependencies.py`, `tests/unit/test_user_use_cases.py`, `tests/unit/test_api.py` | `make lint typecheck unit-backend integration`; existing register/login tests and the new one pass | done |
| 5 | **Chatbot: switch to `TokenService`, remove `_auth.py`.** `dependencies.get_token_service(settings)` → `PyJwtTokenService(jwt_secret_key, jwt_algorithm, jwt_access_token_expire_minutes)`. `LoginUserUseCase(uow_factory, hasher, tokens)` returns `tokens.issue(str(user.id), {"username": user.username})`. `get_current_user` uses `tokens.decode` and turns the result into a `UUID`, raising `InvalidToken` if it isn't one. Delete `services/user/_auth.py`. Tests: `test_login_returns_valid_token` decodes through `PyJwtTokenService` (fixed key), not `jwt`; `test_api.py` keeps `_token()` building tokens with `jwt` directly. That is "the old way", and the existing `test_bad_token_is_401` cases (expired, garbage, non-UUID subject) now run through the new service. Add `test_token_issued_by_the_old_code_is_accepted` (claims `sub`, `username`, `exp`, as `_auth.create_access_token` wrote them → 200) and a tampered-signature case to `test_bad_token_is_401` → `invalid_token`. | `services/user/login_user.py`, `services/user/_auth.py` (delete), `entrypoints/dependencies.py`, `tests/unit/test_user_use_cases.py`, `tests/unit/test_api.py` | `make lint typecheck unit-backend integration`; `grep -rnE "import (bcrypt\|jwt)\|from (bcrypt\|jwt)" backend/src/chatbot` only matches `adapters/security/`; `_auth.py` gone | done |
| 6 | **Docs.** BLUEPRINT §3c *Auth*: replace "(The canonical auth files will be added …)" with: the bcrypt, pyjwt and fake adapters are canonical in `shared/backend/adapters/security/`; the ports stay per app in the shape `hash`/`verify` and `issue(subject, claims)`/`decode → subject`, with `TokenExpired ⊂ InvalidToken`; Chatbot is the reference. Chatbot `CLAUDE.md`: the `domain/user/ + services/user/` bullet names the ports and `adapters/security/` instead of `_auth.py`; the `get_current_user` description says `TokenService.decode`; the canonical copies line lists the three adapters. | `Apps/BLUEPRINT.md`, `Chatbot/CLAUDE.md` | `grep -n "_auth.py\|will be added" Apps/BLUEPRINT.md Chatbot/CLAUDE.md` finds nothing; review reading | done |
| 7 | **Full gate.** `make -C Chatbot test` (lint, typecheck, unit, integration, e2e; e2e is recorded as self-contained in `CLAUDE.md`), `make -C shared test` and `make -C shared drift APP=Chatbot`. Then hand the user the manual check: on the dev stack, which the user starts, log in with an account created **before** this change, send a message, register a new account. | — | all three green; user confirms the manual check | done |

## Risks
- **Database**: no migration, no schema change. Stored hashes stay `$2b$` bcrypt at cost 12,
  so existing passwords verify. Truncation can't break an existing account: bcrypt 5.0
  refused passwords over 72 bytes, so no stored hash comes from one, and older bcrypt
  versions truncated to the same 72 bytes.
- **Existing sessions**: tokens keep the same secret, algorithm and claims (`sub`,
  `username` — the frontend reads `username` for display — `exp`), so nobody is logged
  out by the deploy. Task 5's old-token test guards this.
- **Behaviour users notice**: none intended. A password over 72 bytes now works instead of
  a 500, and logins no longer stall other requests.
- **Other apps**: `shared/` gains files and dependencies (`bcrypt`, `pyjwt`). The drift check
  lists them as *not adopted* for the other apps, which doesn't fail. No app other than
  Chatbot changes, and nothing in `Infrastructure/` changes.
- **Secrets / env vars on the mini-PC**: none new. `JWT_SECRET_KEY` is unchanged.
- **Canonical scaffolding mistaken for canonical**: the reference ports in `shared/` could be
  copied by a later app as if they were shared. They carry no header, and their docstring
  and the README say so.

---
Approved by: Jacopo Grotti · Date: 2026-11-19
