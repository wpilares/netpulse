# NetPulse

Real-time SDN network monitoring platform: streaming telemetry, network KPIs, anomaly detection and alerting.

[![CI](https://github.com/wpilares/netpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/wpilares/netpulse/actions/workflows/ci.yml)
![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB)
![TypeScript](https://img.shields.io/badge/typescript-strict-3178C6)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

NetPulse emulates a software-defined network with Mininet, controls it with an OS-Ken OpenFlow controller, collects per-port statistics, stores them in TimescaleDB and serves them to a React dashboard over REST and WebSockets.

> **Status: v0.1, base structure.** Every component builds, runs and is tested end to end: the network forwards traffic, the controller exposes live port counters and the collector polls them. Persistence, KPIs and live charts are on the [roadmap](#roadmap).

## Architecture

```mermaid
flowchart LR
    subgraph network["network (Mininet + Open vSwitch)"]
        S1[s1] --- S2[s2]
        S1 --- S3[s3]
        S2 --- H1[h1] & H2[h2]
        S3 --- H3[h3] & H4[h4]
    end

    network -- "OpenFlow 1.3 :6653" --> controller["controller<br/>OS-Ken app"]
    collector["collector<br/>async poller"] -- "GET /stats/ports" --> controller
    collector -. "v0.2: write samples" .-> db[("TimescaleDB")]
    api["api<br/>FastAPI"] -- "SQL" --> db
    web["web<br/>React + nginx"] -- "/health, /api/v1" --> api
    web -- "/ws/telemetry" --> api
```

Data flows left to right. The controller requests `OFPPortStatsRequest` from every connected switch on a fixed interval and keeps the latest sample per switch in memory. The collector polls the controller's REST endpoint, validates the payload against the shared `netpulse-core` models and hands it to a repository. The API reads from TimescaleDB and pushes updates to the dashboard over a WebSocket.

## Components

| Component | Path | Stack | Responsibility |
| --- | --- | --- | --- |
| Core | `packages/core` | pydantic 2, pydantic-settings | Shared typed telemetry models and settings base |
| Network | `network` | Mininet, Open vSwitch | Emulated tree topology connected to the remote controller |
| Controller | `services/controller` | OS-Ken 4 (Python 3.13) | Tracks switches, installs forwarding, polls port stats, serves them over REST |
| Collector | `services/collector` | asyncio, httpx2 | Polls the controller, validates samples, stores them through a repository port |
| API | `services/api` | FastAPI, psycopg 3, uvicorn | `/health`, versioned REST under `/api/v1`, `/ws/telemetry` WebSocket |
| Web | `web` | Bun, Vite, React 19, TypeScript, Vitest, Biome | Dashboard shell with live API health status |
| Database | `docker-compose.yml` | TimescaleDB 2.30 on PostgreSQL 18 | Time-series storage for telemetry |

Design decisions are recorded as ADRs in [`docs/adr`](docs/adr).

## Quickstart

Requirements: Docker with Compose v2 or later.

```sh
cp .env.example .env
docker compose up --build
```

| URL | Service |
| --- | --- |
| http://localhost:3000 | Dashboard |
| http://localhost:8000/docs | API OpenAPI docs |
| http://localhost:8000/health | API health, including database reachability |
| http://localhost:8080/stats/ports | Raw port statistics from the controller |

The `network` container runs Mininet and Open vSwitch, which need Linux network namespaces, so it runs **privileged**. On Linux it uses the host kernel directly. On macOS and Windows it runs inside Docker Desktop's Linux VM. By default Open vSwitch uses its userspace datapath (`NETWORK_OVS_DATAPATH=user`), which needs no kernel module; on a Linux host with the `openvswitch` module loaded you can switch to `kernel` for better throughput.

The full stack, including the privileged network container, has been verified with Docker Desktop on macOS (Apple silicon): all hosts reach each other and the collector receives counters from every switch.

## Local development

Requirements: [uv](https://docs.astral.sh/uv/) 0.13+, [Bun](https://bun.sh) 1.2+, Docker. uv downloads Python 3.14 (workspace) and 3.13 (controller) as needed.

```sh
make install     # sync both Python environments and web dependencies
make lint        # ruff check, ruff format --check, biome
make typecheck   # mypy --strict (workspace and controller), tsc
make test        # pytest (workspace, network on 3.13, controller), vitest
make format      # apply ruff and biome fixes
make ci          # everything CI runs, plus web build and compose validation
make up / down   # start or stop the Docker Compose stack
```

Run a single service against the Compose stack:

```sh
NETPULSE_API_DATABASE_URL=postgresql://netpulse:change-me@localhost:5432/netpulse uv run netpulse-api
cd web && bun run dev    # proxies /health, /api and /ws to http://localhost:8000
```

Quality bar: no code comments, no `any` or untyped Python, zero lint and type errors, tests first for logic. See [`CLAUDE.md`](CLAUDE.md).

## Project structure

```
.
├── packages/core/           netpulse-core: telemetry models and settings base
├── services/
│   ├── api/                 FastAPI app, health probe, routers, Dockerfile
│   ├── collector/           polling loop, controller client, repository port, Dockerfile
│   └── controller/          standalone uv project: OS-Ken app, stats store, REST, Dockerfile
├── network/                 Mininet topology spec, runner, entrypoint, Dockerfile
├── web/                     React dashboard, nginx config, Dockerfile
├── docs/adr/                architecture decision records
├── .github/workflows/ci.yml lint, type check, test and build on every push and PR
├── docker-compose.yml       full stack with health checks
├── pyproject.toml           uv workspace and shared ruff, mypy, pytest config
└── Makefile                 developer entry points
```

## Roadmap

- [x] **v0.1 Base structure**: every layer scaffolded, wired, typed, tested and containerized.
- [ ] **v0.2 Telemetry ingestion**: hypertable schema and migrations, TimescaleDB repository in the collector, flow statistics.
- [ ] **v0.3 KPIs and live dashboard**: throughput, utilization, drop and error rates as continuous aggregates, streamed over WebSocket into live charts.
- [ ] **v0.4 Anomaly detection and alerting**: baseline models over KPI series, alert rules, notifications.

## License

[MIT](LICENSE) © 2026 Willber Pilares
