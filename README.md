# NetPulse

Real-time SDN network monitoring platform: streaming telemetry, network KPIs, anomaly detection and alerting.

[![CI](https://github.com/wpilares/netpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/wpilares/netpulse/actions/workflows/ci.yml)
![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB)
![TypeScript](https://img.shields.io/badge/typescript-strict-3178C6)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

NetPulse emulates a software-defined network with Mininet, controls it with an OS-Ken OpenFlow controller, collects per-port statistics, stores them in TimescaleDB, derives KPIs from the counters and streams them to a React dashboard over REST and WebSockets.

![NetPulse dashboard: network summary cards (throughput, max utilization, drop and error rates, switches, ports, counter resets), a tree topology of three switches and four hosts with links colored by utilization, and per-port receive and transmit throughput charts for the selected switch](docs/images/dashboard.png)

> **Status: v0.3, KPIs and live dashboard.** The emulated network carries scheduled iperf3 traffic on 10 Mbit/s links, the API computes throughput, packet rate, drop and error rates and utilization per port, streams them every 5 s over `/ws/telemetry`, and the dashboard draws the discovered topology and live port charts. Next is v0.4, anomaly detection and alerting ([roadmap](#roadmap)).

## What the dashboard shows

| Panel | Source | Content |
| --- | --- | --- |
| Header badges | `GET /health`, socket state, `alerts` frames | API and database reachability, API version, live/reconnecting status and last frame time, open alert count (critical when any critical alert is open, warning when any alert is open, positive otherwise) |
| Network summary | `kpis` frames | Inbound and outbound throughput, max utilization, drop rate, error rate, switches, physical ports, counter resets |
| Alerts | `GET /api/v1/alerts`, `alerts` frames | Open alerts newest first with severity, switch and port, metric, observed and expected values, z-score and opening time; an acknowledge button per alert (`POST /api/v1/alerts/{id}/ack`, applied optimistically and rolled back on failure); a toggle that loads the last 50 resolved alerts on demand |
| Topology | `GET /api/v1/topology` | Switches and hosts as discovered by LLDP; links recolored on every frame by the busiest direction's utilization (idle, low under 30 %, medium under 70 %, high under 90 %, saturated) |
| Switch ports | `kpis` frames | Per-port utilization, drop and error rates, packet rates and a receive/transmit throughput chart over the last 120 frames (about ten minutes) |

Charts and the topology graph are hand-rolled SVG with no chart library. The first frame comes from `GET /api/v1/kpis/summary` and the first alert list from `GET /api/v1/alerts`; after that the client follows the WebSocket (the first `alerts` frame after every connect carries all open alerts, later ones only the changed rows, which the client upserts by id), reconnects with exponential backoff (1 s doubling to 30 s plus jitter) and pings every 15 s to keep proxies from idling the socket out. Host labels are the switch port names facing them (`s2-eth2`), because the controller learns ports from LLDP but never sees Mininet host names.

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
    api -- "GET /topology" --> controller
    web["web<br/>React + nginx"] -- "/health, /api/v1" --> api
    web -- "/ws/telemetry" --> api
```

Data flows left to right. The controller requests `OFPPortStatsRequest` from every connected switch on a fixed interval, keeps the latest sample per switch in memory and discovers inter-switch links with LLDP. The collector polls the controller's REST endpoint, validates the payload against the shared `netpulse-core` models and writes the whole cycle to TimescaleDB in one batch. A one-shot `migrate` service applies the schema before the collector and API start. The API serves stored series and KPIs over REST, proxies the topology from the controller and pushes live KPIs to the dashboard over a WebSocket.

| Component | Path | Stack | Responsibility |
| --- | --- | --- | --- |
| Core | `packages/core` | pydantic 2, pydantic-settings | Shared typed telemetry models, KPI computation and settings base |
| Network | `network` | Mininet, Open vSwitch, iperf3 | Emulated tree topology on shaped links, scheduled traffic between hosts |
| Controller | `services/controller` | OS-Ken 4 (Python 3.13) | Tracks switches, installs forwarding, discovers links with LLDP, polls port stats, serves stats and topology over REST |
| Collector | `services/collector` | asyncio, httpx2, psycopg 3 | Polls the controller, validates samples, writes them idempotently with retry and backoff, scores every port against its EWMA baseline and persists alerts |
| API | `services/api` | FastAPI, httpx2, psycopg 3, uvicorn | `/health`, port statistics, KPIs, topology and service info under `/api/v1`, `/ws/telemetry` WebSocket |
| Web | `web` | Bun, Vite, React 19, TypeScript, Vitest, Biome | Live dashboard: KPI summary cards, topology graph, per-port throughput charts, reconnecting WebSocket client |
| Database | `db/migrations` | TimescaleDB 2.30 on PostgreSQL 18, dbmate | Hypertable, continuous aggregate and policies as versioned SQL |

Design decisions are recorded as ADRs in [`docs/adr`](docs/adr); [ADR 0007](docs/adr/0007-kpi-computation.md) covers the KPIs.

## Run it locally

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

Within a few seconds the controller reports 3 switches and 4 directed links, `GET /api/v1/topology` returns 7 nodes and 6 edges, and the KPI summary counts 8 physical ports. With traffic generation on, the 10 Mbit/s links reach `max_utilization` 1.0 during iperf3 rounds and the summary throughput peaks around 46 Mbit/s across the network.

### Ports and settings

If 3000, 8000 or 8080 are taken on your machine, override the published ports (`.env` or the shell):

```sh
WEB_PORT=3100 API_PORT=8101 CONTROLLER_REST_PORT=8180 docker compose up --build
```

| Variable | Default | Effect |
| --- | --- | --- |
| `WEB_PORT`, `API_PORT`, `CONTROLLER_REST_PORT` | `3000`, `8000`, `8080` | Published host ports for the dashboard, API and controller REST |
| `COLLECTOR_POLL_INTERVAL_SECONDS` | `5` | Collector poll period; Compose reuses it as `NETPULSE_API_LIVE_INTERVAL_SECONDS` for the WebSocket |
| `COLLECTOR_REPOSITORY` | `timescale` | `log` only logs each cycle without a database |
| `COLLECTOR_ALERT_WEBHOOK_URL` | unset | When set, the collector POSTs every alert event to this URL as JSON and keeps the URL out of its logs; unset only logs them |
| `NETPULSE_API_LINK_CAPACITY_BPS` | `10000000` | Link capacity used for utilization by the API and the collector; unset makes utilization `null` |
| `NETWORK_LINK_BANDWIDTH_MBPS` | `10` | `TCLink` bandwidth of every emulated link; keep it equal to the API capacity |
| `NETWORK_TRAFFIC_ENABLED` | `true` | `false` leaves the network idle after the initial `pingAll` |
| `NETWORK_FAULT_ENABLED` | `true` | `false` turns scheduled fault injection off |
| `NETWORK_FAULT_PERIOD_SECONDS`, `NETWORK_FAULT_DURATION_SECONDS` | `90`, `30` | Time between faults and how long each one lasts |
| `NETWORK_FAULT_LOSS_PERCENT` | `20` | Packet loss applied by `loss` faults, 1 to 100 |
| `NETWORK_OVS_DATAPATH` | `user` | `kernel` on a Linux host with the `openvswitch` module loaded, for better throughput |
| `NETWORK_TREE_DEPTH`, `NETWORK_TREE_FANOUT` | `2`, `2` | Shape of the Mininet tree topology |

### The emulated network

The `network` container runs Mininet and Open vSwitch, which need Linux network namespaces, so it runs **privileged**. On Linux it uses the host kernel directly; on macOS and Windows it runs inside Docker Desktop's Linux VM. The default userspace datapath needs no kernel module, but it forwards packets whose checksums the kernel left for hardware offload to compute, so hosts would drop every TCP segment with `InCsumErrors`; the network disables TX checksum offload (`ethtool -K <intf> tx off`) on every host and switch interface right after the switches start.

Every Mininet link is a `TCLink` shaped to `NETWORK_LINK_BANDWIDTH_MBPS`. After the initial `pingAll`, the network starts an `iperf3` server on every host and schedules UDP flows between host pairs: each round pairs the hosts round-robin so every host talks to every other one over time, each flow sends at a rate that drifts deterministically between `NETPULSE_NETWORK_TRAFFIC_MIN_MBPS` and `NETPULSE_NETWORK_TRAFFIC_MAX_MBPS` (1 to 8 Mbit/s by default) for `NETPULSE_NETWORK_TRAFFIC_DURATION_SECONDS` (10 s), and a new round starts every `NETPULSE_NETWORK_TRAFFIC_ROUND_SECONDS` (15 s). UDP keeps the requested rate even when a link is saturated, so drops show up in the port counters instead of TCP backing off. `NETPULSE_NETWORK_TRAFFIC_SEED` changes the schedule.

**Fault injection.** So the anomaly detector has something to find, the network also injects one fault every `NETPULSE_NETWORK_FAULT_PERIOD_SECONDS` (90 s, which leaves the baselines time to warm up) and clears it after `NETPULSE_NETWORK_FAULT_DURATION_SECONDS` (30 s). Faults alternate between `loss`, which adds `NETPULSE_NETWORK_FAULT_LOSS_PERCENT` (20 %) `netem` packet loss on both ends of a link while keeping its bandwidth shaping, and `link down`, which takes both interfaces of a link down. The schedule is deterministic (`NETPULSE_NETWORK_FAULT_SEED`): it visits every host-facing link first, then the switch-to-switch links, and starts over. Traffic rounds keep their own cadence during a fault, so a lossy link shows as drops and a downed link as a throughput collapse on the affected ports. The container logs `*** Fault: ...` and `*** Fault cleared`, clears any active fault on shutdown, and `NETWORK_FAULT_ENABLED=false` disables injection.

The full stack, including the privileged network container, has been verified with Docker Desktop on macOS (Apple silicon).

## How KPIs are computed

Counters are stored cumulative, exactly as OpenFlow reports them; every rate is derived in `netpulse_core.kpi` from two consecutive samples, so history, latest values and the live feed share one tested function ([ADR 0007](docs/adr/0007-kpi-computation.md)).

| KPI | Formula | Notes |
| --- | --- | --- |
| `rx_bps`, `tx_bps` | `8 * Δbytes / Δt` | `Δt` comes from the switch's `duration_sec` when both samples have it, from collection timestamps otherwise |
| `rx_pps`, `tx_pps` | `Δpackets / Δt` | |
| `drop_rate`, `error_rate` | `Δdropped / Δpackets`, `Δerrors / Δpackets` | Over rx and tx together |
| `utilization` | `max(rx_bps, tx_bps) / NETPULSE_API_LINK_CAPACITY_BPS` | Configured capacity, not OpenFlow port speed; `null` when unset |
| `counter_reset` | any negative difference or `Δt <= 0` | The point keeps `counter_reset: true` and every rate `null` |

| Source | Used by | Granularity |
| --- | --- | --- |
| `port_stats_1m` consecutive buckets | per-port KPI history | one point per minute, the first bucket of a window has no point |
| two newest `port_stats` rows per port | per-switch KPIs, network summary, WebSocket frames | one polling interval (5 s by default) |

A counter the switch reports as unsupported (`2^64 - 1`) is stored as `NULL` and yields `null` for the rates that depend on it. OpenFlow reserved ports such as `LOCAL` (`port_no >= 0xffffff00`) are stored but left out of per-switch KPIs, the summary and live frames, so the port count matches the topology. A port with a single sample has no rate yet and is skipped.

### Data model

Migrations live in [`db/migrations`](db/migrations) and are applied by the `migrate` Compose service ([ADR 0005](docs/adr/0005-dbmate-sql-migrations.md)). Sizing and policy choices are explained in [ADR 0006](docs/adr/0006-retention-compression-aggregates.md).

| Relation | Kind | Key | Contents | Retention |
| --- | --- | --- | --- | --- |
| `port_stats` | hypertable, 1-day chunks, compressed after 1 day | `(dpid, port_no, time)` | One row per port per poll: cumulative rx/tx packets, bytes, dropped, errors and `duration_sec` | 7 days |
| `port_stats_1m` | continuous aggregate, refreshed every minute, real-time | `(dpid, port_no, bucket)` | Last counter values in each 1-minute bucket and the number of `samples` | 90 days |

Writes are idempotent, so a retried poll cycle never duplicates rows.

## API

All REST routes live under `/api/v1`; interactive docs are at `/docs`. Invalid parameters return `422`; `503` means the database (or, for topology, the controller) is not configured or unreachable.

| Method and path | Returns | Parameters |
| --- | --- | --- |
| `GET /info` | Service name and version | |
| `GET /switches/{dpid}/ports/{port_no}/stats` | Stored counters, oldest first | `from`, `to` (ISO 8601 with time zone, `from` before `to`); `resolution` `raw` (default, up to 24 h) or `1m` (up to 7 days); `limit` 1 to 10000 (default 1000) |
| `GET /switches/{dpid}/ports/{port_no}/kpis` | KPI history from 1-minute buckets, `{"dpid", "port_no", "points": [...]}` | `from`, `to` (up to 7 days); `limit` (default 1000) bounds the number of points |
| `GET /switches/{dpid}/kpis` | Latest KPIs of every physical port of one switch, `{"dpid", "generated_at", "ports": [...]}` | |
| `GET /kpis/summary` | `{"generated_at", "summary": {...}, "switches": [...]}`: the network summary (`ports`, `switches`, `rx_bps`, `tx_bps`, `drop_rate`, `error_rate`, `max_utilization`, `counter_resets`) plus the latest KPIs of every switch | |
| `GET /topology` | Nodes and edges of the discovered graph | |
| `GET /alerts` | `{"generated_at", "alerts": [...]}`: alerts raised by the collector, newest `opened_at` first | `status` `open` (default), `resolved` or `all`; `limit` 1 to 500 (default 100) |
| `POST /alerts/{id}/ack` | The acknowledged alert; `404` when the id is unknown | Sets `acknowledged_at` once and keeps the first timestamp on repeated calls |
| `GET /health` (no prefix) | API status and database reachability | |

Every KPI point carries `dpid`, `port_no`, `computed_at`, `interval_seconds`, `rx_bps`, `tx_bps`, `rx_pps`, `tx_pps`, `drop_rate`, `error_rate`, `utilization` and `counter_reset`; rates are `null` when they cannot be computed.

Every alert carries `id`, `dpid`, `port_no`, `metric` (`rx_bps`, `tx_bps`, `drop_rate` or `error_rate`), `severity` (`warning` or `critical`), `status` (`open` or `resolved`), `opened_at`, `last_seen_at`, `resolved_at`, `acknowledged_at`, `value`, `expected`, `zscore` and `updated_at`; acknowledging is a user mark and does not resolve the alert. Open alerts survive collector restarts: the collector reloads them at startup, a still-active anomaly keeps refreshing the same row, and a vanished one is resolved after the policy window.

### Port statistics example

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

A range with no data returns an empty `points` list.

### Topology

The controller runs OS-Ken's `switches` app with link observation on: every switch gets an LLDP-to-controller flow at priority `0xFFFF` above the `NORMAL` forwarding rule, so neighbours discover each other through LLDP, and `GET /topology` on the controller lists switches, their ports and the directed links OS-Ken reports. The API reads that payload over HTTP (`NETPULSE_API_CONTROLLER_URL`, `NETPULSE_API_CONTROLLER_TIMEOUT_SECONDS`, 2 s) and turns it into nodes and edges:

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

Each inter-switch link appears once with the lower `dpid` as `source`. A switch port that is neither reserved nor the end of a link is assumed to face a host and becomes a `host` node attached to its switch.

### WebSocket `/ws/telemetry`

The socket pushes the same network summary as `GET /api/v1/kpis/summary`, plus per-switch port KPIs, without polling. The API computes a frame every `NETPULSE_API_LIVE_INTERVAL_SECONDS` (5 s by default; Compose ties it to the collector poll interval) from the two newest samples per port inside the lookback window (`NETPULSE_API_LIVE_LOOKBACK_SECONDS`, 120 s).

| Frame | Direction | When |
| --- | --- | --- |
| `{"type": "hello", "version": "..."}` | server to client | Once, right after the connection opens |
| `{"type": "kpis", "generated_at": "...", "summary": {...}, "switches": [{"dpid", "generated_at", "ports": [...]}]}` | server to client | Every cycle in which at least one port has two samples in the window |
| `{"type": "heartbeat", "at": "..."}` | server to client | Every cycle in which the window holds no sample pairs yet |
| `{"type": "store_unavailable", "at": "..."}` | server to client | Every cycle in which the database cannot be queried |
| `{"type": "alerts", "generated_at": "...", "alerts": [...]}` | server to client | After the KPI frame of the first cycle, with every open alert; afterwards only in cycles where at least one alert was opened, refreshed, resolved or acknowledged since the previous frame, carrying just those alerts |
| `{"type": "ping"}` / `{"type": "pong"}` | client to server / reply | Keepalive; any other client message gets `{"type": "error", "reason": "unsupported message"}` |

Frames queue per client (`NETPULSE_API_LIVE_QUEUE_SIZE`, 16); a client that falls behind is disconnected with close code `1013` and reason `slow consumer`.

## Development

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

Run a single service against the Compose stack:

```sh
NETPULSE_API_DATABASE_URL=postgresql://netpulse:change-me@localhost:5432/netpulse uv run netpulse-api
cd web && bun run dev    # proxies /health, /api and /ws to http://localhost:8000
```

Quality bar: no code comments, no `any` or untyped Python, zero lint and type errors, tests first for logic, Conventional Commits with one work unit per commit. See [`CLAUDE.md`](CLAUDE.md) for the full list of gates.

### Project structure

```
.
├── packages/core/           netpulse-core: telemetry models, KPI computation and settings base
├── services/
│   ├── api/                 FastAPI app, health probe, stats, KPI, live and topology ports and adapters, routers, Dockerfile
│   ├── collector/           polling loop, controller client, repository port, TimescaleDB adapter, Dockerfile
│   └── controller/          standalone uv project: OS-Ken app, stats store, link discovery, REST, Dockerfile
├── network/                 Mininet topology spec, runner, traffic scheduler, entrypoint, Dockerfile
├── web/                     React dashboard, nginx config, Dockerfile
├── db/migrations/           dbmate SQL migrations: hypertable, continuous aggregate, policies
├── docs/adr/                architecture decision records
├── docs/images/             dashboard screenshot
├── .github/workflows/ci.yml lint, type check, test and build on every push and PR
├── docker-compose.yml       full stack with health checks
├── pyproject.toml           uv workspace and shared ruff, mypy, pytest config
└── Makefile                 developer entry points
```

## Roadmap

| Version | Scope | State |
| --- | --- | --- |
| v0.1 | Base structure: every layer scaffolded, wired, typed, tested and containerized | Merged |
| v0.2 | Telemetry ingestion: SQL migrations, `port_stats` hypertable with compression and retention, 1-minute continuous aggregate, idempotent batched writes with retry, stats query endpoint, integration tests in CI | Merged |
| v0.3 | KPIs and live dashboard: KPI domain with counter-reset handling, history, switch and summary endpoints, WebSocket feed with heartbeat and backpressure, LLDP topology, live React dashboard, shaped links with scheduled iperf3 traffic | Delivered on `feat/network-kpis`, PR pending |
| v0.4 | Anomaly detection and alerting: baseline models over KPI series, alert rules, notifications, fault injection in the network | Next |

Known follow-ups from v0.3: read `curr_speed` from OpenFlow port descriptions instead of a configured capacity, and show Mininet host names in the topology once the controller can learn them.

## License

[MIT](LICENSE) © 2026 Willber Pilares
