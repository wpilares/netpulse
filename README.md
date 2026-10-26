# NetPulse

Real-time SDN network monitoring platform: streaming telemetry, network KPIs, anomaly detection and alerting.

[![CI](https://github.com/wpilares/netpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/wpilares/netpulse/actions/workflows/ci.yml)
![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB)
![TypeScript](https://img.shields.io/badge/typescript-strict-3178C6)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

NetPulse emulates a software-defined network with Mininet, controls it with an OS-Ken OpenFlow controller, collects per-port statistics, stores them in TimescaleDB and serves them to a React dashboard over REST and WebSockets.

> **Status: v0.2, telemetry ingestion.** The network forwards traffic, the controller exposes live port counters, the collector stores them in a TimescaleDB hypertable and the API serves them at raw or 1-minute resolution. KPIs and live charts are on the [roadmap](#roadmap).

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
    collector -- "batched INSERT" --> db[("TimescaleDB")]
    migrate["migrate<br/>dbmate"] -- "DDL" --> db
    api["api<br/>FastAPI"] -- "SQL" --> db
    web["web<br/>React + nginx"] -- "/health, /api/v1" --> api
    web -- "/ws/telemetry" --> api
```

Data flows left to right. The controller requests `OFPPortStatsRequest` from every connected switch on a fixed interval and keeps the latest sample per switch in memory. The collector polls the controller's REST endpoint, validates the payload against the shared `netpulse-core` models and writes the whole cycle to TimescaleDB in one batch. A one-shot `migrate` service applies the schema before the collector and API start. The API serves stored series over REST and will push live updates to the dashboard over a WebSocket.

## Components

| Component | Path | Stack | Responsibility |
| --- | --- | --- | --- |
| Core | `packages/core` | pydantic 2, pydantic-settings | Shared typed telemetry models and settings base |
| Network | `network` | Mininet, Open vSwitch | Emulated tree topology connected to the remote controller |
| Controller | `services/controller` | OS-Ken 4 (Python 3.13) | Tracks switches, installs forwarding, discovers links with LLDP, polls port stats, serves stats and topology over REST |
| Collector | `services/collector` | asyncio, httpx2, psycopg 3 | Polls the controller, validates samples, writes them idempotently with retry and backoff |
| API | `services/api` | FastAPI, httpx2, psycopg 3, uvicorn | `/health`, port statistics, KPIs, topology and service info under `/api/v1`, `/ws/telemetry` WebSocket |
| Web | `web` | Bun, Vite, React 19, TypeScript, Vitest, Biome | Live dashboard: KPI summary cards, topology graph, per-port throughput charts, reconnecting WebSocket client |
| Database | `db/migrations` | TimescaleDB 2.30 on PostgreSQL 18, dbmate | Hypertable, continuous aggregate and policies as versioned SQL |

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
| http://localhost:8080/topology | Switches, ports and discovered links from the controller |

## Data model

Migrations live in [`db/migrations`](db/migrations) and are applied by the `migrate` Compose service ([ADR 0005](docs/adr/0005-dbmate-sql-migrations.md)). Sizing and policy choices are explained in [ADR 0006](docs/adr/0006-retention-compression-aggregates.md).

| Relation | Kind | Key | Contents | Retention |
| --- | --- | --- | --- | --- |
| `port_stats` | hypertable, 1-day chunks, compressed after 1 day | `(dpid, port_no, time)` | One row per port per poll: cumulative rx/tx packets, bytes, dropped, errors and `duration_sec` | 7 days |
| `port_stats_1m` | continuous aggregate, refreshed every minute, real-time | `(dpid, port_no, bucket)` | Last counter values in each 1-minute bucket and the number of `samples` | 90 days |

Counters are cumulative, exactly as OpenFlow reports them; KPIs (throughput, packet rate, drop and error rates, utilization) are derived in the core domain from consecutive samples and served under `/api/v1/switches/{dpid}/kpis`, `/api/v1/switches/{dpid}/ports/{port_no}/kpis` and `/api/v1/kpis/summary` ([ADR 0007](docs/adr/0007-kpi-computation.md)). A counter the switch reports as unsupported (`2^64 - 1`) is stored as `NULL`. Writes are idempotent, so a retried poll cycle never duplicates rows.

## Querying port statistics

`GET /api/v1/switches/{dpid}/ports/{port_no}/stats`

| Parameter | Required | Description |
| --- | --- | --- |
| `from`, `to` | yes | ISO 8601 timestamps with a time zone; `from` must be earlier than `to` |
| `resolution` | no | `raw` (default, up to 24 h per request) or `1m` (up to 7 days) |
| `limit` | no | Maximum points, 1 to 10000 (default 1000), oldest first |

```sh
curl -s "http://localhost:8000/api/v1/switches/1/ports/1/stats?from=2026-10-20T12:00:00Z&to=2026-10-20T13:00:00Z&resolution=1m&limit=2"
```

```json
{
  "dpid": 1,
  "port_no": 1,
  "resolution": "1m",
  "points": [
    {"time": "2026-10-20T12:00:00Z", "rx_packets": 14, "tx_packets": 19, "rx_bytes": 1232, "tx_bytes": 1654, "rx_dropped": 0, "tx_dropped": 0, "rx_errors": 0, "tx_errors": 0, "duration_sec": 2, "samples": 12},
    {"time": "2026-10-20T12:01:00Z", "rx_packets": 32, "tx_packets": 41, "rx_bytes": 2736, "tx_bytes": 3458, "rx_dropped": 0, "tx_dropped": 0, "rx_errors": 0, "tx_errors": 0, "duration_sec": 62, "samples": 12}
  ]
}
```

Invalid parameters return `422`; a range with no data returns an empty `points` list; `503` means the database is unreachable or not configured.

### Live telemetry

`/ws/telemetry` pushes the same network summary as `/api/v1/kpis/summary` without polling. After the `{"type": "hello", "version": "..."}` greeting the API sends one frame per cycle (`NETPULSE_API_LIVE_INTERVAL_SECONDS`, 5 s by default; Compose ties it to the collector poll interval):

- `{"type": "kpis", "generated_at": "...", "summary": {...}, "switches": [...]}` when at least one port has two samples inside the lookback window (`NETPULSE_API_LIVE_LOOKBACK_SECONDS`, 120 s).
- `{"type": "heartbeat", "at": "..."}` when the window holds no sample pairs yet.
- `{"type": "store_unavailable", "at": "..."}` when the database cannot be queried.

Clients may send `{"type": "ping"}` and receive `{"type": "pong"}`; any other message gets `{"type": "error", "reason": "unsupported message"}`. Frames queue per client (`NETPULSE_API_LIVE_QUEUE_SIZE`, 16); a client that falls behind is disconnected with close code `1013` and reason `slow consumer`.

### Topology

`GET /api/v1/topology` returns the graph the dashboard draws. The controller runs OS-Ken's `switches` app with link observation on: every switch gets an LLDP-to-controller flow at priority `0xFFFF` above the `NORMAL` forwarding rule, so neighbours discover each other through LLDP, and `GET /topology` on the controller lists switches, their ports and the directed links OS-Ken reports. The API reads that payload over HTTP (`NETPULSE_API_CONTROLLER_URL`, `NETPULSE_API_CONTROLLER_TIMEOUT_SECONDS`, 2 s) and turns it into nodes and edges:

```json
{
  "generated_at": "2026-10-26T09:00:00Z",
  "nodes": [
    {"id": "s:1", "kind": "switch", "dpid": 1, "port_no": null, "label": "s1"},
    {"id": "h:2:1", "kind": "host", "dpid": 2, "port_no": 1, "label": "s2-eth1"}
  ],
  "edges": [
    {"source": "s:1", "target": "s:2", "source_port": 1, "target_port": 3},
    {"source": "s:2", "target": "h:2:1", "source_port": 1, "target_port": null}
  ]
}
```

Each inter-switch link appears once with the lower `dpid` as `source`. A switch port that is neither reserved nor the end of a link is assumed to face a host and becomes a `host` node attached to its switch. `503` means the controller URL is not configured or the controller did not answer.

The `network` container runs Mininet and Open vSwitch, which need Linux network namespaces, so it runs **privileged**. On Linux it uses the host kernel directly. On macOS and Windows it runs inside Docker Desktop's Linux VM. By default Open vSwitch uses its userspace datapath (`NETWORK_OVS_DATAPATH=user`), which needs no kernel module; on a Linux host with the `openvswitch` module loaded you can switch to `kernel` for better throughput.

The full stack, including the privileged network container, has been verified with Docker Desktop on macOS (Apple silicon): all hosts reach each other and the collector receives counters from every switch.

### Traffic generation

Every Mininet link is a `TCLink` shaped to `NETWORK_LINK_BANDWIDTH_MBPS` (10 Mbit/s by default, the same capacity the API uses for utilization). After the initial `pingAll`, the network starts an `iperf3` server on every host and schedules UDP flows between host pairs: each round pairs the hosts round-robin so every host talks to every other one over time, each flow sends at a rate that drifts deterministically between `NETPULSE_NETWORK_TRAFFIC_MIN_MBPS` and `NETPULSE_NETWORK_TRAFFIC_MAX_MBPS` (1 to 8 Mbit/s by default) for `NETPULSE_NETWORK_TRAFFIC_DURATION_SECONDS` (10 s), and a new round starts every `NETPULSE_NETWORK_TRAFFIC_ROUND_SECONDS` (15 s). UDP keeps the requested rate even when a link is saturated, so drops show up in the port counters instead of TCP backing off. Set `NETWORK_TRAFFIC_ENABLED=false` to leave the network idle; `NETPULSE_NETWORK_TRAFFIC_SEED` changes the schedule.

### Dashboard

The web app at http://localhost:3000 paints the first frame from `GET /api/v1/kpis/summary`, then follows `/ws/telemetry`: every `kpis` frame updates the summary cards, recolors the topology links by the busiest direction's utilization (idle, low under 30 %, medium under 70 %, high under 90 %, saturated) and appends a point to each port's ring buffer (120 points, about ten minutes at the default interval). Charts and the topology graph are hand-rolled SVG with no chart library; the connection badge shows the socket state, the reconnect attempt and whether the API reported its store as unavailable. The client reconnects with exponential backoff (1 s doubling to 30 s plus jitter) and pings every 15 s to keep proxies from idling the socket out.

## Local development

Requirements: [uv](https://docs.astral.sh/uv/) 0.13+, [Bun](https://bun.sh) 1.2+, Docker. uv downloads Python 3.14 (workspace) and 3.13 (controller) as needed.

```sh
make install     # sync both Python environments and web dependencies
make lint        # ruff check, ruff format --check, biome
make typecheck   # mypy --strict (workspace and controller), tsc
make test        # pytest (workspace, network on 3.13, controller), vitest
make test-integration  # start TimescaleDB, run migrations, run pytest -m integration
make migrate     # apply pending migrations to the Compose database
make format      # apply ruff and biome fixes
make ci          # everything CI runs, plus web build and compose validation
make up / down   # start or stop the Docker Compose stack
```

Compose-based targets read `.env` by default; pass `ENV_FILE=.env.example` to use the example values. Integration tests are skipped unless `NETPULSE_TEST_DATABASE_URL` points at a TimescaleDB server; each run creates and drops its own temporary database there.

The collector writes to TimescaleDB when `NETPULSE_COLLECTOR_REPOSITORY=timescale` (the Compose default, set through `COLLECTOR_REPOSITORY`). Set it to `log` to only log each cycle without a database.

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
│   ├── api/                 FastAPI app, health probe, stats query port and adapter, routers, Dockerfile
│   ├── collector/           polling loop, controller client, repository port, TimescaleDB adapter, Dockerfile
│   └── controller/          standalone uv project: OS-Ken app, stats store, REST, Dockerfile
├── network/                 Mininet topology spec, runner, entrypoint, Dockerfile
├── web/                     React dashboard, nginx config, Dockerfile
├── db/migrations/           dbmate SQL migrations: hypertable, continuous aggregate, policies
├── docs/adr/                architecture decision records
├── .github/workflows/ci.yml lint, type check, test and build on every push and PR
├── docker-compose.yml       full stack with health checks
├── pyproject.toml           uv workspace and shared ruff, mypy, pytest config
└── Makefile                 developer entry points
```

## Roadmap

- [x] **v0.1 Base structure**: every layer scaffolded, wired, typed, tested and containerized.
- [x] **v0.2 Telemetry ingestion**: SQL migrations, `port_stats` hypertable with compression and retention, 1-minute continuous aggregate, idempotent batched writes with retry in the collector, stats query endpoint, integration tests in CI.
- [ ] **v0.3 KPIs and live dashboard**: throughput, utilization, drop and error rates from the stored counters, flow statistics, streamed over WebSocket into live charts.
- [ ] **v0.4 Anomaly detection and alerting**: baseline models over KPI series, alert rules, notifications.

## License

[MIT](LICENSE) © 2026 Willber Pilares
