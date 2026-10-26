import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from netpulse_collector.alerts import AlertWriteError
from netpulse_collector.timescale_alerts import TimescaleAlertRepository
from netpulse_core import AlertEvent, AlertEventKind, AlertKey, AlertState, Severity

DATABASE_URL_VARIABLE = "NETPULSE_TEST_DATABASE_URL"
MIGRATIONS = Path(__file__).resolve().parents[3] / "db" / "migrations"
UP_MARKER = "-- migrate:up"
DOWN_MARKER = "-- migrate:down"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get(DATABASE_URL_VARIABLE), reason=f"{DATABASE_URL_VARIABLE} is not set"
    ),
]

type ConnectionPool = AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]]


def _up_section(migration: Path) -> str:
    up, _, _ = migration.read_text().partition(DOWN_MARKER)
    return up.replace(UP_MARKER, "", 1)


@pytest.fixture(scope="module")
def database_url() -> Iterator[str]:
    admin_url = os.environ[DATABASE_URL_VARIABLE]
    name = f"netpulse_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        test_url = make_conninfo(admin_url, dbname=name)
        with psycopg.connect(test_url, autocommit=True) as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                connection.execute(_up_section(migration))
        yield test_url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture
async def pool(database_url: str) -> AsyncIterator[ConnectionPool]:
    async with AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]](
        database_url, min_size=1, max_size=2, open=False
    ) as connection_pool:
        await connection_pool.wait()
        yield connection_pool


@pytest.fixture(autouse=True)
async def clean_alerts(pool: ConnectionPool) -> None:
    async with pool.connection() as connection:
        await connection.execute("DELETE FROM alerts")


T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
DPID = 2**64 - 1
KEY: AlertKey = (DPID, 4_294_967_294, "drop_rate")
SELECT_ALERTS = """
    SELECT status, severity, opened_at, last_seen_at, resolved_at, value, expected, zscore
    FROM alerts
    WHERE dpid = %s::numeric AND port_no = %s AND metric = %s
    ORDER BY id
"""


def _event(
    kind: AlertEventKind,
    *,
    severity: Severity = "warning",
    last_seen_at: datetime = T0,
    resolved_at: datetime | None = None,
    value: float = 0.1,
    zscore: float = 20.0,
) -> AlertEvent:
    return AlertEvent(
        kind=kind,
        state=AlertState(
            key=KEY,
            severity=severity,
            opened_at=T0,
            last_seen_at=last_seen_at,
            value=value,
            expected=0.0,
            zscore=zscore,
            status="resolved" if resolved_at is not None else "open",
            resolved_at=resolved_at,
        ),
    )


async def _rows(pool: ConnectionPool) -> list[tuple[object, ...]]:
    async with pool.connection() as connection:
        cursor = await connection.execute(SELECT_ALERTS, KEY)
        return await cursor.fetchall()


async def test_lifecycle_events_insert_update_and_resolve_one_row(pool: ConnectionPool) -> None:
    repository = TimescaleAlertRepository(pool)
    refreshed_at = T0 + timedelta(seconds=5)
    resolved_at = T0 + timedelta(seconds=70)

    await repository.apply([_event("opened")])
    await repository.apply(
        [
            _event(
                "escalated", severity="critical", last_seen_at=refreshed_at, value=0.4, zscore=80.0
            )
        ]
    )
    await repository.apply([_event("suppressed", severity="critical", last_seen_at=refreshed_at)])
    await repository.apply(
        [
            _event(
                "resolved",
                severity="critical",
                last_seen_at=refreshed_at,
                resolved_at=resolved_at,
                value=0.4,
                zscore=80.0,
            )
        ]
    )

    assert await _rows(pool) == [
        ("resolved", "critical", T0, refreshed_at, resolved_at, 0.4, 0.0, 80.0)
    ]


async def test_resolved_alert_leaves_room_for_a_new_open_one(pool: ConnectionPool) -> None:
    repository = TimescaleAlertRepository(pool)
    resolved_at = T0 + timedelta(seconds=70)
    reopened_at = T0 + timedelta(seconds=200)

    await repository.apply([_event("opened")])
    await repository.apply([_event("resolved", resolved_at=resolved_at)])
    await repository.apply(
        [
            AlertEvent(
                kind="opened",
                state=_event("opened").state.model_copy(
                    update={"opened_at": reopened_at, "last_seen_at": reopened_at}
                ),
            )
        ]
    )

    rows = await _rows(pool)
    assert [(row[0], row[2]) for row in rows] == [("resolved", T0), ("open", reopened_at)]


async def test_second_open_alert_for_the_same_key_is_rejected(pool: ConnectionPool) -> None:
    repository = TimescaleAlertRepository(pool)
    await repository.apply([_event("opened")])

    with pytest.raises(AlertWriteError, match="alerts_open_key_idx"):
        await repository.apply([_event("opened")])

    assert len(await _rows(pool)) == 1
