CONTROLLER := services/controller
WEB := web

.PHONY: install lint format typecheck test up down ci

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

up:
	docker compose up --build --detach

down:
	docker compose down

ci: install lint typecheck test
	cd $(WEB) && bun run build
	docker compose --env-file .env.example config --quiet
