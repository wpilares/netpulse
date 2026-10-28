# Changelog

All notable changes to NetPulse, in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) form. Versions before 1.0.0 were milestones delivered as one pull request each; 1.0.0 is the closed portfolio release; later versions refine it without changing the API contract, and possible extensions stay listed in the [README roadmap](README.md#roadmap).

## [1.1.0] - 2026-10-27

### Added

- Theme selector with `light`, `dark` and `system` modes: the choice is persisted in `localStorage` under `netpulse.theme` and applied by an inline script before the first paint, so a reload never flashes the wrong palette.
- Design tokens in `web/src/styles/tokens.css` (colour, spacing, type scale, radius, shadow, motion) and a set of reusable components under `web/src/components/ui`: `Button`, `Badge`, `Card`, `Pill`, `SegmentedControl`, `Switch`, `Skeleton`, `Icon`, `StatTile`, `StatusPill`, `EmptyState`, `ErrorState`, `ChartFrame` and `ThemeToggle`, each with its CSS Module and tests.
- Loading skeletons, empty states and error states with a retry action on every panel; a responsive layout down to 390 px with an icon-only theme toggle that keeps its accessible names.
- Visual and accessibility verification in both themes with Playwright and axe: no serious or critical violations.
- ADR 0010 on the frontend architecture.

### Changed

- HTTP goes through an `ApiClient` port implemented with axios on the fetch adapter; failures are normalised into a typed `ApiError` (`network`, `not_found`, `unavailable`, `invalid`) and `GET /health` keeps reading a 503 body.
- Every REST response and WebSocket frame is validated with zod schemas in `web/src/api/schemas.ts`; the exported types keep their names.
- Server state lives in a TanStack Query cache: health polls every 10 s, topology every 30 s, the KPI summary and the open alerts load once over REST and are then fed by the WebSocket through a cache bridge; acknowledging an alert is an optimistic mutation with rollback.
- Each feature is split into a container that owns its queries and a view that renders props; the global `styles.css` is replaced by tokens, `global.css` and one CSS Module per component, linted by Biome with `cssModules` enabled.
- Every package reports `1.1.0`.

### Fixed

- A WebSocket `alerts` frame is written into the cache synchronously and cancels the in-flight REST list, so a REST response that resolves after the frame can no longer overwrite it.

## [1.0.0] - 2026-10-27

### Added

- `CHANGELOG.md` and a dashboard GIF in the README showing a `host_down` fault opening and resolving a `drop_rate` alert.
- Roadmap closed: every milestone marked done, possible extensions listed as not planned.

### Changed

- Every package reports `1.0.0`: `GET /health`, `GET /api/v1/info` and the WebSocket `hello` frame carry the new version.
- Resolved alerts are purged by a `RetentionObserver` composed next to `DetectionObserver`, so the purge keeps running when `COLLECTOR_DETECTION_ENABLED=false` whenever the collector writes to TimescaleDB.

## [0.5.0] - 2026-10-27

### Added

- Alert confirmation: a key stays `pending` until `NETPULSE_COLLECTOR_ALERT_OPEN_AFTER_SIGNALS` (3) consecutive signals, so 10 s iperf3 bursts never open an alert; `opened_at` keeps the first signal time.
- Alert routing in `netpulse_core.routing`: `COLLECTOR_ALERT_ROUTES` adds routes filtered by severity, metric and event kind, each with its own webhook; `COLLECTOR_ALERT_WEBHOOK_URL` stays the `default` route.
- Baselines persisted every cycle in `alert_baselines` and reloaded at startup, so a collector restart skips the warm-up.
- `alerts.seq` sequence cursor for the live feed; the broadcaster fetches rows above the last `seq` it saw.
- Hourly purge of resolved alerts older than `COLLECTOR_ALERT_RETENTION_DAYS` (7).
- ADR 0009 on confirmation, persisted baselines, the sequence cursor and routing.

### Changed

- Detection floors and the confirmation count are `NETPULSE_COLLECTOR_*` settings; the throughput floor `min_bps_delta` defaults to 1 Mbit/s in the collector.
- Open alerts of ports absent for 60 cycles are resolved and notified, and their baselines are deleted.

### Fixed

- `seq` is assigned in commit order: the collector apply and the API acknowledge transactions take `pg_advisory_xact_lock`, closing the race between an acknowledgement and a collector cycle.
- Empty route filters are rejected and webhook URLs validated at startup instead of creating a route that matches nothing.

## [0.4.0] - 2026-10-26

### Added

- Anomaly detection in `netpulse_core.anomaly`: EWMA baseline per `(switch, port, metric)`, z-scores with sigma floors, absolute floors for `drop_rate` and `error_rate`, warm-up, counter resets skipped.
- Alert lifecycle in `netpulse_core.alerts`: one open alert per key, escalation, refresh, resolution after silence, cooldown suppression.
- `alerts` table, `GET /api/v1/alerts`, `POST /api/v1/alerts/{id}/ack` and `alerts` frames over `/ws/telemetry`, with the open-alert snapshot sent to every new subscriber.
- Dashboard alerts panel with severity badges, acknowledge with optimistic rollback, resolved toggle and a header badge.
- Scheduled fault injection: `loss` and `host_down` faults alternate across the links; a peer floods the downed host so the switch port counts real drops.
- Hosts discovered from ARP and labelled by IPv4; OpenFlow `curr_speed` exposed per port with `NETPULSE_API_LINK_CAPACITY_SOURCE=openflow` as an opt-in.
- ADR 0008 on detection, the alert lifecycle and fault injection.

### Fixed

- `drop_rate` and `error_rate` are measured against attempted frames, so a port that only drops reads `1.0` instead of `null`.
- The `opened` event is an idempotent upsert on the partial unique index and the webhook URL stays out of the logs.

## [0.3.0] - 2026-10-26

### Added

- KPIs in `netpulse_core.kpi` from consecutive samples: throughput, packet rate, drop and error rate, utilization, counter resets as `null` rates (ADR 0007).
- `GET /api/v1/switches/{dpid}/ports/{port_no}/kpis`, `GET /api/v1/switches/{dpid}/kpis` and `GET /api/v1/kpis/summary`.
- Live `kpis` frames over `/ws/telemetry` with `heartbeat`, `store_unavailable` and slow consumers closed with `1013`.
- Topology discovery: LLDP links in the controller, `GET /api/v1/topology` with nodes and edges.
- React dashboard: summary cards, SVG topology, per-port throughput charts, reconnecting WebSocket client with exponential backoff.
- Links shaped to 10 Mbit/s with scheduled iperf3 UDP rounds between hosts.

### Fixed

- TX checksum offload disabled on every veth so hosts stop dropping TCP segments under the Open vSwitch userspace datapath.
- Reserved OpenFlow ports such as `LOCAL` are left out of per-switch KPIs and the summary.

## [0.2.0] - 2026-10-20

### Added

- dbmate SQL migrations: `port_stats` hypertable with 1-day chunks, compression after a day and 7-day retention; `port_stats_1m` continuous aggregate with 90-day retention; one-shot `migrate` Compose service (ADR 0005, ADR 0006).
- `TimescalePortStatsRepository` with batched idempotent inserts and a retrying decorator with bounded exponential backoff.
- `GET /api/v1/switches/{dpid}/ports/{port_no}/stats` at `raw` or `1m` resolution over a time range.
- Integration tests against a real TimescaleDB (`make test-integration`) and a CI `integration` job.

## [0.1.0] - 2026-10-20

### Added

- Monorepo with a uv workspace (Python 3.14), a standalone OS-Ken controller project on Python 3.13 and a Bun web app (ADR 0001 to 0004).
- Mininet tree topology of three switches and four hosts in a privileged container, connected to the OS-Ken controller.
- Controller REST endpoints `/health`, `/switches` and `/stats/ports`; collector polling loop behind `PortStatsSource` and `PortStatsRepository` ports.
- FastAPI service with `/health`, the `/api/v1` router and the `/ws/telemetry` WebSocket; React dashboard shell behind nginx.
- Shared frozen pydantic models in `netpulse-core`; ruff, mypy strict, pytest, Biome, Vitest and GitHub Actions CI.

[1.1.0]: https://github.com/wpilares/netpulse/pull/7
[1.0.0]: https://github.com/wpilares/netpulse/pull/6
[0.5.0]: https://github.com/wpilares/netpulse/pull/5
[0.4.0]: https://github.com/wpilares/netpulse/pull/4
[0.3.0]: https://github.com/wpilares/netpulse/pull/3
[0.2.0]: https://github.com/wpilares/netpulse/pull/2
[0.1.0]: https://github.com/wpilares/netpulse/pull/1
