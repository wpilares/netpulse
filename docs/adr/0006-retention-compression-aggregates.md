# ADR 0006: Retention, compression and continuous aggregates for port statistics

- Status: Accepted
- Date: 2026-10-20

## Context

The collector stores one row per switch port every poll (5 s by default). The default topology has 3 switches and 11 ports, which is about 190,000 rows per day; a real deployment can have orders of magnitude more ports. Counters are cumulative (OpenFlow reports totals since the port came up), so rates are computed later from differences between samples. The dashboard needs fine detail for recent troubleshooting and coarse history for trends.

## Decision

**Schema.** `port_stats(time, dpid, port_no, rx/tx packets, bytes, dropped, errors, duration_sec)` with primary key `(dpid, port_no, time)`.

- `dpid` is `numeric(20, 0)` because OpenFlow datapath IDs are unsigned 64-bit and do not fit `bigint`. A check constraint keeps it in range.
- `port_no` is `bigint` because reserved OpenFlow ports such as `LOCAL` (`4294967294`) appear in port statistics and overflow `integer`.
- Counters are nullable `bigint`. OpenFlow reports an unsupported counter as all ones (`2^64 - 1`); the collector stores any value beyond signed 64 bits as `NULL` (unknown) instead of failing the whole batch.
- The primary key makes writes idempotent: the collector inserts with `ON CONFLICT DO NOTHING`, so a retried or replayed cycle never duplicates samples.

**Hypertable.** Partitioned on `time` with **1-day chunks**. A day of raw data for the default topology is a few tens of MB before compression, which keeps the active chunk and its indexes in memory, and it aligns chunk boundaries with the compression and retention windows so whole chunks are compressed or dropped at once.

**Compression (columnstore).** Enabled with `segmentby = 'dpid, port_no'` and `orderby = 'time DESC'`, and a columnstore policy compressing chunks older than **1 day**. Segmenting by port puts each series in its own compressed batches, so per-port queries decompress only that port, and delta encoding of monotonic counters compresses very well. TimescaleDB 2.18+ names this the columnstore API (`enable_columnstore`, `add_columnstore_policy`); the older `compress` names are aliases.

**Continuous aggregate.** `port_stats_1m` buckets by **1 minute** per `(dpid, port_no)` and keeps `last()` of each counter plus the `samples` count. Because counters are cumulative, the last value of a bucket is the meaningful value: rates over any window are differences between bucket values, and averaging counters would be meaningless. `samples` exposes gaps (fewer than 12 samples per minute at 5 s polling). Real-time aggregation is on (`materialized_only = false`), so the newest, not yet materialized minute is computed from raw rows on read. A refresh policy runs every minute over the window from 1 hour to 1 minute ago, which also absorbs late or retried writes.

**Retention.** Raw data is kept **7 days**, the aggregate **90 days**.

## Consequences

- Raw 5 s detail covers the last week, enough to investigate recent incidents; trends beyond that use 1-minute resolution, which is 12 times smaller and still fine-grained for a quarter of history.
- The aggregate keeps its rows after raw chunks are dropped, because the refresh window (1 hour) is far shorter than raw retention (7 days). Refreshing a range older than 7 days manually would erase aggregate rows for it, so manual refreshes must stay inside raw retention.
- Writes into compressed chunks are possible but slower; the collector only writes current data, which always lands in the uncompressed chunk.
- These numbers are starting points sized for the demo topology. Larger fleets would shorten raw retention or chunk interval, and v0.3 can add hourly aggregates on top of `port_stats_1m` (hierarchical continuous aggregates) for long-range charts.
- Counter resets (switch or port restarts, visible as `duration_sec` going down) are stored as-is; rate computations in v0.3 must detect and handle them.
