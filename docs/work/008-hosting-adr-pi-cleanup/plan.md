# 008 — Plan

Spec: [spec.md](spec.md) (approved 2026-11-25)

## Approach
The change is three small edits. (1) The frontend Dockerfile loses its
`--platform=$BUILDPLATFORM` flag and the QEMU/arm64 comment. CI builds `linux/amd64` on
an amd64 runner (BLUEPRINT §12), so the flag does nothing and the image stays the same.
(2) A new **ADR-008 "Mini-PC hosting"** supersedes ADR-002. It records today's setup:
mini-PC host, llama.cpp on the host via the `shared_network` gateway, the `chatbot_app`
role, the shared Garage (ADR-004), amd64-only images with `sha-…` tags, and deploys via
Deployer + docker-autoupdate. It links BLUEPRINT §7 / §7b / §12 instead of deciding
those rules again, and lists the stopped-LLM behaviour as a known gap. ADR-002 gets only
a new Status line, and the ADR index is updated. (3) The full gate: the spec's grep plus
`make test`. Its e2e step runs `compose --profile app up --build`, which rebuilds the
frontend image from the edited Dockerfile.

**1 of 3 tasks is `local`** (task 1: one file, one exact edit, a grep check that fails
today). Task 2 is the ADR work and task 3 is the full gate. The factory rules keep both
with Claude.

## Tasks

| # | Task | Files | Check | Worker | Status |
|---|------|-------|-------|--------|--------|
| 1 | Drop the QEMU/arm64 comment (lines 1–3) and `--platform=$BUILDPLATFORM` from the build stage, leaving `FROM node:20-alpine AS build` | `frontend/Dockerfile` | `! grep -q -i -E 'buildplatform\|qemu\|arm64\|--platform' frontend/Dockerfile && grep -qx 'FROM node:20-alpine AS build' frontend/Dockerfile && grep -qx 'FROM nginx:stable-alpine' frontend/Dockerfile` | local | done (local) |
| 2 | Write `docs/adr/008-mini-pc-hosting.md` (format as 001–007, Status: Accepted, Date 2026-11-25, "Supersedes ADR-002"), covering every bullet in the spec's *What changes*. Set ADR-002's `**Status**` line to `Superseded by [ADR-008](008-mini-pc-hosting.md) (2026-11-25)`, changing nothing else in it. In `docs/adr/README.md`, set the 002 row's status to `Superseded by 008` and add the 008 row | `docs/adr/008-mini-pc-hosting.md` (new), `docs/adr/002-pi-native-deployment.md`, `docs/adr/README.md` | `git diff docs/adr/002-pi-native-deployment.md` = Status line only; every relative link in the index and in ADR-008 points to an existing file; ADR-008 does not claim the UI shows an error when the LLM is down | claude | done |
| 3 | Full gate: run the spec's acceptance grep, check `git diff --stat` touches no `docs/work/001–007` file and no workflow, then run `make test` (lint → typecheck → unit → integration → e2e, which rebuilds the frontend image) | — | the grep prints nothing; `make test` is green | claude | done |

## Worker briefs

### Task 1
In `frontend/Dockerfile`, delete the three comment lines at the top of the file (they
explain building on BUILDPLATFORM to avoid QEMU/arm64 emulation) and change the line
`FROM --platform=$BUILDPLATFORM node:20-alpine AS build` to exactly
`FROM node:20-alpine AS build`. The file then starts with that `FROM` line. Keep every
other line unchanged and in the same order: the `WORKDIR`, `COPY`, `RUN npm install`,
`RUN npm run build` lines of the build stage, and the whole second stage
(`FROM nginx:stable-alpine`, the two `COPY` lines, `EXPOSE 80`, `CMD`). Don't add a
new comment. No other file changes.

## Risks
- **Deploy:** the push to `main` rebuilds and redeploys both images through
  docker-autoupdate. The frontend image comes out the same: CI targets `linux/amd64` on
  an amd64 runner, so dropping `--platform=$BUILDPLATFORM` doesn't change the base
  image or the bundle. If the frontend build somehow fails, CI stops before pushing and
  production keeps the current image.
- **No migrations, no new env vars, nothing to do on the mini-PC, no other app or
  `Infrastructure/` affected.** The rest is docs.
- **ADR accuracy:** ADR-008 states facts about production (gateway address, role name,
  tags). Task 2 takes them from `deployment/docker-compose.yml`,
  `deployment/.env.example`, `.github/workflows/ci.yml` and BLUEPRINT §7/§12, not from
  memory, so the published example app doesn't describe a setup that differs from the
  real one.

---
Approved by: Jacopo Grotti · Date: 2026-11-25
