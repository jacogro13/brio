.PHONY: env drift types migration test test-backend lint typecheck unit unit-backend unit-frontend integration e2e clean backend frontend cli sync db

E2E_PROJECT := chatbot_e2e

env:
	@if [ -f .env ]; then echo ".env already exists, delete it first to regenerate."; exit 1; fi
	@cp .env.example .env
	@sed -i "s|changeme|$$(head -c 16 /dev/urandom | xxd -p | tr -d '\n')|g" .env
	@sed -i "s|^GARAGE_ACCESS_KEY_ID=.*|GARAGE_ACCESS_KEY_ID=GK$$(openssl rand -hex 12)|" .env
	@sed -i "s|^GARAGE_SECRET_ACCESS_KEY=.*|GARAGE_SECRET_ACCESS_KEY=$$(openssl rand -hex 32)|" .env
	@sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$$(openssl rand -hex 32)|" .env
	@echo ".env generated."

# Start the dev Postgres + Garage (+ one-shot garage-init) and wait for them.
# Idempotent: a no-op if they're already up. garage-init provisions the bucket
# and exits.
db:
	docker compose up -d --wait db garage garage-init

migration: sync db
	set -a && . ./.env && set +a && \
	cd backend && uv run alembic upgrade head

test: lint typecheck unit integration e2e

# Regenerate frontend/src/api/schema.d.ts from the backend's OpenAPI, offline:
# no server, no database (v2, F1). Importing the app needs no env vars (D4), so
# .env is optional (CI has none). Commit the result with the backend change.
types: sync frontend/node_modules
	@if [ -f .env ]; then set -a && . ./.env && set +a; fi && tmp=$$(mktemp --suffix=.json) && \
	(cd backend && uv run python -c "import json, sys; from chatbot.entrypoints.main import app; json.dump(app.openapi(), sys.stdout)") > $$tmp && \
	(cd frontend && npx openapi-typescript $$tmp -o src/api/schema.d.ts) && rm -f $$tmp

# Canonical shared/ copies: fails on unlabelled edits (BLUEPRINT §15).
drift:
	$(MAKE) -C ../shared drift APP=Chatbot

lint: sync frontend/node_modules
	cd backend && uv run ruff format --check . && uv run ruff check .
	cd frontend && npm run lint

typecheck: sync frontend/node_modules
	cd backend && uv run pyright
	cd frontend && npx tsc -b

test-backend: lint typecheck unit-backend integration

sync:
	cd backend && uv sync

unit: unit-backend unit-frontend

unit-backend: sync
	cd backend && uv run pytest tests/unit

unit-frontend: frontend/node_modules
	cd frontend && npm test

integration: sync
	cd backend && uv run pytest tests/integration

e2e:
	docker compose -p $(E2E_PROJECT) -f docker-compose.yml -f docker-compose.e2e.yml --profile app up -d --build --wait
	@trap 'docker compose -p $(E2E_PROJECT) --profile app down -v' EXIT INT TERM; \
	  ( cd e2e && npm install --silent && npx playwright install chromium >/dev/null && npm test )

clean:
	docker compose down -v
	-docker compose -p $(E2E_PROJECT) down -v

backend: migration
	set -a && . ./.env && set +a && \
	cd backend && uv run uvicorn chatbot.entrypoints.main:app --reload --port 5004

# Install frontend deps if missing or stale (package.json newer than node_modules).
frontend/node_modules: frontend/package.json
	cd frontend && npm install
	@touch frontend/node_modules

frontend:
	cd frontend && npm run dev

cli: migration
	set -a && . ./.env && set +a && \
	uv run --project=backend chatbot

