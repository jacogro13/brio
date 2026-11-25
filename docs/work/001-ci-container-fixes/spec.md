# 001 — CI and container fixes

App: Chatbot · Created: 2026-11-19
Status: shipped
<!-- draft → approved → building → in review → shipped | abandoned -->

## Why
Chatbot can't deploy at the moment. CI runs on `ubuntu-latest`, which is Ubuntu 26.04,
and Playwright can't install Chromium there. The e2e job fails, so no image is
published. CI also still builds arm64 under QEMU, though the mini-PC is amd64 only
(BLUEPRINT §12). That makes builds slow and risks the QEMU/musl hang. Images have no
`sha-…` tag, so there is nothing to pin for a rollback.

The container also starts the way Famiglia did before 004: `entrypoint.sh` runs
`uv run alembic` and the image runs `uv run uvicorn`. Both re-resolve the environment
at every start, so startup is slow or never gets healthy.

This is the first of the Chatbot Blueprint v2 changes. It unblocks deploys before the
code work starts (backlog: "Backend v2 foundations", fleet-fixes part).

## What changes
Users see no difference.

- **CI** runs on `ubuntu-24.04`, builds amd64 only (no QEMU step, no arm64 platform),
  and tags each image with `sha-<short sha>` and the branch name, plus `latest`.
- **GitHub Actions** that target Node 20 are bumped to their current major versions
  (`actions/checkout`, `astral-sh/setup-uv`, `actions/setup-node`,
  `actions/upload-artifact`, `docker/*`), so CI shows no deprecation warnings.
- **Container start**: neither `entrypoint.sh` nor the image's CMD uses `uv run`.
  The venv's binaries are on `PATH`, as in Famiglia 004. Migrations still run
  automatically on every start.
- **`make test`** runs `lint typecheck unit integration e2e` (BLUEPRINT §8). For now,
  `lint` = frontend eslint and `typecheck` = frontend `tsc`. Backend ruff and pyright
  join these targets in the backend v2 spec. CI runs the same gates.
- **E2E self-contained check**: confirm `make e2e` needs nothing outside its own
  compose project (mock LLM, mock web tools, its own Garage and db, `down -v`). Record
  the result in `CLAUDE.md` as `E2E self-contained: yes/no (checked <date>)` so the
  factory knows whether it may run it.
- `CLAUDE.md`'s CI/CD paragraph no longer describes the multi-arch/QEMU build.

## Out of scope
- All backend v2 code: canonical `shared/backend/` files, D1 validated types, D2 error
  model, D3 ruff + pyright, D4 settings, D6 logging. Making `/health` quiet in the
  access log belongs there too: `/health` already exists, skips the DB, and both
  healthchecks already use it. That is the next spec.
- Imperative ORM mapping (its own backlog item, after backend v2).
- Whether SSE `error` events get a D2 `code` (decided in the backend v2 spec).
- Auth ports (D7), frontend v2, v1 docs cleanup and trimming `CLAUDE.md`.
- Any change to how the app behaves.

## Acceptance checks
- [ ] `grep -n "runs-on" .github/workflows/ci.yml` shows only `ubuntu-24.04`.
- [ ] `grep -n -i "qemu\|arm64" .github/workflows/ci.yml` finds nothing.
- [ ] No action in `ci.yml` is on a version that targets Node 20. A CI run on `main`
      shows no Node 20 deprecation warning.
- [ ] The CI run on `main` is green: lint, typecheck, unit, integration and e2e pass,
      and both images are pushed.
- [ ] ghcr.io has `chatbot-api` and `chatbot-frontend` images tagged
      `sha-<short sha>` for that commit (and `latest`).
- [ ] `grep -n "uv run" backend/entrypoint.sh backend/Dockerfile` finds nothing.
- [ ] `make test` runs `lint typecheck unit integration e2e` in that order, and passes.
- [ ] `CLAUDE.md` has an `E2E self-contained:` line with a date and the reason.
- [ ] After deploy, `docker ps` on the mini-PC shows `chatbot_api` as `healthy` within
      a minute of start, and you can log in, open an existing conversation and send
      a message.

## Open questions
<!-- none -->

---
Approved by: Jacopo Grotti · Date: 2026-11-19
