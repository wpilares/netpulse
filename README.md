# NetPulse

Real-time SDN network monitoring platform: streaming telemetry, network KPIs, anomaly detection and alerting.

[![CI](https://github.com/wpilares/netpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/wpilares/netpulse/actions/workflows/ci.yml)
![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB)
![TypeScript](https://img.shields.io/badge/typescript-strict-3178C6)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

NetPulse emulates a software-defined network with Mininet, controls it with an OS-Ken OpenFlow controller, collects per-port statistics, stores them in TimescaleDB, derives KPIs from the counters, scores every port against its own baseline, raises alerts and streams KPIs and alerts to a React dashboard over REST and WebSockets. The emulated network injects faults on a schedule so there is always something to detect.

![NetPulse dashboard during a host-down fault: header badge with one open alert, network summary cards, an open critical drop_rate alert on switch 3 port 3 with observed value 1.0, a tree topology of three switches and four hosts labelled by IP address with links colored by utilization, and per-port receive and transmit throughput charts for the selected switch](docs/images/dashboard-alerts.png)

> **Status: v0.4, anomaly detection and alerting.** The collector keeps an EWMA baseline per port and metric, opens, escalates and resolves alerts, the API lists, acknowledges and streams them, the dashboard shows them live, and the network alternates packet-loss and host-down faults every two minutes. Next is v0.5, alert tuning and correlation ([roadmap](#roadmap)).

## What the dashboard shows

| Panel | Source | Content |
| --- | --- | --- |
| Header badges | `GET /health`, socket state, `alerts` frames | API and database reachability, API version, live/reconnecting status and last frame time, open alert count (critical when any critical alert is open, warning when any alert is open, positive otherwise) |
| Network summary | `kpis` frames | Inbound and outbound throughput, max utilization, drop rate, error rate, switches, physical ports, counter resets |
| Alerts | `GET /api/v1/alerts`, `alerts` frames | Open alerts newest first with severity, switch and port, metric, observed and expected values, z-score and opening time; an acknowledge button per alert (`POST /api/v1/alerts/{id}/ack`, applied optimistically and rolled back on failure); a toggle that loads the last 50 resolved alerts on demand |
| Topology | `GET /api/v1/topology` | Switches discovered by LLDP and hosts learned from ARP, labelled by IPv4 address; links recolored on every frame by the busiest direction's utilization (idle, low under 30 %, medium under 70 %, high under 90 %, saturated) |
| Switch ports | `kpis` frames | Per-port utilization, drop and error rates, packet rates and a receive/transmit throughput chart over the last 120 frames (about ten minutes) |

Charts and the topology graph are hand-rolled SVG with no chart library. The first frame comes from `GET /api/v1/kpis/summary` and the first alert list from `GET /api/v1/alerts`; after that the client follows the WebSocket, reconnects with exponential backoff (1 s doubling to 30 s plus jitter) and pings every 15 s to keep proxies from idling the socket out. Host labels fall back to the switch port name facing the host (`s2-eth2`) until the host has sent its first ARP frame.

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
    collector["collector<br/>poller + detector"] -- "GET /stats/ports" --> controller
    collector -- "port_stats, alerts" --> db[("TimescaleDB")]
    collector -. "POST events" .-> webhook["webhook<br/>(optional)"]
    migrate["migrate<br/>dbmate"] -- "DDL" --> db
    api["api<br/>FastAPI"] -- "SQL" --> db
    api -- "GET /topology" --> controller
    web["web<br/>React + nginx"] -- "/health, /api/v1" --> api
    web -- "/ws/telemetry" --> api
```

Data flows left to right. The controller requests `OFPPortStatsRequest` from every connected switch on a fixed interval, keeps the latest sample per switch in memory, discovers inter-switch links with LLDP and hosts from ARP. The collector polls the controller's REST endpoint, validates the payload against the shared `netpulse-core` models, writes the whole cycle to TimescaleDB in one batch, computes the KPIs of the cycle against the previous one, scores them against per-port baselines and persists the resulting alert events in the same database. A one-shot `migrate` service applies the schema before the collector and API start. The API serves stored series, KPIs and alerts over REST, proxies the topology from the controller and pushes live KPIs and alert changes to the dashboard over a WebSocket. The collector and the API never talk to each other: the database is the contract.

| Component | Path | Stack | Responsibility |
| --- | --- | --- | --- |
| Core | `packages/core` | pydantic 2, pydantic-settings | Shared typed telemetry models, KPI computation, anomaly detection, alert lifecycle and settings base |
| Network | `network` | Mininet, Open vSwitch, iperf3 | Emulated tree topology on shaped links, scheduled traffic between hosts, scheduled fault injection |
| Controller | `services/controller` | OS-Ken 4 (Python 3.13) | Tracks switches, installs forwarding, discovers links with LLDP and hosts from ARP, polls port stats, serves stats and topology over REST |
| Collector | `services/collector` | asyncio, httpx2, psycopg 3 | Polls the controller, validates samples, writes them idempotently with retry and backoff, scores every port against its EWMA baseline, persists alerts and notifies a webhook |
| API | `services/api` | FastAPI, httpx2, psycopg 3, uvicorn | `/health`, port statistics, KPIs, topology, alerts and service info under `/api/v1`, `/ws/telemetry` WebSocket |
| Web | `web` | Bun, Vite, React 19, TypeScript, Vitest, Biome | Live dashboard: KPI summary cards, alerts panel with acknowledge, topology graph, per-port throughput charts, reconnecting WebSocket client |
| Database | `db/migrations` | TimescaleDB 2.30 on PostgreSQL 18, dbmate | Hypertable, continuous aggregate, policies and the `alerts` table as versioned SQL |

### Design decisions

Recorded as ADRs in [`docs/adr`](docs/adr):

| ADR | Decision |
| --- | --- |
| [0001](docs/adr/0001-monorepo.md) to [0004](docs/adr/0004-fastapi-websocket.md) | Monorepo, OS-Ken over Ryu, TimescaleDB, FastAPI with a WebSocket feed |
| [0005](docs/adr/0005-dbmate-sql-migrations.md), [0006](docs/adr/0006-retention-compression-aggregates.md) | dbmate SQL migrations; chunking, compression, retention and the 1-minute aggregate |
| [0007](docs/adr/0007-kpi-computation.md) | KPIs computed in core from consecutive samples, counter resets as `null` rates |
| [0008](docs/adr/0008-anomaly-detection-and-alerting.md) | EWMA baselines with z-scores and floors, alert lifecycle, `alerts` table, cursor streaming, webhook notifier, fault injection and why `loss` and `host_down` leave different marks |

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
| http://localhost:8080/topology | Switches, ports, hosts and discovered links from the controller |

### What to expect, and when

| After start | What happens |
| --- | --- |
| a few seconds | The controller reports 3 switches and 4 directed links; `GET /api/v1/topology` returns 7 nodes and 6 edges, hosts labelled `10.0.0.1` to `10.0.0.4` once they have sent ARP; the KPI summary counts 8 physical ports |
| 15 s and every 15 s | An iperf3 round starts; during rounds the 10 Mbit/s links reach `max_utilization` 1.0 and the summary throughput peaks around 46 Mbit/s |
| about 60 s | Baselines finish warming up (12 samples at 5 s); the first alerts, usually `rx_bps`/`tx_bps` on the ports the iperf3 bursts cross, appear about 70 s after the collector started |
| 90 s, then every 120 s | A fault starts and lasts 30 s; the network logs `*** Fault: ...` and `*** Fault cleared`, and `loss` and `host_down` alternate across the links |
| during a `host_down` fault | A `critical` `drop_rate` alert with value `1.0` opens on the switch port facing the downed host within one poll, and resolves about a minute after the fault clears |

Throughput alerts with the default thresholds also fire on the iperf3 bursts themselves, because every round is a step in the rate; the baseline absorbs the step within a few samples and the alerts resolve on their own. That is expected noise in the demo; see [anomaly detection](#anomaly-detection-and-alerts) for the knobs.

### Ports and settings

If 3000, 8000 or 8080 are taken on your machine, override the published ports (`.env` or the shell):

```sh
WEB_PORT=3100 API_PORT=8101 CONTROLLER_REST_PORT=8180 docker compose up --build
```

Variables read by Compose (`.env`):

| Variable | Default | Effect |
| --- | --- | --- |
| `WEB_PORT`, `API_PORT`, `CONTROLLER_REST_PORT` | `3000`, `8000`, `8080` | Published host ports for the dashboard, API and controller REST |
| `COLLECTOR_POLL_INTERVAL_SECONDS` | `5` | Collector poll period; Compose reuses it as `NETPULSE_API_LIVE_INTERVAL_SECONDS` for the WebSocket |
| `COLLECTOR_REPOSITORY` | `timescale` | `log` only logs each cycle without a database |
| `COLLECTOR_ALERT_WEBHOOK_URL` | unset | When set, the collector POSTs each cycle's `opened`, `escalated` and `resolved` alert events to this URL as JSON (the `default` route) and keeps the URL out of its logs; unset and without routes it only logs them |
| `COLLECTOR_ALERT_ROUTES` | unset | JSON list of extra alert routes filtered by severity, metric and event kind, see [Alert routing](#alert-routing-and-retention) |
| `COLLECTOR_ALERT_RETENTION_DAYS` | `7` | Resolved alerts older than this are deleted by the collector once an hour |
| `NETPULSE_API_LINK_CAPACITY_BPS` | `10000000` | Link capacity used for utilization by the API and the collector; unset makes utilization `null` |
| `NETPULSE_API_LINK_CAPACITY_SOURCE` | `configured` | `openflow` makes the API use each port's OpenFlow `curr_speed` for utilization, falling back to the configured capacity for ports without one; on Mininet OVS reports the veth speed (10 Gbit/s), so leave it `configured` |
| `NETWORK_LINK_BANDWIDTH_MBPS` | `10` | `TCLink` bandwidth of every emulated link; keep it equal to the API capacity |
| `NETWORK_TRAFFIC_ENABLED` | `true` | `false` leaves the network idle after the initial `pingAll` |
| `NETWORK_FAULT_ENABLED` | `true` | `false` turns scheduled fault injection off |
| `NETWORK_FAULT_PERIOD_SECONDS`, `NETWORK_FAULT_DURATION_SECONDS` | `90`, `30` | Gap between the end of a fault and the start of the next one, and how long each fault lasts; the duration must be shorter than the period |
| `NETWORK_FAULT_LOSS_PERCENT` | `20` | Packet loss applied by `loss` faults, 1 to 100 |
| `NETWORK_OVS_DATAPATH` | `user` | `kernel` on a Linux host with the `openvswitch` module loaded, for better throughput |
| `NETWORK_TREE_DEPTH`, `NETWORK_TREE_FANOUT` | `2`, `2` | Shape of the Mininet tree topology |

Detection and alert policy are collector settings. Compose maps each one from a `.env` variable without the `NETPULSE_` prefix (for example `COLLECTOR_DETECTION_WARNING_Z=4`); when running the collector directly, export the full names:

| Variable | Default | Effect |
| --- | --- | --- |
| `NETPULSE_COLLECTOR_DETECTION_ENABLED` | `true` | `false` writes samples without scoring them |
| `NETPULSE_COLLECTOR_DETECTION_ALPHA` | `0.2` | EWMA weight of the newest sample, in `(0, 1]` |
| `NETPULSE_COLLECTOR_DETECTION_WARMUP_SAMPLES` | `12` | Samples a baseline needs before it scores (one minute at 5 s polling) |
| `NETPULSE_COLLECTOR_DETECTION_WARNING_Z`, `NETPULSE_COLLECTOR_DETECTION_CRITICAL_Z` | `3`, `5` | z-score thresholds; critical must exceed warning |
| `NETPULSE_COLLECTOR_DETECTION_MIN_BPS_DELTA` | `1000000` | Throughput change below this many bit/s never signals, whatever its z-score (1 Mbit/s; the core default is 100 kbit/s) |
| `NETPULSE_COLLECTOR_DETECTION_MIN_SIGMA_BPS`, `NETPULSE_COLLECTOR_DETECTION_MIN_SIGMA_RATE` | `10000`, `0.005` | Sigma floors for throughput and rate z-scores, so a flat series cannot produce infinite scores |
| `NETPULSE_COLLECTOR_DETECTION_DROP_RATE_FLOOR`, `NETPULSE_COLLECTOR_DETECTION_ERROR_RATE_FLOOR` | `0.02`, `0` | Absolute guards: a drop rate at or above the floor, or an error rate above it, signals at least warning regardless of the baseline |
| `NETPULSE_COLLECTOR_ALERT_RESOLVE_AFTER_SECONDS` | `60` | An open alert with no signal for this long resolves |
| `NETPULSE_COLLECTOR_ALERT_COOLDOWN_SECONDS` | `120` | Signals inside this window after a resolution are suppressed instead of reopening |
| `NETPULSE_COLLECTOR_ALERT_OPEN_AFTER_SIGNALS` | `3` | Consecutive signals a key needs before its alert opens (15 s at 5 s polling); a gap resets the count |
| `NETPULSE_COLLECTOR_ALERT_WEBHOOK_URL` | unset | Same as `COLLECTOR_ALERT_WEBHOOK_URL` above, which Compose maps onto it |
| `NETPULSE_COLLECTOR_ALERT_ROUTES` | unset | Same as `COLLECTOR_ALERT_ROUTES` above; malformed JSON stops the collector at startup |
| `NETPULSE_COLLECTOR_ALERT_RETENTION_DAYS`, `NETPULSE_COLLECTOR_ALERT_RETENTION_EVERY_CYCLES` | `7`, `720` | Age after which resolved alerts are deleted, and how many poll cycles pass between purges (one hour at 5 s polling) |

The network's traffic and fault schedules use the same prefix convention (`NETPULSE_NETWORK_TRAFFIC_*`, `NETPULSE_NETWORK_FAULT_*`, including the `_SEED` variables that change the deterministic schedules); Compose maps the `NETWORK_*` variables above onto them.

### The emulated network

The `network` container runs Mininet and Open vSwitch, which need Linux network namespaces, so it runs **privileged**. On Linux it uses the host kernel directly; on macOS and Windows it runs inside Docker Desktop's Linux VM. The default userspace datapath needs no kernel module, but it forwards packets whose checksums the kernel left for hardware offload to compute, so hosts would drop every TCP segment with `InCsumErrors`; the network disables TX checksum offload (`ethtool -K <intf> tx off`) on every host and switch interface right after the switches start.

**Traffic.** Every Mininet link is a `TCLink` shaped to `NETWORK_LINK_BANDWIDTH_MBPS`. After the initial `pingAll`, the network starts an `iperf3` server on every host and schedules UDP flows between host pairs: each round pairs the hosts round-robin so every host talks to every other one over time, each flow sends at a rate that drifts deterministically between `NETPULSE_NETWORK_TRAFFIC_MIN_MBPS` and `NETPULSE_NETWORK_TRAFFIC_MAX_MBPS` (1 to 8 Mbit/s by default) for `NETPULSE_NETWORK_TRAFFIC_DURATION_SECONDS` (10 s), and a new round starts every `NETPULSE_NETWORK_TRAFFIC_ROUND_SECONDS` (15 s). UDP keeps the requested rate even when a link is saturated, so drops show up in the port counters instead of TCP backing off. The network runs without static ARP entries so hosts really resolve each other and the controller can learn them.

**Fault injection.** So the detector has something to find, the network injects one fault at a time: the first one 90 s after start, each lasting 30 s, with a 90 s gap before the next (`NETWORK_FAULT_PERIOD_SECONDS`, `NETWORK_FAULT_DURATION_SECONDS`), so faults repeat every 120 s of wall clock and the baselines recover in between. The schedule is deterministic (`NETPULSE_NETWORK_FAULT_SEED`): it visits every host-facing link first, then the switch-to-switch links, and starts over, alternating two kinds. Traffic rounds keep their own cadence during a fault.

| Fault | What the network does | What the counters show |
| --- | --- | --- |
| `loss` | Adds `NETWORK_FAULT_LOSS_PERCENT` (20 %) `netem` packet loss on both ends of the link, keeping its bandwidth shaping | Nothing in the drop counters: `netem` discards packets inside the queue discipline, after Open vSwitch has counted them as transmitted. The receiving side's throughput deviates, so it appears as `rx_bps`/`tx_bps` alerts |
| `host_down` | Takes the host-side interface of a host link down; the switch port stays up and LLDP keeps the topology intact. Another host (a sibling behind the same switch when there is one) pins the downed host's MAC as a permanent neighbour entry and floods it with `ping -f` for the fault duration, then forgets the entry | The Linux veth driver counts every frame sent towards the downed peer in the switch port's `tx_dropped`; in the smoke run `s3-eth3` went from 0 to 2715 dropped frames in 30 s and `drop_rate` reached `1.0`, so a `critical` alert opened within 4 s of the fault |

Switch-to-switch links only ever get `loss`, since a host must stay behind a `host_down` fault. The container logs `*** Fault: ...`, `*** Probe: ...` and `*** Fault cleared`, clears any active fault on shutdown, and `NETWORK_FAULT_ENABLED=false` disables injection.

The full stack, including the privileged network container, has been verified with Docker Desktop on macOS (Apple silicon).

## How KPIs are computed

Counters are stored cumulative, exactly as OpenFlow reports them; every rate is derived in `netpulse_core.kpi` from two consecutive samples, so history, latest values, the live feed and the detector share one tested function ([ADR 0007](docs/adr/0007-kpi-computation.md)).

| KPI | Formula | Notes |
| --- | --- | --- |
| `rx_bps`, `tx_bps` | `8 * Δbytes / Δt` | `Δt` comes from the switch's `duration_sec` when both samples have it, from collection timestamps otherwise |
| `rx_pps`, `tx_pps` | `Δpackets / Δt` | |
| `drop_rate`, `error_rate` | `Δdropped / (Δpackets + Δdropped)`, `Δerrors / (Δpackets + Δerrors)` | Over rx and tx together; the denominator is the frames the port attempted, so a port that only drops reports `1.0` instead of `null` |
| `utilization` | `max(rx_bps, tx_bps) / capacity` | Capacity is `NETPULSE_API_LINK_CAPACITY_BPS` by default; with `NETPULSE_API_LINK_CAPACITY_SOURCE=openflow` the switch and summary endpoints and the WebSocket feed use the port's `curr_speed_bps` from the topology (cached for 30 s) when the switch reports one and the configured value otherwise; the history endpoint and the collector always use the configured value; `null` when no capacity applies |
| `counter_reset` | any negative difference or `Δt <= 0` | The point keeps `counter_reset: true` and every rate `null` |

| Source | Used by | Granularity |
| --- | --- | --- |
| `port_stats_1m` consecutive buckets | per-port KPI history | one point per minute, the first bucket of a window has no point |
| two newest `port_stats` rows per port | per-switch KPIs, network summary, WebSocket frames | one polling interval (5 s by default) |
| the previous and current poll in collector memory | anomaly detection | one polling interval |

A counter the switch reports as unsupported (`2^64 - 1`) is stored as `NULL` and yields `null` for the rates that depend on it. OpenFlow reserved ports such as `LOCAL` (`port_no >= 0xffffff00`) are stored but left out of per-switch KPIs, the summary, live frames and detection, so the port count matches the topology. A port with a single sample has no rate yet and is skipped.

## Anomaly detection and alerts

Detection runs in the collector on every poll and is pure code in `netpulse_core.anomaly` and `netpulse_core.alerts` ([ADR 0008](docs/adr/0008-anomaly-detection-and-alerting.md)). Each `(switch, port, metric)` keeps an EWMA mean and variance; after the warm-up every new value is scored before it updates the baseline.

| Metric | Signal when | Floor |
| --- | --- | --- |
| `rx_bps`, `tx_bps` | `\|z\| >= 3` warning, `\|z\| >= 5` critical, and the deviation is at least `100 kbit/s` | sigma at least `10 kbit/s` |
| `drop_rate` | the same z thresholds, or `drop_rate >= 0.02` (at least warning) | sigma at least `0.005` |
| `error_rate` | the same z thresholds, or `error_rate > 0` (at least warning) | sigma at least `0.005` |

`z = (value - mean) / max(sigma, floor)`. Counter resets skip scoring and do not touch the baseline. The sigma floors keep a flat series from producing infinite scores; the absolute guards keep quiet ports from alerting on noise and keep a port that drops packets alerting for as long as it drops.

Signals drive an alert lifecycle with one open alert per `(switch, port, metric)`:

| Event | When | Effect |
| --- | --- | --- |
| `opened` | A signal arrives with no open alert and no cooldown in force | New row with `opened_at = last_seen_at`, the signal's severity, value, expected and z-score |
| `refreshed` | A further signal of the same or lower severity | `last_seen_at`, value, expected and z-score updated; severity never drops while open |
| `escalated` | A further signal of higher severity | As refreshed, plus severity raised to critical |
| `resolved` | No signal for `NETPULSE_COLLECTOR_ALERT_RESOLVE_AFTER_SECONDS` (60 s) | `status = resolved`, `resolved_at` set |
| `suppressed` | A signal within `NETPULSE_COLLECTOR_ALERT_COOLDOWN_SECONDS` (120 s) after a resolution | Nothing persisted; after the cooldown the next signal opens a new alert |

Every event except `suppressed` is written to the `alerts` table, and every event is handed to the notifier: logging by default, or the alert routes below when any is configured. Opening is an upsert on the partial unique index over open alerts, so a retried cycle never duplicates a row, and open alerts survive collector restarts: the collector reloads them at startup, a still-active anomaly keeps refreshing the same row and a vanished one resolves after the policy window. Baselines are not persisted, so a restart re-enters the one-minute warm-up before scoring resumes. Acknowledging an alert is a user mark on the row and does not stop the lifecycle.

Because the baseline is an EWMA, a sustained step in throughput is absorbed within a few samples: throughput alerts describe changes, not levels, and resolve on their own. That makes the iperf3 bursts themselves open short throughput alerts with the core defaults. The collector counters that in two ways: `NETPULSE_COLLECTOR_DETECTION_MIN_BPS_DELTA` ignores changes under 1 Mbit/s, and `NETPULSE_COLLECTOR_ALERT_OPEN_AFTER_SIGNALS` keeps a key pending until three consecutive samples signal, so a 10 s burst never opens an alert while a 30 s `host_down` still does. Raise the z thresholds (`NETPULSE_COLLECTOR_DETECTION_WARNING_Z`, `NETPULSE_COLLECTOR_DETECTION_CRITICAL_Z`) or the floor to quiet them further. Rate alerts do not have this problem because the absolute floors keep them open while the port keeps dropping.

### Alert routing and retention

Alert events leave the collector through routes. `COLLECTOR_ALERT_WEBHOOK_URL` defines a route named `default`, and `COLLECTOR_ALERT_ROUTES` adds any number of others as a JSON list:

```json
[
  {"name": "pager", "webhook_url": "https://pager.example.test/hook", "min_severity": "critical"},
  {"name": "drops", "webhook_url": "https://chat.example.test/hook", "metrics": ["drop_rate", "error_rate"]},
  {"name": "audit", "kinds": ["opened", "refreshed", "escalated", "resolved", "suppressed"]}
]
```

Each route takes a `name`, an optional `webhook_url`, a `min_severity` (`warning` by default, or `critical`), an optional `metrics` list (`rx_bps`, `tx_bps`, `drop_rate`, `error_rate`; all metrics when omitted) and an optional `kinds` list, which defaults to `opened`, `escalated` and `resolved`. A route with a `webhook_url` receives one POST per cycle with its matching events (`{"events": [{"kind": "opened", "alert": {...}}]}`); a route without one logs them. The same event can reach several routes, a failing route never blocks the others, and `refreshed` and `suppressed` events stay inside the collector unless a route lists them. With neither variable set, every event is logged.

The collector also deletes resolved alerts older than `COLLECTOR_ALERT_RETENTION_DAYS` (7 days) once every `NETPULSE_COLLECTOR_ALERT_RETENTION_EVERY_CYCLES` poll cycles (720, one hour at 5 s polling), logging how many rows it removed; open alerts are never touched.

### Data model

Migrations live in [`db/migrations`](db/migrations) and are applied by the `migrate` Compose service ([ADR 0005](docs/adr/0005-dbmate-sql-migrations.md)). Sizing and policy choices are explained in [ADR 0006](docs/adr/0006-retention-compression-aggregates.md).

| Relation | Kind | Key | Contents | Retention |
| --- | --- | --- | --- | --- |
| `port_stats` | hypertable, 1-day chunks, compressed after 1 day | `(dpid, port_no, time)` | One row per port per poll: cumulative rx/tx packets, bytes, dropped, errors and `duration_sec` | 7 days |
| `port_stats_1m` | continuous aggregate, refreshed every minute, real-time | `(dpid, port_no, bucket)` | Last counter values in each 1-minute bucket and the number of `samples` | 90 days |
| `alerts` | plain table, partial unique index on open `(dpid, port_no, metric)`, index on `(status, opened_at desc)` | `id` | One row per alert: key, severity, status, `opened_at`, `last_seen_at`, `resolved_at`, `acknowledged_at`, value, expected, z-score, `updated_at` | none yet |

Sample writes are idempotent (`ON CONFLICT DO NOTHING`), so a retried poll cycle never duplicates rows.

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

Every alert carries `id`, `dpid`, `port_no`, `metric` (`rx_bps`, `tx_bps`, `drop_rate` or `error_rate`), `severity` (`warning` or `critical`), `status` (`open` or `resolved`), `opened_at`, `last_seen_at`, `resolved_at`, `acknowledged_at`, `value`, `expected`, `zscore` and `updated_at`.

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

### Alerts example

```sh
curl -s "http://localhost:8000/api/v1/alerts?status=all&limit=1"
```

```json
{
  "generated_at": "2026-10-26T12:25:10Z",
  "alerts": [
    {"id": 62, "dpid": 3, "port_no": 3, "metric": "drop_rate", "severity": "critical", "status": "resolved", "opened_at": "2026-10-26T12:23:04Z", "last_seen_at": "2026-10-26T12:23:34Z", "resolved_at": "2026-10-26T12:24:38Z", "acknowledged_at": null, "value": 1.0, "expected": 0.0, "zscore": 200.0, "updated_at": "2026-10-26T12:24:38Z"}
  ]
}
```

### Topology

The controller runs OS-Ken's `switches` app with link observation on: every switch gets an LLDP-to-controller flow at priority `0xFFFF` above the `NORMAL` forwarding rule, so neighbours discover each other through LLDP, and `GET /topology` on the controller lists switches, their ports and the directed links OS-Ken reports. Hosts come from ARP: a second flow at priority `1` matches `eth_type 0x0806` and outputs to both `NORMAL` and `CONTROLLER` (128 bytes), so forwarding is unchanged while OS-Ken's host discovery learns `(mac, ipv4, port)` from every ARP frame that enters an edge port. Each controller port lists its hosts (`"hosts": [{"mac": ..., "ipv4": [...]}]`). The API reads that payload over HTTP (`NETPULSE_API_CONTROLLER_URL`, `NETPULSE_API_CONTROLLER_TIMEOUT_SECONDS`, 2 s) and turns it into nodes and edges:

```json
{
  "generated_at": "2026-10-26T09:00:00Z",
  "nodes": [
    {"id": "s:1", "kind": "switch", "dpid": 1, "port_no": null, "label": "s1", "address": null, "mac": null},
    {"id": "h:2:1", "kind": "host", "dpid": 2, "port_no": 1, "label": "10.0.0.1", "address": "10.0.0.1", "mac": "00:00:00:00:00:01"}
  ],
  "edges": [
    {"source": "s:1", "target": "s:2", "source_port": 1, "target_port": 3, "source_speed_bps": 10000000000, "target_speed_bps": 10000000000},
    {"source": "s:2", "target": "h:2:1", "source_port": 1, "target_port": null, "source_speed_bps": 10000000000, "target_speed_bps": null}
  ]
}
```

The controller reads `curr_speed` (kbps) from each OpenFlow port description and exposes it as `curr_speed_bps` per port (`null` when the switch reports `0`); the API copies it onto each edge end as `source_speed_bps` and `target_speed_bps`. On Mininet, Open vSwitch reports the veth speed (typically 10 Gbit/s) rather than the `TCLink` shaping, which is why utilization keeps using the configured capacity unless `NETPULSE_API_LINK_CAPACITY_SOURCE=openflow`. Each inter-switch link appears once with the lower `dpid` as `source`. A switch port that is neither reserved nor the end of a link is assumed to face a host and becomes a `host` node attached to its switch. Its `label` is the first IPv4 address of the first learned host on that port (`10.0.0.3 +1` when several hosts share the port), or the port name until an ARP frame has been seen; `address` and `mac` carry the same host or `null`. Before LLDP has settled, a broadcast ARP can be learned on an inter-switch port; such entries are ignored because linked ports never become hosts, and the next ARP from the host moves it to its real edge port.

### WebSocket `/ws/telemetry`

The socket pushes the same network summary as `GET /api/v1/kpis/summary`, plus per-switch port KPIs and alert changes, without polling. The API computes a frame every `NETPULSE_API_LIVE_INTERVAL_SECONDS` (5 s by default; Compose ties it to the collector poll interval) from the two newest samples per port inside the lookback window (`NETPULSE_API_LIVE_LOOKBACK_SECONDS`, 120 s).

| Frame | Direction | When |
| --- | --- | --- |
| `{"type": "hello", "version": "..."}` | server to client | Once, right after the connection opens |
| `{"type": "alerts", "generated_at": "...", "alerts": [...]}` | server to client | Right after `hello`, with every open alert, when any alert is open at connect time; afterwards once per cycle in which at least one alert was opened, refreshed, escalated, resolved or acknowledged since the previous cycle, carrying just those alerts, which the client upserts by `id` |
| `{"type": "kpis", "generated_at": "...", "summary": {...}, "switches": [{"dpid", "generated_at", "ports": [...]}]}` | server to client | Every cycle in which at least one port has two samples in the window |
| `{"type": "heartbeat", "at": "..."}` | server to client | Every cycle in which the window holds no sample pairs yet |
| `{"type": "store_unavailable", "at": "..."}` | server to client | Every cycle in which the database cannot be queried |
| `{"type": "ping"}` / `{"type": "pong"}` | client to server / reply | Keepalive; any other client message gets `{"type": "error", "reason": "unsupported message"}` |

Alert changes are picked up by an `updated_at` cursor. `updated_at` is PostgreSQL's `now()`, fixed at transaction start, so a row committed just after the API's poll but stamped before the cursor is skipped until its next change; the window is milliseconds and a reconnect gets the full open snapshot, so the dashboard self-heals ([ADR 0008](docs/adr/0008-anomaly-detection-and-alerting.md) lists the gapless alternative).

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
├── packages/core/           netpulse-core: telemetry models, KPI computation, anomaly detection, alert lifecycle, settings base
├── services/
│   ├── api/                 FastAPI app, health probe, stats, KPI, alert, live and topology ports and adapters, routers, Dockerfile
│   ├── collector/           polling loop, controller client, detector, repository and notifier ports, TimescaleDB and webhook adapters, Dockerfile
│   └── controller/          standalone uv project: OS-Ken app, stats store, link and host discovery, REST, Dockerfile
├── network/                 Mininet topology spec, runner, traffic scheduler, fault injection, entrypoint, Dockerfile
├── web/                     React dashboard, nginx config, Dockerfile
├── db/migrations/           dbmate SQL migrations: hypertable, continuous aggregate, policies, alerts table
├── docs/adr/                architecture decision records
├── docs/images/             dashboard screenshots
├── .github/workflows/ci.yml lint, type check, test and build on every push and PR
├── docker-compose.yml       full stack with health checks
├── pyproject.toml           uv workspace and shared ruff, mypy, pytest config
└── Makefile                 developer entry points
```

## Roadmap

| Version | Scope | State |
| --- | --- | --- |
| v0.1 | Base structure: every layer scaffolded, wired, typed, tested and containerized | Merged (PR #1) |
| v0.2 | Telemetry ingestion: SQL migrations, `port_stats` hypertable with compression and retention, 1-minute continuous aggregate, idempotent batched writes with retry, stats query endpoint, integration tests in CI | Merged (PR #2) |
| v0.3 | KPIs and live dashboard: KPI domain with counter-reset handling, history, switch and summary endpoints, WebSocket feed with heartbeat and backpressure, LLDP topology, live React dashboard, shaped links with scheduled iperf3 traffic | Merged (PR #3) |
| v0.4 | Anomaly detection and alerting: EWMA baselines with z-scores and floors, alert lifecycle with escalation, resolution and cooldown, `alerts` table, list and acknowledge endpoints, alert frames over the WebSocket, webhook notifier, dashboard alerts panel, scheduled `loss` and `host_down` faults, hosts labelled by IP, OpenFlow port speed | Delivered on `feat/anomaly-alerting`, PR pending |
| v0.5 | Alert tuning and routing (quieter throughput thresholds, silencing, per-severity destinations), baseline persistence across collector restarts, multi-metric and multi-port correlation | Next |

## License

[MIT](LICENSE) © 2026 Willber Pilares
