# 001 — Plan

Spec: [spec.md](spec.md) (approved 2026-11-19)

## Approach
Copy what Famiglia already does: its `backend/Dockerfile` and `entrypoint.sh` (Famiglia
004 / its ADR-010, BLUEPRINT §7), its CI runner and `sha-…` tags (`ci-cd.yml`), and its
Makefile `lint`/`typecheck`/`frontend/node_modules` targets (BLUEPRINT §8). Here they
are frontend-only for now. Chatbot goes one step further than Famiglia: no QEMU/arm64
(BLUEPRINT §12) and no actions on Node 20. No new ADR: the "start without `uv run`"
decision is already in BLUEPRINT §7, and dropping arm64 follows §12.

Facts checked while planning (2026-11-19):
- `npm run lint` and `npx tsc -b` already pass in `frontend/`.
- `uv lock --check` passes.
- `httpx`, the only dev-group package that runtime code imports, is also a main
  dependency, so `--no-dev` is safe.
- CI today runs no frontend checks at all (not even vitest).

## Tasks

| # | Task | Files | Check | Status |
|---|------|-------|-------|--------|
| 1 | **Image starts without `uv run`.** `backend/Dockerfile`, following Famiglia's: `COPY pyproject.toml uv.lock ./`, `uv sync --frozen --no-install-project --no-dev`, then copy `src`/`alembic`/`alembic.ini` as now, `uv sync --frozen --no-dev`, add `ENV PYTHONDONTWRITEBYTECODE=1`, `ENV PYTHONUNBUFFERED=1` and `ENV PATH="/app/.venv/bin:$PATH"` (with Famiglia's one-line comment), `CMD ["uvicorn", "chatbot.entrypoints.main:app", "--host", "0.0.0.0", "--port", "80"]`. `backend/entrypoint.sh`: `alembic upgrade head`. | `backend/Dockerfile`, `backend/entrypoint.sh` | `grep -n "uv run" backend/entrypoint.sh backend/Dockerfile` finds nothing. `docker build -t chatbot-api-check backend`, then `docker run --rm --network none -e DATABASE_URL=postgresql+asyncpg://x:x@nowhere:5432/x chatbot-api-check` exits with alembic's DB connection error and shows no uv `Downloading`/`Installed` lines (if the build stalls on the laptop's WireGuard MTU, Jacopo runs these two commands). `make unit-backend` | done |
| 2 | **Makefile gates.** Add `frontend/node_modules` (as in Famiglia: `npm install` + `touch`), `lint: frontend/node_modules` → `cd frontend && npm run lint`, `typecheck: frontend/node_modules` → `cd frontend && npx tsc -b`, each with a comment that the backend ruff/pyright join in the backend v2 spec. `unit-frontend` depends on `frontend/node_modules`. `test: lint typecheck unit integration e2e`. Add `lint typecheck` to `.PHONY` if present. `test-backend` stays as is (it gets the backend gates in the next spec). `CLAUDE.md` *Aggregates*: `make test` line says the new order, and `make lint` / `make typecheck` are listed. | `Makefile`, `CLAUDE.md` | `make lint typecheck` passes. `make -n test` shows lint, typecheck, unit, integration, e2e in that order | done |
| 3 | **CI runner + frontend gates.** In `.github/workflows/ci.yml`: every `runs-on` → `ubuntu-24.04`. In the `test` job, after the backend tests, add as in Famiglia: setup-node (Node 20, npm cache on `frontend/package-lock.json`), `npm ci`, `npm run lint`, `npx tsc -b`, `npm test` (all in `frontend/`). | `.github/workflows/ci.yml` | `grep -n "runs-on" .github/workflows/ci.yml` shows only `ubuntu-24.04`. YAML parses (`python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"`). Locally `cd frontend && npm ci && npm run lint && npx tsc -b && npm test` passes | done |
| 4 | **amd64 only + `sha-…` tags.** In both build jobs: remove the "Set up QEMU" step, set `platforms: linux/amd64`, remove `provenance: false` and its QEMU comment, and give `docker/metadata-action` `tags: \| type=ref,event=branch / type=sha` with Famiglia's comment ("pin it as IMAGE_TAG to roll back"). Keep the extra `:latest` tag (docker-autoupdate pulls it). | `.github/workflows/ci.yml` | `grep -n -i "qemu\|arm64\|provenance" .github/workflows/ci.yml` finds nothing. `grep -c "type=sha" .github/workflows/ci.yml` = 2. YAML parses | done |
| 5 | **No actions on Node 20.** For each action in `ci.yml` (`actions/checkout`, `astral-sh/setup-uv`, `actions/setup-node`, `actions/upload-artifact`, `docker/setup-buildx-action`, `docker/login-action`, `docker/metadata-action`, `docker/build-push-action`), find the latest major release and check that its `action.yml` declares `runs.using: node24` (e.g. `gh api repos/<owner>/<repo>/contents/action.yml?ref=<tag> --jq .content \| base64 -d \| grep using`). Bump `ci.yml` to that major. Read each bumped action's release notes for breaking input changes and adapt. If an action has no Node 24 release yet, leave it, note it in the task row and in the backlog line at ship. | `.github/workflows/ci.yml` | For every `uses:` line, the `gh api` check prints `node24` (paste the list in the task notes). YAML parses | done (see notes) |
| 6 | **E2E self-contained check + CLAUDE.md CI/CD.** Check by reading, not by running: `Makefile` `e2e` (own project `chatbot_e2e`, `down -v` on exit), `docker-compose.e2e.yml` (no db/garage host ports, `LLM_BASE_URL=` → mock LLM, `WEB_TOOLS_ENABLED=false` → mock web tools), `docker-compose.yml` (own `garage`/`db` services, api `GARAGE_ENDPOINT=http://garage:3900`), the keys in `.env.example` that the api reads via `env_file` (look for any other external URL; read only `.env.example`, never `.env`), and `e2e/` specs (only `http://localhost:120`). Record it in `CLAUDE.md`'s E2E section as `E2E self-contained: yes\|no (checked 2026-11-<dd>) — <reason>`, in Famiglia's wording. Rewrite the *CI/CD* paragraph: lint/typecheck/unit (backend + frontend) → integration → browser e2e → amd64 Docker build & push with `sha-…`, branch and `latest` tags. | `CLAUDE.md` | `grep -n "E2E self-contained:" CLAUDE.md` hits. `grep -n -i "arm64\|qemu\|multi-arch" CLAUDE.md` finds nothing | done |
| 7 | **Full gate.** All the spec's local checks. | — | `make test` (lint, typecheck, unit, integration; e2e too if task 6 says self-contained, otherwise Jacopo runs `make e2e`). The CI-run, ghcr-tag and mini-PC checks happen at ship | done |

### Task 5 notes (2026-11-19)
`runs.using` of each action as now pinned in `ci.yml` (`gh api …/action.yml?ref=<tag>`):

| Action | Was | Now | runs.using |
|---|---|---|---|
| actions/checkout | v4 | v7 | node24 |
| astral-sh/setup-uv | v4 | v10.3.3 | node24 |
| actions/setup-node | v4 | v7 | node24 |
| actions/upload-artifact | v4 | v7 | node24 |
| docker/setup-buildx-action | v3 | v4 | node24 |
| docker/login-action | v3 | v4 | node24 |
| docker/metadata-action | v5 | v6 | node24 |
| docker/build-push-action | v5 | v7 | node24 |

- setup-uv publishes no floating `@vN` tags since v8 (its v8.0.0 notes: immutable tags
  only, for supply-chain safety), so it is pinned to the latest v10 release `v10.3.3`.
- Release notes of every skipped major read; none renames or removes an input this
  workflow uses. Behaviour changes that apply: setup-uv caches by default since v5
  (keyed on `uv.lock`), build-push writes a build summary since v6, and with
  `provenance: false` gone (task 4) build-push attaches its default provenance.

## Risks
- **This push is the first deploy in a while.** CI has been red since `ubuntu-latest`
  became 26.04, so everything merged to `main` since then deploys with it. At ship,
  check `git log` against the image running on the mini-PC so nothing unexpected goes
  out. If the new image fails, pin the previous image (the mini-PC still has it) until
  it's fixed. There's no earlier `sha-…` tag to roll back to; this change creates the
  first.
- **The image changes how it starts.** `--frozen` fails the build if `uv.lock` drifts
  from `pyproject.toml`, which is the point. `--no-dev` removes test packages from the
  image; checked that runtime code only needs main dependencies. Task 1's
  `docker run --network none` proves the start needs no network.
- **amd64 only.** The mini-PC is amd64 (BLUEPRINT §12) and nothing else runs these
  images. `:latest` is still pushed, so `docker-autoupdate` keeps working (provided root's
  GHCR login is valid: see the GHCR root-login memory; check the autoupdate log at ship).
- **Action major bumps** may rename inputs. Task 5 reads the release notes, and the
  first CI run on `main` is the real check. A failing CI deploys nothing, so the
  failure mode is "no deploy", not a broken production.
- **No migrations, no env vars, no secrets, no `deployment/` change.** Users see no
  change. Other apps and `Infrastructure/` are untouched.
- **Node 20 as the job's Node version** (`node-version: 20` for npm/Playwright) is
  not the same as the actions' runtime and stays as it is. Node 20 is past its end of
  life, so bumping it is a later item, outside this spec.

---
Approved by: Jacopo Grotti · Date: 2026-11-19

## Fixes from review (2026-11-19)

| # | Task | Files | Check | Status |
|---|------|-------|-------|--------|
| R1 | **Commit the lockfile** (review finding 1). Remove the `backend/uv.lock` line from `.gitignore`, run `cd backend && uv lock --check`, and commit `backend/uv.lock`, so the CI checkout has the file that `backend/Dockerfile`'s `COPY pyproject.toml uv.lock ./` needs. | `.gitignore`, `backend/uv.lock` | `git ls-files backend/uv.lock` lists it. `git archive HEAD backend \| tar -t \| grep uv.lock` hits. `git check-ignore backend/uv.lock` prints nothing | done |
