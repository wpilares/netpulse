import asyncio
import logging
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta

import httpx2
import psycopg
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from netpulse_collector.alerts import (
    AlertNotifier,
    AlertReadError,
    AlertRepository,
    LoggingAlertNotifier,
    LoggingAlertRepository,
)
from netpulse_collector.controller_client import ControllerClient
from netpulse_collector.detector import AlertRetention, AnomalyDetector, DetectionObserver
from netpulse_collector.poller import PortStatsObserver, run_polling
from netpulse_collector.repository import LoggingPortStatsRepository, PortStatsRepository
from netpulse_collector.retry import RetryingPortStatsRepository, RetryPolicy
from netpulse_collector.routing import RoutingAlertNotifier
from netpulse_collector.settings import CollectorSettings
from netpulse_collector.timescale_alerts import TimescaleAlertRepository
from netpulse_collector.timescale_repository import TimescalePortStatsRepository
from netpulse_collector.webhook import WebhookAlertNotifier
from netpulse_core.settings import quiet_http_client_logging

logger = logging.getLogger(__name__)

POOL_CONNECTION_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class Repositories:
    port_stats: PortStatsRepository
    alerts: AlertRepository


@asynccontextmanager
async def open_repositories(settings: CollectorSettings) -> AsyncIterator[Repositories]:
    if settings.repository == "log" or settings.database_url is None:
        yield Repositories(LoggingPortStatsRepository(), LoggingAlertRepository())
        return
    pool = AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]](
        settings.database_url.encoded_string(),
        min_size=1,
        max_size=1,
        open=False,
        timeout=POOL_CONNECTION_TIMEOUT_SECONDS,
        check=AsyncConnectionPool.check_connection,
        name="collector",
    )
    async with pool:
        yield Repositories(
            port_stats=RetryingPortStatsRepository(
                TimescalePortStatsRepository(pool),
                RetryPolicy(
                    attempts=settings.write_attempts,
                    base_delay_seconds=settings.write_retry_base_seconds,
                ),
            ),
            alerts=TimescaleAlertRepository(pool),
        )


@asynccontextmanager
async def open_notifier(settings: CollectorSettings) -> AsyncIterator[AlertNotifier]:
    routes = settings.routes()
    if not routes:
        yield LoggingAlertNotifier()
        return
    async with httpx2.AsyncClient(timeout=settings.request_timeout_seconds) as http:
        webhooks = {
            route.name: WebhookAlertNotifier(http, route.webhook_url)
            for route in routes
            if route.webhook_url is not None
        }
        logger.info("routing alert events to %d routes (%d webhooks)", len(routes), len(webhooks))
        yield RoutingAlertNotifier(routes, webhooks)


async def build_observer(
    settings: CollectorSettings, repositories: Repositories, notifier: AlertNotifier
) -> PortStatsObserver | None:
    if not settings.detection_enabled:
        return None
    detector = AnomalyDetector(
        config=settings.detection_config(),
        policy=settings.alert_policy(),
        link_capacity_bps=settings.link_capacity_bps,
    )
    await seed_open_alerts(detector, repositories.alerts)
    retention = AlertRetention(
        older_than=timedelta(days=settings.alert_retention_days),
        every_cycles=settings.alert_retention_every_cycles,
    )
    return DetectionObserver(detector, repositories.alerts, notifier, retention)


async def seed_open_alerts(detector: AnomalyDetector, repository: AlertRepository) -> None:
    try:
        states = await repository.load_open()
    except AlertReadError:
        logger.exception("loading open alerts failed; starting without alert state")
        return
    detector.seed(states)
    logger.info("seeded detector with %d open alerts", len(states))


async def serve(settings: CollectorSettings) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop.set)

    async with (
        httpx2.AsyncClient(
            base_url=str(settings.controller_url),
            timeout=settings.request_timeout_seconds,
        ) as http,
        open_repositories(settings) as repositories,
        open_notifier(settings) as notifier,
    ):
        await run_polling(
            ControllerClient(http),
            repositories.port_stats,
            interval_seconds=settings.poll_interval_seconds,
            stop=stop,
            observer=await build_observer(settings, repositories, notifier),
        )


def main() -> None:
    settings = CollectorSettings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    quiet_http_client_logging()
    asyncio.run(serve(settings))


if __name__ == "__main__":
    main()
