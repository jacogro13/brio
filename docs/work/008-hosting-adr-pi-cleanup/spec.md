# 008 — Hosting ADR and Pi cleanup

App: Chatbot · Created: 2026-11-25
Status: shipped
<!-- draft → approved → building → in review → shipped | abandoned -->

## Why
Chatbot is going to be published as the factory's example app, but some live files
still describe a setup that no longer exists. `frontend/Dockerfile:1-4` justifies
`--platform=$BUILDPLATFORM` with QEMU/arm64, although CI has been amd64-only since 001.
ADR-002 ("Pi-native deployment with the LLM on the laptop") is the only hosting
decision on record, and it is framed around the Pi and the laptop bridge. Only its
status line says it was superseded. A reader of the public repo can't tell how
Chatbot is actually hosted. From the backlog item *Pi leftovers in live files*.

## What changes
- **`frontend/Dockerfile`**: the build stage is a plain `FROM node:20-alpine AS build`.
  The `--platform=$BUILDPLATFORM` flag and its QEMU/arm64 comment are gone. The built
  image is unchanged.
- **New `docs/adr/008-…md`** (ADR format as 001–007, Status: Accepted). It supersedes
  ADR-002 and records how Chatbot is hosted today:
  - runs on the mini-PC (`deployment/docker-compose.yml`, `chatbot-api` +
    `chatbot-frontend`);
  - LLM: llama.cpp as a host service on the mini-PC (`Infrastructure/llm`), reached on
    the pinned `shared_network` gateway `http://10.100.0.1:8080` (`LLM_BASE_URL`);
  - database: `shared_postgres` as the least-privilege role `chatbot_app`, not the
    `postgres` superuser; alembic runs at container start;
  - attachments: the shared Garage (links ADR-004);
  - images: amd64-only, tagged `sha-<short sha>`, branch name and `latest`;
  - deploys: Deployer + docker-autoupdate (BLUEPRINT §7);
  - fleet-wide rules are linked to BLUEPRINT §7 / §7b / §12, not decided again here;
  - **known gap**: when the LLM is down, the stream just ends without an error in the
    UI (backlog item *A stopped LLM cuts the stream off*). This is stated as a gap,
    not as working behaviour.
- **ADR-002**: only the `Status` line changes, to "Superseded by ADR-008 (2026-11-25)".
  The title, body and the 2026-06-22 update note stay word for word.
- **`docs/adr/README.md`**: the ADR-002 row shows "Superseded by 008", and a new row
  is added for 008.

## Out of scope
- CI changes, the Node-20 Actions bump, and the *stopped LLM* items (including the
  stale "errors cleanly" comments in `deployment/`).
- Old work records (`docs/work/001–007`): not edited.
- ADR-002's title and body: they stay as history.
- The laptop as the **dev machine** (`docs/MOBILE_UX_PLAN.md:141`, `<laptop-LAN-IP>`)
  and llama.cpp's "tools bridge" in `docs/IMPROVEMENT_PLAN.md`: neither describes
  hosting, so both stay.
- Lockfiles (`uv.lock`, `package-lock.json`), whose `arm64`/`aarch64` wheel names
  aren't prose.

## Acceptance checks
- [ ] This grep prints nothing (it skips work records, ADR-002, lockfiles, the
      generated schema, the two dev-machine/tools-bridge lines above, the
      `driver: bridge` lines in compose and the "pi" test fixture):
      `cd Chatbot && git ls-files | grep -v -E '^docs/work/|^docs/adr/002-|uv.lock|package-lock|schema.d.ts|test_orm_types' | xargs grep -n -i -E '\bpi\b|raspberry|laptop|arm64|aarch64|qemu|buildplatform|multi-arch|laptop.bridge' | grep -v -E 'driver: bridge|laptop-LAN-IP'`
- [ ] `docs/adr/008-*.md` exists and covers each bullet under *What changes* (host,
      LLM via gateway, `chatbot_app` role, Garage, amd64 images, deploys, links to
      BLUEPRINT §7/§7b/§12). It states the stopped-LLM behaviour as a known gap, and
      it does not claim the UI shows an error.
- [ ] `git diff docs/adr/002-pi-native-deployment.md` shows only the `Status` line
      changed, naming ADR-008.
- [ ] `docs/adr/README.md` lists 008 and marks 002 as superseded by 008. All links in
      the index and in ADR-008 resolve to existing files.
- [ ] `git diff --stat` touches no file under `docs/work/001`–`007` and no CI workflow.
- [ ] The frontend image still builds: `docker compose build frontend` (or the CI
      build job) succeeds, and `make test` stays green.

## Open questions

---
Approved by: Jacopo Grotti · Date: 2026-11-25
