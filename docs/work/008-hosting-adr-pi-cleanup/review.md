# 008 — Review

Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md) · Reviewed: 2026-11-25

## Automated checks
Run by the reviewer on `work/008-hosting-adr-pi-cleanup` (clean tree, after `bfafb68`,
`757bb88`, `2a1a3cb`).
- `make lint typecheck`: pass. ruff format/check clean (124 files), eslint clean,
  pyright 0 errors, `tsc -b` clean.
- `make unit`: pass. Backend 158 passed, frontend 67 passed (13 files).
- `make -C shared drift APP=Chatbot` (from `Apps/`): pass. Every canonical copy is `ok current`.
- `make integration`: pass. 29 passed.
- `make e2e` (E2E self-contained: yes, per `Chatbot/CLAUDE.md`): pass. 17 passed. The stack rebuilt `chatbot_e2e-frontend` from the edited Dockerfile (`[frontend build 1/6] FROM docker.io/library/node:20-alpine`), and `down -v` removed every container, volume and network afterwards. The e2e
  stack rebuilds the frontend image from the edited Dockerfile, so this also covers
  "the frontend image still builds".

## Against the spec
- [~] **Acceptance grep prints nothing.** *Not met as written; user to confirm.* Run
  literally, the spec's command prints two lines:
  - `docs/adr/008-mini-pc-hosting.md:3` (`supersedes [ADR-002](002-pi-native-deployment.md)`)
  - `docs/adr/README.md:6` (the 002 row: file name `002-pi-native-deployment.md` and
    title "Pi-native deployment with the LLM on the laptop").

  The spec itself requires both. It asks for a supersedes link to ADR-002, an index row
  for 002, links that resolve, and ADR-002's title kept word for word. The grep's
  exclusions forgot those references. No hit is a live description of Pi/laptop
  hosting. With those two lines set aside, the grep prints nothing (reviewer ran it).
  This is a defect in the check, not in the change, but the check as approved does fail,
  so the user has to accept the two lines (see Findings, note 1).
- [x] **ADR-008 exists and covers every bullet.** Met. `docs/adr/008-mini-pc-hosting.md`
  has: mini-PC host with `chatbot-api` + `chatbot-frontend` from
  `deployment/docker-compose.yml`, llama.cpp host service (`Infrastructure/llm`) via
  `http://10.100.0.1:8080` / `LLM_BASE_URL`, role `chatbot_app` (not the superuser) and
  alembic at container start, shared Garage with a link to ADR-004, amd64-only images
  tagged `sha-…` / branch / `latest`, Deployer + docker-autoupdate, links to BLUEPRINT
  §7 / §7b / §12. The stopped-LLM behaviour is listed under **Known gap**, and the ADR
  says the UI shows *no* error. The reviewer checked each fact against the source:
  `deployment/docker-compose.yml`, `deployment/.env.example:10` (`DB_USER=chatbot_app`),
  `.github/workflows/ci.yml:146-155,191-200` (`type=ref,event=branch`, `type=sha`,
  `platforms: linux/amd64`, `:latest`), `Infrastructure/init/01-init.sh:63`,
  `Infrastructure/llm/llama.service`, `Infrastructure/deployment/systemd/chatbot-stack.service`,
  `deployment/deploy.sh`.
- [x] **ADR-002: only the Status line changes, naming ADR-008.** Met.
  `git diff main...work/008-hosting-adr-pi-cleanup -- docs/adr/002-pi-native-deployment.md`
  is one line, `**Status**: Superseded by [ADR-008](008-mini-pc-hosting.md) (2026-11-25)`.
  The title, body and the 2026-06-22 update note are unchanged.
- [x] **Index lists 008 and marks 002 superseded by 008; all links resolve.** Met.
  `docs/adr/README.md` has both rows. The reviewer resolved every relative link in
  `README.md` and `008-mini-pc-hosting.md` (001–008, all exist).
- [x] **No file under `docs/work/001`–`007` and no CI workflow touched.** Met.
  `git diff --stat main...work/008-hosting-adr-pi-cleanup` touches only `docs/adr/002-…`,
  `docs/adr/008-…` (new), `docs/adr/README.md`, `frontend/Dockerfile` and this work record.
- [x] **Frontend image still builds, `make test` green.** Met. The e2e run above rebuilt the frontend image from the new Dockerfile and 17 e2e tests passed. Together with. lint, typecheck,
  unit and integration pass (above).

## Blueprint
- Hexagonal layers, ORM mapping, Unit of Work, routes/components error rules, Italian UI:
  not touched. No code under `backend/src` or `frontend/src` changes.
- Canonical copies: none touched. Drift check is clean.
- §12 (amd64-only CI): the change fits it. `--platform=$BUILDPLATFORM` did nothing on
  an amd64 runner building `linux/amd64`, so the image is the same.
- §7 / §7b: ADR-008 points to them and doesn't decide them again, as the spec asked.
- No migrations, no new environment variables, nothing secret committed. Nothing to do
  on the mini-PC.

## Local worker
- Task 1 · done by local (unaided) · 1 run · 20.1 s · 3400 tokens in / 149 out.
  The worker's raw diff (`Apps/factory/worker/logs/Chatbot-008-task1.diff`) matches the
  committed `frontend/Dockerfile` change line for line. Claude changed nothing before
  committing. The edit matches the brief exactly: the three comment lines are gone, the
  line is now `FROM node:20-alpine AS build`, and the rest of the file is unchanged.
- 1 of 1 local tasks finished unaided. The worker got nothing wrong.

## Findings
1. **note**: the spec's acceptance grep (`spec.md`, first acceptance check) contradicts
   the spec's own requirements. The required ADR-002 link in
   `docs/adr/008-mini-pc-hosting.md:3` and the required 002 row in
   `docs/adr/README.md:6` both match `\bpi\b`/`laptop`. The change is right and the check
   is wrong. Nothing to fix in the code. The user only has to accept that these two lines
   are expected. Commit `2a1a3cb` already says so. (Factory lesson added to the backlog:
   dry-run acceptance greps against the intended end state at `/spec` time.)
2. **note**: `deployment/docker-compose.yml:17-18` still says "When llama is down,
   sending a message errors cleanly", which contradicts ADR-008's known gap. The spec
   leaves this out of scope on purpose, and it is already in the backlog with the
   *stopped LLM* item (`Apps/factory/BACKLOG.md`, Chatbot section). No action here.

No must-fix or should-fix findings.

## Verdict
**ready to ship once confirmed**

To confirm before `/release`: the spec's acceptance grep prints exactly two lines,
`docs/adr/008-mini-pc-hosting.md:3` and `docs/adr/README.md:6`. Both are references to
ADR-002's file name and title that the spec itself requires (finding 1). Accept them as
expected. Nothing else is left: every automated check passed when the reviewer ran it
(e2e included), and every other acceptance check is met.

Confirmed by user, 2026-11-25: the two grep lines are expected.

---
Shipped: merge of work/008-hosting-adr-pi-cleanup · Date: 2026-11-25
