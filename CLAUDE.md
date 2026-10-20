# CLAUDE.md

Project rules for AI-assisted work in NetPulse.

## Code rules

- **No code comments.** Applies to Python, TypeScript, YAML, Dockerfiles, Makefile and config. Names and structure carry intent; if something needs a comment, refactor it.
- **No `any` and no untyped code.** TypeScript forbids `any` in every form; use precise types, generics or `unknown` with narrowing. Python is fully annotated and passes `mypy --strict`; `Any` is allowed only at an untyped third-party boundary (OS-Ken, Mininet) and stays inside that adapter module.
- **Zero lint and type errors.** Fix issues properly; never silence them with ignore comments.
- **Test first for logic.** For behavior with a clear expected outcome, write the failing pytest or Vitest test, watch it fail, then implement.
- **Respect boundaries.** Domain models live in `packages/core`; services depend on them, never on each other. Framework and driver code (FastAPI, httpx2, psycopg, OS-Ken, Mininet) stays at the edges behind small typed interfaces.
- **Conventional Commits** (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `ci:`), one reviewable work unit per commit.
- **English** for code, docs and commit messages.

## Quality gates

Run `make ci`, or individually from the repository root:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run --directory services/controller mypy
uv run --directory services/controller pytest
uv run --directory network --python 3.13 --isolated --no-project --with pytest pytest
```

From `web/`:

```sh
bun run lint
bun run typecheck
bun run test
bun run build
```

Compose must stay valid: `docker compose --env-file .env.example config --quiet`.
