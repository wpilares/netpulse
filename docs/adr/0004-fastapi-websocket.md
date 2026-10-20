# ADR 0004: FastAPI with WebSocket streaming for the API

- Status: Accepted
- Date: 2026-10-20

## Context

The dashboard needs two kinds of access: request/response queries (health, inventory, history) and a live stream of telemetry updates with low latency. The backend is Python, shares typed models with the collector and must stay strictly typed.

## Decision

- Use **FastAPI** with pydantic models for REST under a versioned prefix (`/api/v1`) and a liveness/readiness endpoint at `/health`.
- Use a **WebSocket** endpoint (`/ws/telemetry`) for live updates. It sends a typed `hello` message on connect and answers `ping` with `pong`; telemetry frames arrive in v0.3.
- Build routers through small factory functions that receive their dependencies (for example the database probe). This keeps handlers typed without reading untyped application state and makes tests replace dependencies directly.
- Serve the dashboard through nginx, which proxies `/health`, `/api/` and `/ws/` to the API so the browser uses a single origin.

## Consequences

- OpenAPI documentation is generated from the typed handlers.
- WebSockets keep the dashboard simple: no polling loop for live data, one connection per tab.
- Horizontal scaling of WebSocket fan-out will need a broker (for example PostgreSQL `LISTEN/NOTIFY` or Redis) once more than one API replica runs.
