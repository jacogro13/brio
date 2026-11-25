# ADR-008: Mini-PC hosting

**Status**: Accepted — supersedes [ADR-002](002-pi-native-deployment.md)  
**Date**: 2026-11-25

## Context

ADR-002 recorded Chatbot's first production setup, which no longer exists. Today
every app in the fleet runs on one always-on x86_64 mini-PC, which also runs the
shared LLM. The fleet-wide rules for this live in the Apps blueprint:
BLUEPRINT §7 (`deployment/`, update flow, migrations), §7b (shared production
infrastructure) and §12 (CI/CD). This ADR records what they mean for Chatbot. It
does not decide them again.

## Decision

Chatbot runs on the **mini-PC**, from published images only
(`deployment/docker-compose.yml`): the `chatbot-api` backend and the
`chatbot-frontend` SPA (nginx, host port `120`), pulled from
`ghcr.io/<GHCR_OWNER>/chatbot-{api,frontend}:${IMAGE_TAG:-latest}`.

- **LLM**: llama.cpp runs as a host systemd service on the mini-PC
  (`Infrastructure/llm`), shared with the other apps. The api reaches it on the
  pinned `shared_network` gateway, `http://10.100.0.1:8080` (`LLM_BASE_URL`, with
  `LLM_MODEL` matching the served model). The app only knows an OpenAI-compatible
  URL (ADR-001), so this is configuration, not code.
- **Database**: the shared `shared_postgres` on `shared_network`, managed by
  `Infrastructure/` (BLUEPRINT §7b). The api connects as its own least-privilege
  role **`chatbot_app`**, which owns only the `chatbot` database, never as the
  `postgres` superuser. `Infrastructure/init/01-init.sh` creates the role and
  database; alembic creates the tables on every container start
  (`backend/entrypoint.sh`, BLUEPRINT §7).
- **Attachments**: the shared Garage (`shared_garage`, reached via its `garage`
  alias at `http://garage:3900`) with its own `chatbot` bucket. See ADR-004.
- **Images**: CI builds and pushes **`linux/amd64` only**, tagged `sha-<short sha>`,
  the branch name and `latest` (BLUEPRINT §12). Pinning `IMAGE_TAG` to a `sha-…`
  tag rolls back.
- **Deploys**: a push to `main` is a production deploy. CI publishes the images,
  and the `docker-autoupdate` timer on the mini-PC pulls them and restarts the
  stack within minutes. The Deployer app (or `deployment/deploy.sh`) copies changed
  `deployment/` files to the mini-PC and drives manual pulls and restarts
  (BLUEPRINT §7).

## Consequences

- Chatbot is a plain fleet app: shared Postgres, shared Garage and the shared host
  LLM, with nothing specific to Chatbot in `Infrastructure/` beyond its DB role,
  its Garage bucket and its systemd stack unit.
- Listing and reading conversations only touch Postgres, so they keep working
  when the LLM is stopped.
- **Known gap**: when the LLM is down, sending a message doesn't produce an error
  in the UI. The stream just ends with no `error` event. This is tracked as the
  *stopped LLM* item in the factory backlog, not solved here.
