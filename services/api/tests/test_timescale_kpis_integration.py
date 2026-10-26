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

from netpulse_api.kpis import KpiRange
from netpulse_api.timescale_kpis import TimescaleKpiHistoryQuery, TimescaleLatestSamplesQuery

DATABASE_URL_VARIABLE = "NETPULSE_TEST_DATABASE_URL"
MIGRATIONS = Path(__file__).resolve().parents[3] / "db" / "migrations"
UP_MARKER = "-- migrate:up"
DOWN_MARKER = "-- migrate:down"
CAPACITY_BPS = 10_000_000
POLL = timedelta(seconds=15)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get(DATABASE_URL_VARIABLE), reason=f"{DATABASE_URL_VARIABLE} is not set"
    ),
]

type ConnectionPool = AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]]
type Row = tuple[datetime, int, int, int, int, int, int, int, int, int | None, int, int]


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


@pytest.fixture(scope="module")
def start() -> datetime:
    return datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(minutes=10)


@pytest.fixture
async def pool(database_url: str, start: datetime) -> AsyncIterator[ConnectionPool]:
    async with AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]](
        database_url, min_size=1, max_size=2, open=False
    ) as connection_pool:
        await connection_pool.wait()
        await _seed(connection_pool, start)
        yield connection_pool


INSERT = """
    INSERT INTO port_stats (
        time, dpid, port_no, rx_packets, tx_packets, rx_bytes, tx_bytes,
        rx_dropped, tx_dropped, rx_errors, tx_errors, duration_sec
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT DO NOTHING
"""


def _row(time: datetime, dpid: int, port_no: int, step: int, *, since_reset: int) -> Row:
    return (
        time,
        dpid,
        port_no,
        10 + since_reset * 100,
        since_reset * 50,
        since_reset * 1_000,
        since_reset * 500,
        0,
        0,
        None if port_no == 2 else step,
        0,
        since_reset * 15,
    )


def _resetting_port_rows(start: datetime) -> list[Row]:
    return [
        _row(start + POLL * step, 7, 2, step, since_reset=step if step < 8 else step - 8)
        for step in range(12)
    ]


async def _seed(pool: ConnectionPool, start: datetime) -> None:
    rows = [
        *_resetting_port_rows(start),
        _row(start, 7, 3, 0, since_reset=0),
        _row(start + POLL, 7, 3, 1, since_reset=1),
        _row(start, 7, 9, 0, since_reset=0),
        _row(start, 8, 1, 0, since_reset=0),
        _row(start + POLL, 8, 1, 1, since_reset=2),
    ]
    async with pool.connection() as connection:
        await connection.set_autocommit(True)
        async with connection.cursor() as cursor:
            await cursor.executemany(INSERT, rows)
        await connection.execute("CALL refresh_continuous_aggregate('port_stats_1m', NULL, NULL)")


def _range(start: datetime, *, offset: timedelta = timedelta(), limit: int = 100) -> KpiRange:
    return KpiRange(
        dpid=7, port_no=2, start=start + offset, end=start + timedelta(minutes=5), limit=limit
    )


async def test_history_pairs_consecutive_buckets(pool: ConnectionPool, start: datetime) -> None:
    query = TimescaleKpiHistoryQuery(pool, link_capacity_bps=CAPACITY_BPS)

    points = await query.fetch(_range(start))

    assert [point.computed_at for point in points] == [
        start + timedelta(minutes=1),
        start + timedelta(minutes=2),
    ]
    steady, reset = points
    assert steady.dpid == 7
    assert steady.port_no == 2
    assert steady.interval_seconds == 60.0
    assert steady.rx_pps == pytest.approx(400 / 60)
    assert steady.rx_bps == pytest.approx(4_000 * 8 / 60)
    assert steady.utilization == pytest.approx(4_000 * 8 / 60 / CAPACITY_BPS)
    assert steady.error_rate is None
    assert steady.counter_reset is False
    assert reset.counter_reset is True
    assert reset.rx_bps is None


async def test_history_limit_counts_points(pool: ConnectionPool, start: datetime) -> None:
    query = TimescaleKpiHistoryQuery(pool, link_capacity_bps=CAPACITY_BPS)

    points = await query.fetch(_range(start, limit=1))

    assert [point.computed_at for point in points] == [start + timedelta(minutes=1)]


async def test_history_starts_at_the_second_bucket_of_the_window(
    pool: ConnectionPool, start: datetime
) -> None:
    query = TimescaleKpiHistoryQuery(pool, link_capacity_bps=CAPACITY_BPS)

    points = await query.fetch(_range(start, offset=timedelta(minutes=1)))

    assert [(point.computed_at, point.counter_reset) for point in points] == [
        (start + timedelta(minutes=2), True)
    ]


async def test_history_is_empty_for_unknown_port(pool: ConnectionPool, start: datetime) -> None:
    query = TimescaleKpiHistoryQuery(pool, link_capacity_bps=CAPACITY_BPS)

    points = await query.fetch(
        KpiRange(dpid=7, port_no=4, start=start, end=start + timedelta(minutes=5), limit=100)
    )

    assert points == []


async def test_latest_pairs_the_two_newest_rows_per_port(
    pool: ConnectionPool, start: datetime
) -> None:
    query = TimescaleLatestSamplesQuery(pool)

    pairs = await query.fetch(None)

    assert [(current.dpid, current.stats.port_no) for _, current in pairs] == [
        (7, 2),
        (7, 3),
        (8, 1),
    ]
    previous, current = pairs[0]
    assert previous.collected_at == start + POLL * 10
    assert current.collected_at == start + POLL * 11
    assert (previous.stats.rx_packets, current.stats.rx_packets) == (210, 310)
    assert current.stats.rx_errors is None
    assert pairs[1][1].stats.rx_errors == 1


async def test_latest_filters_by_switch(pool: ConnectionPool, start: datetime) -> None:
    query = TimescaleLatestSamplesQuery(pool)

    switch_pairs = await query.fetch(7)
    unknown = await query.fetch(9)

    assert [current.stats.port_no for _, current in switch_pairs] == [2, 3]
    assert unknown == []


async def test_latest_honours_the_lookback_window(pool: ConnectionPool, start: datetime) -> None:
    recent = TimescaleLatestSamplesQuery(pool, lookback_seconds=60)
    wide = TimescaleLatestSamplesQuery(pool, lookback_seconds=3_600)

    assert await recent.fetch(None) == []
    assert [(current.dpid, current.stats.port_no) for _, current in await wide.fetch(None)] == [
        (7, 2),
        (7, 3),
        (8, 1),
    ]
