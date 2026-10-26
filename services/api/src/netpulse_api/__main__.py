import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
import uvicorn
from fastapi import FastAPI
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool
from starlette.types import Lifespan

from netpulse_api.app import create_app
from netpulse_api.health import PostgresProbe
from netpulse_api.settings import ApiSettings
from netpulse_api.timescale_kpis import TimescaleKpiHistoryQuery, TimescaleLatestSamplesQuery
from netpulse_api.timescale_stats import ConnectionPool, TimescalePortStatsQuery


def pool_lifespan(pool: ConnectionPool) -> Lifespan[FastAPI]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with pool:
            yield

    return lifespan


def build_app(settings: ApiSettings) -> FastAPI:
    if settings.database_url is None:
        return create_app(database_probe=None, link_capacity_bps=settings.link_capacity_bps)
    dsn = settings.database_url.encoded_string()
    pool = AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]](
        dsn,
        min_size=1,
        max_size=settings.database_pool_size,
        open=False,
        timeout=settings.database_timeout_seconds,
        check=AsyncConnectionPool.check_connection,
        name="api",
    )
    return create_app(
        database_probe=PostgresProbe(dsn, timeout_seconds=settings.database_timeout_seconds),
        port_stats_query=TimescalePortStatsQuery(pool),
        kpi_history=TimescaleKpiHistoryQuery(pool, link_capacity_bps=settings.link_capacity_bps),
        latest_samples=TimescaleLatestSamplesQuery(pool),
        link_capacity_bps=settings.link_capacity_bps,
        lifespan=pool_lifespan(pool),
    )


def main() -> None:
    settings = ApiSettings()
    logging.basicConfig(level=settings.log_level)
    uvicorn.run(
        build_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
