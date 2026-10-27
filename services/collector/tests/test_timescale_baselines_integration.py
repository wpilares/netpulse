import os
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from netpulse_collector.alerts import AlertReadError
from netpulse_collector.timescale_baselines import TimescaleBaselineRepository
from netpulse_core import Baseline, BaselineKey

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

MAX_DPID = 2**64 - 1
MAX_PORT = 4_294_967_294
RX_KEY: BaselineKey = (MAX_DPID, MAX_PORT, "rx_bps")
DROP_KEY: BaselineKey = (MAX_DPID, MAX_PORT, "drop_rate")
OTHER_KEY: BaselineKey = (7, 3, "tx_bps")


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
        async with connection_pool.connection() as connection:
            await connection.execute("DELETE FROM alert_baselines")
        yield connection_pool


async def test_load_returns_an_empty_mapping_without_rows(pool: ConnectionPool) -> None:
    assert await TimescaleBaselineRepository(pool).load() == {}


async def test_saved_baselines_round_trip_through_load(pool: ConnectionPool) -> None:
    repository = TimescaleBaselineRepository(pool)
    baselines = {
        RX_KEY: Baseline(mean=1_600.0, variance=250.5, samples=12),
        DROP_KEY: Baseline(mean=0.0, variance=0.0, samples=1),
        OTHER_KEY: Baseline(mean=8_000_000.0, variance=1e9, samples=40),
    }

    await repository.save(baselines)

    assert await repository.load() == baselines


async def test_save_overwrites_existing_rows(pool: ConnectionPool) -> None:
    repository = TimescaleBaselineRepository(pool)
    await repository.save({RX_KEY: Baseline(mean=1_600.0, variance=250.5, samples=12)})

    await repository.save({RX_KEY: Baseline(mean=1_700.0, variance=300.0, samples=13)})

    assert await repository.load() == {RX_KEY: Baseline(mean=1_700.0, variance=300.0, samples=13)}


async def test_save_without_baselines_is_a_no_op(pool: ConnectionPool) -> None:
    repository = TimescaleBaselineRepository(pool)

    await repository.save({})

    assert await repository.load() == {}


async def test_delete_removes_only_the_given_keys(pool: ConnectionPool) -> None:
    repository = TimescaleBaselineRepository(pool)
    kept = Baseline(mean=8_000_000.0, variance=1e9, samples=40)
    await repository.save(
        {
            RX_KEY: Baseline(mean=1_600.0, variance=250.5, samples=12),
            DROP_KEY: Baseline(mean=0.0, variance=0.0, samples=1),
            OTHER_KEY: kept,
        }
    )

    await repository.delete([RX_KEY, DROP_KEY, (9, 9, "error_rate")])
    await repository.delete([])

    assert await repository.load() == {OTHER_KEY: kept}


DROP_SAMPLES_CONSTRAINT = (
    "ALTER TABLE alert_baselines DROP CONSTRAINT alert_baselines_samples_positive"
)
RESTORE_SAMPLES_CONSTRAINT = """
    ALTER TABLE alert_baselines
    ADD CONSTRAINT alert_baselines_samples_positive CHECK (samples >= 1)
"""
INSERT_UNSAMPLED_ROW = """
    INSERT INTO alert_baselines (dpid, port_no, metric, mean, variance, samples)
    VALUES (7, 3, 'tx_bps', 1.0, 1.0, 0)
"""


async def test_load_reports_rows_the_model_rejects_as_a_read_error(pool: ConnectionPool) -> None:
    repository = TimescaleBaselineRepository(pool)
    async with pool.connection() as connection:
        await connection.execute(DROP_SAMPLES_CONSTRAINT)
    try:
        async with pool.connection() as connection:
            await connection.execute(INSERT_UNSAMPLED_ROW)

        with pytest.raises(AlertReadError, match="ValidationError"):
            await repository.load()
    finally:
        async with pool.connection() as connection:
            await connection.execute("DELETE FROM alert_baselines")
            await connection.execute(RESTORE_SAMPLES_CONSTRAINT)
