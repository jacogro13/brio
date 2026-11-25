# 001 — Review

Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md) · Reviewed: 2026-11-19 (round 2)

Branch `work/001-ci-container-fixes` (head `aaf1f4a`), diffed against `main`. Round 1
(`1fea611`) found one must-fix: `backend/uv.lock` was not committed. Fix task R1
(`aaf1f4a`) is marked done. This round re-checks the whole change, not just the fix.

## Automated checks
- `make lint typecheck` (from `Chatbot/`): **pass** (eslint clean, `tsc -b` clean).
- `make unit` (from `Chatbot/`): **pass**: backend 91 passed, frontend vitest 10 passed.
- `make -C shared drift APP=Chatbot` (from `Apps/`): **pass** (exit 0). It lists the 7
  canonical files as "not adopted", which is expected: that is the backend/frontend v2
  specs, out of scope here.
- `make integration` (from `Chatbot/`): **pass**: 23 passed (testcontainers).
- `make e2e` (from `Chatbot/`; `CLAUDE.md:59` says `E2E self-contained: yes`, and I
  checked that claim in round 1): **pass**: 13 passed.
- Clean-checkout build, to stand in for CI: `git archive HEAD backend` extracted into an
  empty folder, then `docker build` of it: **pass**. The archive contains `uv.lock`.
  `docker run --rm --network none -e DATABASE_URL=postgresql+asyncpg://x:x@nowhere:5432/x`
  on that image stops at alembic's DB connection error (name resolution), with no uv
  download, resolve or install lines. Inside the image, `alembic`, `uvicorn` and `python`
  resolve to `/app/.venv/bin/`, and `pytest` is not installed (so `--no-dev` works).
- Lockfile: `git ls-files backend/uv.lock` lists it. `git check-ignore backend/uv.lock`
  prints nothing. `cd backend && uv lock --check` passes (129 packages). There is no
  `.dockerignore` that would drop it, and `pyproject.toml` has no private index.
- `make -n test`: runs `npm run lint` → `tsc -b` → backend unit → frontend unit →
  integration → e2e, in that order.
- Action runtimes, checked again with
  `gh api repos/<owner>/<repo>/contents/action.yml?ref=<tag>`: every `uses:` in
  `ci.yml` (checkout@v7, setup-uv@v10.3.3, setup-node@v7, upload-artifact@v7,
  setup-buildx@v4, login@v4, metadata@v6, build-push@v7) declares `node24`.

## Against the spec
- [x] **`runs-on` only `ubuntu-24.04`**: met. All 4 jobs (`ci.yml:13,46,108,153`).
- [x] **No qemu/arm64 in `ci.yml`**: met. `grep -n -i "qemu\|arm64\|provenance"` finds nothing.
- [~] **No action on Node 20; no deprecation warning on `main`**: first half met (the
  `gh api` check above). That the CI run shows no warning is **user to verify** on the
  first `main` run's Actions page.
- [~] **CI on `main` is green, both images pushed**: **user to verify** on the first
  `main` run. Round 1's blocker is gone: the lockfile is committed, and an image built
  from a clean `git archive HEAD` works (above). Every gate CI runs passes locally.
- [~] **ghcr.io has `sha-<short sha>` + `latest` for both images**: the config is right
  (`type=ref,event=branch` + `type=sha` in both metadata steps, `:latest` kept,
  `ci.yml:136-139,181-184`). **User to verify** on ghcr.io after that run.
- [x] **No `uv run` in `backend/entrypoint.sh` / `backend/Dockerfile`**: met. The grep
  finds nothing.
- [x] **`make test` runs lint typecheck unit integration e2e in order, and passes**: met.
  Order from `make -n test`. Every stage passed when I ran it (above).
- [x] **`CLAUDE.md` has an `E2E self-contained:` line with date and reason**: met
  (`CLAUDE.md:59`). Verified by reading in round 1. Nothing in that area has changed since.
- [~] **On the mini-PC `chatbot_api` is `healthy` within a minute; login, open a
  conversation, send a message**: **user to verify** after deploy. Supporting evidence:
  the image starts with no network (above), and in `make e2e` it reached `healthy` and
  all 13 specs passed.

## Blueprint
- §7 (start without `uv run`, migrations on start): holds. `entrypoint.sh` runs
  `alembic upgrade head` from the venv on `PATH`, then `exec "$@"`.
- §8 (`make test` = lint typecheck unit integration e2e): holds. Lint and typecheck are
  frontend-only for now, as the spec says.
- §12 (amd64 only): holds.
- Hexagonal / ORM / UoW / route error rules / canonical files / Italian UI: this change
  does not touch them (no application code changed). It adds no migrations, env vars or
  secrets, and changes nothing in `deployment/`.
- Scope: only the files named in the plan and in R1 changed (`ci.yml`, `.gitignore`,
  `CLAUDE.md`, `Makefile`, `backend/Dockerfile`, `backend/entrypoint.sh`,
  `backend/uv.lock`, and the work record). The diff has no weakened tests, no new
  suppressions (`noqa`, `ts-ignore`, `eslint-disable`, `pyright: ignore`), no TODOs and
  no debug code.

## Findings
1. ~~**must-fix**~~ **resolved** (round 1): `backend/uv.lock` was gitignored and not
   committed, so the CI image build would fail at `backend/Dockerfile:10`. Fixed in
   `aaf1f4a`. Verified above: the file is tracked, it is not ignored, it matches
   `pyproject.toml`, and a clean-archive build works.
2. **note**: `.github/workflows/ci.yml:142,190`. Now that `provenance: false` is gone,
   build-push attaches its default provenance attestation. Each image index on ghcr.io
   therefore gets an `unknown/unknown` entry, which `docker pull` on amd64 ignores. The
   plan's task 5 notes mention it. Listed only so it isn't a surprise in the ghcr UI.
3. **note**: `docs/adr/002-pi-native-deployment.md` still talks about arm64. It is a
   historical ADR, already marked superseded, so it is left alone. The docs cleanup is
   a separate backlog item.
4. **note**: the CI `test` job runs backend unit + integration before the frontend
   lint/typecheck/vitest, while `make test` runs lint and typecheck first. Both run
   every gate, as plan task 3 asks ("after the backend tests").

## Verdict
**ready to ship once confirmed**: to confirm at ship:
1. The first CI run on `main` is green (test, browser-e2e, build-backend,
   build-frontend), and its run page shows no Node 20 deprecation warning.
2. ghcr.io has `chatbot-api` and `chatbot-frontend` tagged `sha-<short sha>` for that
   commit, plus `latest`.
3. After deploy, `docker ps` on the mini-PC shows `chatbot_api` as `healthy` within a
   minute of start, and in the app you can log in, open an existing conversation and
   send a message.

Items 1–3 confirmed by user, 2026-11-19 (after the push).

---
Shipped: merge of work/001-ci-container-fixes · Date: 2026-11-19
