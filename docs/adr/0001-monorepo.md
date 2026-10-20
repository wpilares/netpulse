# ADR 0001: Single monorepo with a uv workspace and a Bun web app

- Status: Accepted
- Date: 2026-10-20

## Context

NetPulse spans five runtimes: a Mininet network, an OS-Ken SDN controller, a telemetry collector, an HTTP/WebSocket API and a React dashboard. The collector and the API share the same telemetry vocabulary (datapath ids, port counters, timestamps). Changes such as adding a counter usually touch the controller payload, the shared model, the API and the dashboard at once, and a single person maintains the whole system.

## Decision

Keep everything in one repository:

- A **uv workspace** at the root groups the Python packages that share an interpreter (3.14) and a lockfile: `packages/core`, `services/api`, `services/collector` and `network`. Tooling (ruff, mypy strict, pytest) is configured once in the root `pyproject.toml`.
- `packages/core` owns the typed domain models. Services depend on it, never on each other.
- `services/controller` is a **standalone uv project** with its own lockfile and Python 3.13 (see ADR 0002). It talks to the rest of the system only through its REST contract, so no Python import crosses that boundary.
- `web/` is a **Bun** project with its own lockfile, Biome, TypeScript and Vitest.
- One `docker-compose.yml`, one `Makefile` and one CI workflow cover every component.

## Consequences

- One pull request can change a contract end to end, and CI checks every side of it.
- Shared tooling configuration avoids drift between services.
- Two Python lockfiles exist; CI and `make install` sync both explicitly.
- Docker builds for workspace services use the repository root as build context, so `.dockerignore` must keep that context small.
