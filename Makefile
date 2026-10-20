CONTROLLER := services/controller
WEB := web
ENV_FILE ?= .env
COMPOSE := docker compose --env-file $(ENV_FILE)

.PHONY: install lint format typecheck test test-integration migrate up down ci

install:
	uv sync --all-packages --locked
	uv sync --project $(CONTROLLER) --locked
	cd $(WEB) && bun install --frozen-lockfile

lint:
	uv run ruff check .
	uv run ruff format --check .
	cd $(WEB) && bun run lint

format:
	uv run ruff check --fix .
	uv run ruff format .
	cd $(WEB) && bun run format

typecheck:
	uv run mypy
	uv run --directory $(CONTROLLER) mypy
	cd $(WEB) && bun run typecheck

test:
	uv run pytest
	uv run --directory network --python 3.13 --isolated --no-project --with pytest pytest
	uv run --directory $(CONTROLLER) pytest
	cd $(WEB) && bun run test

test-integration:
	$(COMPOSE) up --detach --wait timescaledb
	$(COMPOSE) run --rm migrate
	set -a && . ./$(ENV_FILE) && set +a && \
	NETPULSE_TEST_DATABASE_URL="postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@localhost:$${POSTGRES_PORT:-5432}/$${POSTGRES_DB}" \
	uv run pytest -m integration

migrate:
	$(COMPOSE) run --rm migrate

up:
	$(COMPOSE) up --build --detach

down:
	$(COMPOSE) down

ci: install lint typecheck test
	cd $(WEB) && bun run build
	docker compose --env-file .env.example config --quiet
