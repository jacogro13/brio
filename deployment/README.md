# Chatbot — Deployment (mini-PC-native stack)

This compose file runs the app **on the mini-PC**: the `chatbot-api` backend and the
`chatbot-frontend` SPA, both pulling `ghcr.io/<GHCR_OWNER>/chatbot-*`. The api
connects to `shared_postgres` on the same mini-PC (managed by `Infrastructure/`) and
reaches the **LLM running as a host service on the mini-PC** (`Infrastructure/llm`)
on the pinned `shared_network` gateway `10.100.0.1:8080` (llama.cpp) — the same
shared LLM used by Registro_Spese, Pasti, and Blibiobot.

Listing and reading existing conversations work with the LLM off (they only
touch Postgres); only sending a new message needs the LLM, and it errors
cleanly when it is down.

## Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | `api` + `frontend`, pulling `ghcr.io/<GHCR_OWNER>/chatbot-*` |
| `deploy.sh` | Copies the compose file + `.env.example` to the remote host |
| `.env.example` | Template: DB creds, `LLM_MODEL`, optional `IMAGE_TAG`, optional host port |

## Prerequisites on the mini-PC

- `Infrastructure/` running so `shared_postgres` and `shared_network` exist. The
  `chatbot_app` role + `chatbot` database are created by `Infrastructure/init/01-init.sh`;
  alembic creates the tables on container start.
- The **host LLM** running (`Infrastructure/llm`, llama.cpp on the mini-PC) so it
  is reachable at `10.100.0.1:8080`. It already serves the other apps — no
  Chatbot-specific change is needed.

## First-time setup

**1. Deploy files to the remote host** (or use the Deployer app):
```bash
./deploy.sh <user> <host> <path>
# e.g. ./deploy.sh <user> <server> ~/Apps/Chatbot
```

**2. SSH into the mini-PC and fill in `.env`:**
```bash
ssh <user>@<host>
cd <path>
nano .env   # DB values from Infrastructure/deployment/.env; set LLM_MODEL
```

**3. Start the stack:**
```bash
docker compose up -d
```

The frontend is served on port **120** (`FRONTEND_HOST_PORT`). The api is reached
from the frontend's nginx via the internal `chatbot_network`.

## Schema migrations

Migrations run automatically on container start: `backend/entrypoint.sh` runs
`alembic upgrade head` before the app boots (baked into the image), against
`shared_postgres`. Matches every other `Apps/` stack — no manual step.

## Updating

```bash
ssh <user>@<host>
cd <path> && docker compose pull && docker compose up -d
```

## Pinning a specific image version

Set `IMAGE_TAG` in `.env` (e.g. `IMAGE_TAG=sha-abc1234`), then `docker compose up -d`.

## Teardown

```bash
docker compose down
```
