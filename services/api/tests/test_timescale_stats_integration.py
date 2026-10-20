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

from netpulse_api.stats import PortStatsRange
from netpulse_api.timescale_stats import TimescalePortStatsQuery

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


INSERT = """
    INSERT INTO port_stats (
        time, dpid, port_no, rx_packets, tx_packets, rx_bytes, tx_bytes,
        rx_dropped, tx_dropped, rx_errors, tx_errors, duration_sec
    )
    VALUES (%s, 7, 2, %s, 0, 0, 0, 0, 0, NULL, 0, %s)
"""


async def test_queries_raw_and_one_minute_resolution(pool: ConnectionPool) -> None:
    start = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(minutes=10)
    samples = [(start + timedelta(seconds=15 * step), 10 + step, step) for step in range(6)]
    async with pool.connection() as connection:
        await connection.set_autocommit(True)
        async with connection.cursor() as cursor:
            await cursor.executemany(INSERT, samples)
        await connection.execute(
            "CALL refresh_continuous_aggregate('port_stats_1m', %s, %s)",
            (start - timedelta(minutes=1), start + timedelta(minutes=3)),
        )
    query = TimescalePortStatsQuery(pool)
    end = start + timedelta(minutes=5)

    raw = await query.fetch(
        PortStatsRange(dpid=7, port_no=2, start=start, end=end, resolution="raw", limit=100)
    )
    per_minute = await query.fetch(
        PortStatsRange(dpid=7, port_no=2, start=start, end=end, resolution="1m", limit=100)
    )
    limited = await query.fetch(
        PortStatsRange(dpid=7, port_no=2, start=start, end=end, resolution="raw", limit=2)
    )

    assert [point.rx_packets for point in raw] == [10, 11, 12, 13, 14, 15]
    assert {point.samples for point in raw} == {1}
    assert raw[0].rx_errors is None
    assert [(point.time, point.rx_packets, point.samples) for point in per_minute] == [
        (start, 13, 4),
        (start + timedelta(minutes=1), 15, 2),
    ]
    assert [point.rx_packets for point in limited] == [10, 11]


async def test_other_ports_and_ranges_are_excluded(pool: ConnectionPool) -> None:
    query = TimescalePortStatsQuery(pool)
    start = datetime.now(UTC) - timedelta(hours=1)

    points = await query.fetch(
        PortStatsRange(
            dpid=7,
            port_no=3,
            start=start,
            end=start + timedelta(minutes=50),
            resolution="raw",
            limit=100,
        )
    )

    assert points == []
