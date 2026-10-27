import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import httpx2
import psycopg
import uvicorn
from fastapi import FastAPI
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool
from starlette.types import Lifespan

from netpulse_api.app import create_app
from netpulse_api.capacity import ConfiguredCapacity, LinkCapacityResolver, TopologyCapacity
from netpulse_api.controller_topology import ControllerTopologyQuery
from netpulse_api.health import PostgresProbe
from netpulse_api.live import LiveKpiBroadcaster
from netpulse_api.settings import ApiSettings
from netpulse_api.timescale_alerts import TimescaleAlertStore
from netpulse_api.timescale_kpis import TimescaleKpiHistoryQuery, TimescaleLatestSamplesQuery
from netpulse_api.timescale_stats import ConnectionPool, TimescalePortStatsQuery
from netpulse_api.topology import TopologyQuery
from netpulse_core.settings import quiet_http_client_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def live_kpis(pool: ConnectionPool, broadcaster: LiveKpiBroadcaster) -> AsyncIterator[None]:
    stop = asyncio.Event()
    async with pool:
        task = asyncio.create_task(broadcaster.run(stop), name="live-kpis")
        try:
            yield
        finally:
            stop.set()
            await task


def build_lifespan(
    controller: httpx2.AsyncClient | None,
    storage: tuple[ConnectionPool, LiveKpiBroadcaster] | None,
) -> Lifespan[FastAPI]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            if controller is not None:
                await stack.enter_async_context(controller)
            if storage is not None:
                await stack.enter_async_context(live_kpis(*storage))
            yield

    return lifespan


def build_controller_client(settings: ApiSettings) -> httpx2.AsyncClient | None:
    if settings.controller_url is None:
        return None
    return httpx2.AsyncClient(
        base_url=str(settings.controller_url), timeout=settings.controller_timeout_seconds
    )


def build_capacity(
    settings: ApiSettings, topology_query: TopologyQuery | None
) -> LinkCapacityResolver:
    if settings.link_capacity_source == "openflow":
        if topology_query is not None:
            return TopologyCapacity(topology_query, fallback_bps=settings.link_capacity_bps)
        logger.warning(
            "link capacity source is openflow but no controller url is configured, "
            "using the configured capacity"
        )
    return ConfiguredCapacity(settings.link_capacity_bps)


def build_app(settings: ApiSettings) -> FastAPI:
    controller = build_controller_client(settings)
    topology_query = None if controller is None else ControllerTopologyQuery(controller)
    capacity = build_capacity(settings, topology_query)
    if settings.database_url is None:
        return create_app(
            database_probe=None,
            link_capacity_bps=settings.link_capacity_bps,
            capacity=capacity,
            topology_query=topology_query,
            lifespan=build_lifespan(controller, None),
        )
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
    alert_store = TimescaleAlertStore(pool)
    broadcaster = LiveKpiBroadcaster(
        TimescaleLatestSamplesQuery(pool, lookback_seconds=settings.live_lookback_seconds),
        link_capacity_bps=settings.link_capacity_bps,
        interval_seconds=settings.live_interval_seconds,
        queue_size=settings.live_queue_size,
        alerts=alert_store,
        capacity=capacity,
    )
    return create_app(
        database_probe=PostgresProbe(dsn, timeout_seconds=settings.database_timeout_seconds),
        port_stats_query=TimescalePortStatsQuery(pool),
        kpi_history=TimescaleKpiHistoryQuery(pool, link_capacity_bps=settings.link_capacity_bps),
        latest_samples=TimescaleLatestSamplesQuery(pool),
        link_capacity_bps=settings.link_capacity_bps,
        capacity=capacity,
        live_broadcaster=broadcaster,
        topology_query=topology_query,
        alerts_query=alert_store,
        alert_command=alert_store,
        lifespan=build_lifespan(controller, (pool, broadcaster)),
    )


def main() -> None:
    settings = ApiSettings()
    logging.basicConfig(level=settings.log_level)
    quiet_http_client_logging()
    uvicorn.run(
        build_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
