# ADR 0007: KPI computation from cumulative port counters

- Status: Accepted
- Date: 2026-10-26

## Context

`port_stats` stores the cumulative counters OpenFlow reports per port (packets, bytes, drops, errors and `duration_sec`), and `port_stats_1m` keeps the last value of each counter per 1-minute bucket (ADR 0006). The dashboard and the API need rates: throughput in bits per second, packet rate, drop and error ratios and link utilization, both as history for charts and as a current value per port and per switch.

A rate is the difference between two cumulative samples divided by the elapsed time. Two details make this non-trivial: a switch or port restart resets the counters to zero, which produces negative differences, and a counter the switch does not support is stored as `NULL`. Utilization also needs the link capacity, which the controller does not expose yet.

The computation could live in SQL (`lag()` window functions in the query), in the API adapter, or in the shared core domain.

## Decision

**KPIs are computed in `packages/core`** (`netpulse_core.kpi`) from two consecutive `PortSample`s with `compute_port_kpis(previous, current, link_capacity_bps=...)`; `summarize_kpis` folds a set of port KPIs into a `NetworkSummary`. The SQL layer only selects rows: no subtraction, division or reset detection happens in the database, so one tested function owns the semantics for history, latest values and the live WebSocket feed.

**History comes from 1-minute buckets.** `GET /api/v1/switches/{dpid}/ports/{port_no}/kpis?from&to&limit` reads consecutive `port_stats_1m` rows ordered by `bucket` within the window and pairs each bucket with the previous one; the KPI point is stamped with the later bucket. The adapter fetches `limit + 1` buckets so `limit` bounds the number of points. The first bucket of the window has no predecessor inside the window and therefore produces no point; a window of at most 7 days is allowed, matching the aggregate's granularity and retention.

**Latest values come from raw rows.** `GET /api/v1/switches/{dpid}/kpis` and `GET /api/v1/kpis/summary` pair the two newest `port_stats` rows per `(dpid, port_no)` (`row_number()` over a partition ordered by `time DESC`). A port with a single sample has no rate yet and is skipped. The live telemetry feed reuses the same `LatestSamplesQuery` port and the same pure helpers (`latest_port_kpis`, `switch_kpis`, `network_kpi_summary`).

**Counter resets produce no rates.** When any counter difference is negative, or the interval is not positive, the KPI point carries `counter_reset = true` and every rate is `null`. The interval is taken from `duration_sec` when both samples have it (the switch's own clock) and from the collection timestamps otherwise. A `NULL` counter yields `null` for the rates that depend on it and leaves the others intact.

**Utilization uses a configured link capacity.** `max(rx_bps, tx_bps) / NETPULSE_API_LINK_CAPACITY_BPS` (default 10 Mbit/s, matching the emulated TCLink bandwidth). Reading `curr_speed` from OpenFlow port descriptions is deferred; when the setting is unset, utilization is `null`.

## Consequences

- Rates are consistent everywhere: history, latest, summary and the WebSocket feed cannot drift apart because they share `compute_port_kpis`.
- The database stays a plain store of counters; moving the arithmetic later (for example into a continuous aggregate for long-range charts) would be an optimization behind the same API, not a semantic change.
- A 1-minute history point averages the minute, so short bursts are smoothed; the raw-based latest value reflects one polling interval (5 s by default).
- Counter resets appear as gaps (`null` rates) rather than as negative or absurd spikes; clients should render them as missing data and may show the `counter_reset` flag.
- Utilization is only meaningful when every link has the configured capacity, which holds for the emulated topology. Mixed-speed networks need per-port speed from OpenFlow before utilization is trusted.
- The latest-samples query scans the whole hypertable to rank rows per port. It is acceptable for the demo fleet inside the 7-day raw retention; a larger deployment should bound it to a recent window.
