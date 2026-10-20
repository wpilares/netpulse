# ADR 0003: TimescaleDB for telemetry storage

- Status: Accepted
- Date: 2026-10-20

## Context

Telemetry is an append-heavy time series: every poll produces one row per switch port with monotonic counters. The dashboard needs rate computations over sliding windows, downsampled history and retention limits. The API also needs ordinary relational data later (switch inventory, alert rules, acknowledgements).

## Decision

Use **TimescaleDB** (PostgreSQL 18 with the Timescale extension, image `timescale/timescaledb:2.30.2-pg18`).

- Port counters will live in a hypertable partitioned by time.
- Continuous aggregates will back the KPI views (throughput, drop and error rates).
- Retention and compression policies will bound disk usage.
- Relational data shares the same database, so there is one operational dependency.

## Consequences

- Standard PostgreSQL drivers and SQL work unchanged (`psycopg` 3 in the API).
- Time-series features come from the database instead of application code.
- The schema and migrations arrive with telemetry ingestion (v0.2). In v0.1 the API only probes connectivity, and the collector exposes a repository interface with a logging implementation.
