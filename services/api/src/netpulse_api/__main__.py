import asyncio
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
from netpulse_api.live import LiveKpiBroadcaster
from netpulse_api.settings import ApiSettings
from netpulse_api.timescale_kpis import TimescaleKpiHistoryQuery, TimescaleLatestSamplesQuery
from netpulse_api.timescale_stats import ConnectionPool, TimescalePortStatsQuery


def storage_lifespan(pool: ConnectionPool, broadcaster: LiveKpiBroadcaster) -> Lifespan[FastAPI]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        stop = asyncio.Event()
        async with pool:
            live_kpis = asyncio.create_task(broadcaster.run(stop), name="live-kpis")
            try:
                yield
            finally:
                stop.set()
                await live_kpis

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
    broadcaster = LiveKpiBroadcaster(
        TimescaleLatestSamplesQuery(pool, lookback_seconds=settings.live_lookback_seconds),
        link_capacity_bps=settings.link_capacity_bps,
        interval_seconds=settings.live_interval_seconds,
        queue_size=settings.live_queue_size,
    )
    return create_app(
        database_probe=PostgresProbe(dsn, timeout_seconds=settings.database_timeout_seconds),
        port_stats_query=TimescalePortStatsQuery(pool),
        kpi_history=TimescaleKpiHistoryQuery(pool, link_capacity_bps=settings.link_capacity_bps),
        latest_samples=TimescaleLatestSamplesQuery(pool),
        link_capacity_bps=settings.link_capacity_bps,
        live_broadcaster=broadcaster,
        lifespan=storage_lifespan(pool, broadcaster),
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
