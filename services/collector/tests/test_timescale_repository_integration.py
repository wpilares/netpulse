import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from netpulse_collector.timescale_repository import TimescalePortStatsRepository
from netpulse_core import PortStats, PortStatsReport, SwitchPortStats

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


UNSUPPORTED_COUNTER = 2**64 - 1


def _report(dpid: int, collected_at: datetime) -> PortStatsReport:
    ports = tuple(
        PortStats(
            port_no=port_no,
            rx_packets=10,
            tx_packets=11,
            rx_bytes=1_000,
            tx_bytes=1_100,
            rx_dropped=0,
            tx_dropped=0,
            rx_errors=UNSUPPORTED_COUNTER,
            tx_errors=0,
            duration_sec=30,
        )
        for port_no in (1, 2, 4_294_967_294)
    )
    return PortStatsReport(
        switches=(SwitchPortStats(dpid=dpid, collected_at=collected_at, ports=ports),)
    )


async def test_writing_the_same_cycle_twice_stores_it_once(pool: ConnectionPool) -> None:
    dpid = 2**64 - 1
    report = _report(dpid, datetime.now(UTC))
    repository = TimescalePortStatsRepository(pool)

    await repository.save(report)
    await repository.save(report)

    async with pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT port_no, rx_errors FROM port_stats WHERE dpid = %s::numeric ORDER BY port_no",
            (dpid,),
        )
        rows = await cursor.fetchall()
    assert rows == [(1, None), (2, None), (4_294_967_294, None)]
