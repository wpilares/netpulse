# ADR 0005: Plain SQL migrations with dbmate

- Status: Accepted
- Date: 2026-10-20

## Context

v0.2 introduces the first schema: a hypertable, a continuous aggregate and background policies for compression, retention and refresh. Most of that DDL is TimescaleDB-specific (`create_hypertable`, `add_columnstore_policy`, `WITH (timescaledb.continuous)`), so an ORM's schema diffing cannot express it and would hide it behind raw-SQL escape hatches anyway. The schema must be applied before the collector writes and the API reads, both locally with Compose and in CI.

Options considered:

- **Alembic.** Python-native and widely used, but its value is autogeneration from SQLAlchemy models, which NetPulse does not use. Every migration here would be `op.execute("...")`, which adds a Python layer and a dependency on the workspace environment without adding safety.
- **Application-run migrations at startup.** Couples schema changes to whichever service starts first and races when two services boot together.
- **dbmate with plain SQL files.** A single static binary with an official image, versioned `.sql` files with `up` and `down` sections, a `schema_migrations` table, and a `--wait` flag that blocks until the database accepts connections.

## Decision

- Use **dbmate 2.36** (`ghcr.io/amacneil/dbmate:2.36.0`) with plain SQL files in `db/migrations`, named `<UTC timestamp>_<description>.sql`.
- Each file has a `-- migrate:up` and a `-- migrate:down` section. These two markers are dbmate directives, not explanatory comments, and are the only comment-syntax lines allowed in SQL.
- Compose runs a one-shot `migrate` service. `collector` and `api` depend on it with `condition: service_completed_successfully`, so neither starts against an unmigrated database. Schema dumps are disabled (`DBMATE_NO_DUMP_SCHEMA`) because the migrations are the source of truth.
- CI applies every migration, rolls all of them back and applies them again against a TimescaleDB service container, so `down` sections are exercised and cannot rot.
- The integration test fixture applies the `up` sections to a throwaway database, which keeps tests isolated from development data.

## Consequences

- TimescaleDB DDL stays explicit and reviewable as SQL; nothing is generated.
- No migration code ships inside the service images, and services never need DDL privileges.
- Migrations are forward-only in production practice; `down` sections exist for local iteration and CI verification. Rolling back `port_stats` drops data.
- A second tool (dbmate) joins the toolchain, but it runs only as a container, so developers install nothing.
