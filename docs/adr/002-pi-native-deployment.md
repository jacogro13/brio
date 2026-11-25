# ADR-002: Pi-native deployment with the LLM on the laptop

**Status**: Superseded by [ADR-008](008-mini-pc-hosting.md) (2026-11-25)  
**Date**: 2026-06-11

> **Update (2026-06-22):** the fleet moved off the Raspberry Pi to a mini-PC, which
> hosts the LLM directly. The "deploy like every other app" decision stands; the
> **laptop bridge is gone**. llama.cpp now runs as a host systemd service on the
> mini-PC (`Infrastructure/llm`), reached by the api on the pinned `shared_network`
> gateway at `http://10.100.0.1:8080`.

## Context

Until now Chatbot ran only on the laptop — CI just tested it, there was no
`deployment/` folder, and it was the one product app in `Apps/` not running on
the always-on Raspberry Pi. We want it deployed like every other app, but the
LLM is too heavy for the Pi: llama.cpp already runs on the laptop and is shared
with Registro_Spese, Pasti, and Blibiobot.

## Decision

Deploy Chatbot **on the Pi** (`deployment/docker-compose.yml`): the
`chatbot-api` backend and the `chatbot-frontend` SPA, pulling
`ghcr.io/<GHCR_OWNER>/chatbot-*` images published by CI.

- The api connects to the shared `shared_postgres` on `shared_network` (managed
  by `Infrastructure/`). The `chatbot` database already exists in
  `Infrastructure/init/init.sql`; alembic creates the tables on container start
  via `backend/entrypoint.sh`. In prod `shared_postgres` exposes only the
  superuser role, so `DB_USER=postgres`.
- The **LLM stays on the laptop**. The api reaches it over the persistent
  `Infrastructure/laptop-bridge` reverse-SSH tunnel on the pinned `shared_network`
  gateway `10.100.0.1:8080` (`LLM_BASE_URL`). The bridge already forwards `:8080`
  for the other apps, so no bridge change was needed.

This required **no application-code change** — `OpenAILikeLLMAdapter` is already
configured by `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` (`dependencies.py`); only
deployment, CI image publishing, and the Deployer/systemd registration were added.

## Consequences

- Listing and reading existing conversations work with the laptop off (they only
  touch Postgres). Only sending a new message needs the laptop LLM; when the
  laptop/tunnel is down the streaming request fails and the UI surfaces the error.
- CI now builds and publishes multi-arch (`amd64`+`arm64`) `chatbot-api` and
  `chatbot-frontend` images to ghcr.io on `main` (`provenance: false` to avoid the
  QEMU SIGILL on ARM cross-build).
- The Pi runs the stack via the `chatbot-stack.service` systemd unit
  (`Infrastructure/deployment/systemd/`); the Deployer app discovers it and
  drives deploys/pulls/restarts like the other apps.
- Same shared-services pattern as Registro_Spese/Pasti (shared Postgres + laptop
  LLM over the bridge); Chatbot is Pasti without Garage.
