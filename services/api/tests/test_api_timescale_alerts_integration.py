import asyncio
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

from netpulse_api.alerts import Alert
from netpulse_api.timescale_alerts import LOCK_ALERT_SEQ, TimescaleAlertStore
from netpulse_core import AlertStatus, Metric

DATABASE_URL_VARIABLE = "NETPULSE_TEST_DATABASE_URL"
MIGRATIONS = Path(__file__).resolve().parents[3] / "db" / "migrations"
UP_MARKER = "-- migrate:up"
DOWN_MARKER = "-- migrate:down"
START = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
MINUTE = timedelta(minutes=1)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get(DATABASE_URL_VARIABLE), reason=f"{DATABASE_URL_VARIABLE} is not set"
    ),
]

type ConnectionPool = AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]]
type Row = tuple[int, int, Metric, str, AlertStatus, datetime, datetime, datetime | None, datetime]


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


INSERT = """
    INSERT INTO alerts (
        dpid, port_no, metric, severity, status,
        opened_at, last_seen_at, resolved_at, value, expected, zscore, updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1000000, 100000, 6.5, %s)
"""


def _row(
    dpid: int,
    port_no: int,
    metric: Metric,
    *,
    opened_minutes: int,
    status: AlertStatus = "open",
    severity: str = "warning",
) -> Row:
    opened_at = START + MINUTE * opened_minutes
    resolved_at = None if status == "open" else opened_at + MINUTE * 2
    updated_at = opened_at + MINUTE if resolved_at is None else resolved_at
    return (dpid, port_no, metric, severity, status, opened_at, opened_at, resolved_at, updated_at)


ROWS: list[Row] = [
    _row(1, 1, "rx_bps", opened_minutes=0),
    _row(1, 2, "drop_rate", opened_minutes=1, status="resolved"),
    _row(2, 1, "error_rate", opened_minutes=2, severity="critical"),
    _row(2, 1, "tx_bps", opened_minutes=3, status="resolved"),
]


@pytest.fixture
async def pool(database_url: str) -> AsyncIterator[ConnectionPool]:
    async with AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]](
        database_url, min_size=1, max_size=2, open=False
    ) as connection_pool:
        await connection_pool.wait()
        async with connection_pool.connection() as connection:
            await connection.execute("TRUNCATE alerts RESTART IDENTITY")
            await connection.execute("ALTER SEQUENCE alerts_seq RESTART")
            async with connection.cursor() as cursor:
                await cursor.executemany(INSERT, ROWS)
        yield connection_pool


def _keys(alerts: list[Alert]) -> list[tuple[int, int, str]]:
    return [(alert.dpid, alert.port_no, alert.metric) for alert in alerts]


async def test_fetch_lists_open_alerts_newest_first(pool: ConnectionPool) -> None:
    store = TimescaleAlertStore(pool)

    alerts = await store.fetch("open", limit=100)

    assert _keys(alerts) == [(2, 1, "error_rate"), (1, 1, "rx_bps")]
    newest = alerts[0]
    assert newest.id == 3
    assert newest.severity == "critical"
    assert newest.status == "open"
    assert newest.opened_at == START + MINUTE * 2
    assert newest.last_seen_at == START + MINUTE * 2
    assert newest.resolved_at is None
    assert newest.acknowledged_at is None
    assert (newest.value, newest.expected, newest.zscore) == (1_000_000.0, 100_000.0, 6.5)
    assert newest.updated_at == START + MINUTE * 3


async def test_fetch_filters_resolved_and_all(pool: ConnectionPool) -> None:
    store = TimescaleAlertStore(pool)

    resolved = await store.fetch("resolved", limit=100)
    everything = await store.fetch("all", limit=100)

    assert _keys(resolved) == [(2, 1, "tx_bps"), (1, 2, "drop_rate")]
    assert resolved[0].resolved_at == START + MINUTE * 5
    assert _keys(everything) == [
        (2, 1, "tx_bps"),
        (2, 1, "error_rate"),
        (1, 2, "drop_rate"),
        (1, 1, "rx_bps"),
    ]


async def test_fetch_honours_the_limit(pool: ConnectionPool) -> None:
    store = TimescaleAlertStore(pool)

    alerts = await store.fetch("all", limit=2)

    assert _keys(alerts) == [(2, 1, "tx_bps"), (2, 1, "error_rate")]


async def test_fetch_after_returns_rows_past_the_cursor_in_seq_order(pool: ConnectionPool) -> None:
    store = TimescaleAlertStore(pool)

    changed = await store.fetch_after(2)
    nothing = await store.fetch_after(4)
    everything = await store.fetch_after(0)

    assert [(alert.id, alert.seq) for alert in changed] == [(3, 3), (4, 4)]
    assert nothing == []
    assert [alert.seq for alert in everything] == [1, 2, 3, 4]


async def test_fetch_after_honours_the_limit(pool: ConnectionPool) -> None:
    store = TimescaleAlertStore(pool)

    first_page = await store.fetch_after(0, limit=2)
    second_page = await store.fetch_after(first_page[-1].seq, limit=2)

    assert [alert.seq for alert in first_page] == [1, 2]
    assert [alert.seq for alert in second_page] == [3, 4]


async def test_acknowledge_sets_the_timestamp_once(pool: ConnectionPool) -> None:
    store = TimescaleAlertStore(pool)
    first_at = START + MINUTE * 10
    second_at = START + MINUTE * 11

    first = await store.acknowledge(1, at=first_at)
    second = await store.acknowledge(1, at=second_at)

    assert first is not None
    assert first.id == 1
    assert first.acknowledged_at == first_at
    assert first.updated_at > START + MINUTE
    assert first.seq == 5
    assert second == first
    (stored,) = [alert for alert in await store.fetch("open", limit=100) if alert.id == 1]
    assert stored == first


async def test_acknowledge_reports_unknown_alerts(pool: ConnectionPool) -> None:
    store = TimescaleAlertStore(pool)

    assert await store.acknowledge(99, at=START) is None


async def test_acknowledge_is_visible_after_the_cursor(pool: ConnectionPool) -> None:
    store = TimescaleAlertStore(pool)

    acknowledged = await store.acknowledge(2, at=START + MINUTE * 10)
    changed = await store.fetch_after(4)

    assert acknowledged is not None
    assert acknowledged.seq == 5
    assert changed == [acknowledged]


WAITING_ADVISORY_LOCKS = "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted"


async def _wait_for_a_lock_waiter(connection: psycopg.AsyncConnection[TupleRow]) -> None:
    while True:
        cursor = await connection.execute(WAITING_ADVISORY_LOCKS)
        row = await cursor.fetchone()
        if row is not None and row[0] == 1:
            return
        await asyncio.sleep(0.02)


async def test_acknowledge_waits_for_the_sequence_lock_held_by_the_collector(
    pool: ConnectionPool,
) -> None:
    store = TimescaleAlertStore(pool)

    async with pool.connection() as collector:
        await collector.execute(LOCK_ALERT_SEQ)
        cursor = await collector.execute("SELECT nextval('alerts_seq')")
        held_row = await cursor.fetchone()
        assert held_row is not None
        held_seq = int(held_row[0])
        blocked = asyncio.create_task(store.acknowledge(1, at=START + MINUTE * 10))
        await asyncio.wait_for(_wait_for_a_lock_waiter(collector), timeout=5)
        assert not blocked.done()
    acknowledged = await asyncio.wait_for(blocked, timeout=5)

    assert acknowledged is not None
    assert acknowledged.seq > held_seq
