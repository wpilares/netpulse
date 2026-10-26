import asyncio
import logging
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx2
import psycopg
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from netpulse_collector.alerts import (
    AlertNotifier,
    AlertRepository,
    LoggingAlertNotifier,
    LoggingAlertRepository,
)
from netpulse_collector.controller_client import ControllerClient
from netpulse_collector.detector import AnomalyDetector, DetectionObserver
from netpulse_collector.poller import PortStatsObserver, run_polling
from netpulse_collector.repository import LoggingPortStatsRepository, PortStatsRepository
from netpulse_collector.retry import RetryingPortStatsRepository, RetryPolicy
from netpulse_collector.settings import CollectorSettings
from netpulse_collector.timescale_alerts import TimescaleAlertRepository
from netpulse_collector.timescale_repository import TimescalePortStatsRepository
from netpulse_collector.webhook import WebhookAlertNotifier

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
    if settings.alert_webhook_url is None:
        yield LoggingAlertNotifier()
        return
    async with httpx2.AsyncClient(timeout=settings.request_timeout_seconds) as http:
        yield WebhookAlertNotifier(http, str(settings.alert_webhook_url))


def build_observer(
    settings: CollectorSettings, repositories: Repositories, notifier: AlertNotifier
) -> PortStatsObserver | None:
    if not settings.detection_enabled:
        return None
    detector = AnomalyDetector(
        config=settings.detection_config(),
        policy=settings.alert_policy(),
        link_capacity_bps=settings.link_capacity_bps,
    )
    return DetectionObserver(detector, repositories.alerts, notifier)


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
            observer=build_observer(settings, repositories, notifier),
        )


def main() -> None:
    settings = CollectorSettings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    asyncio.run(serve(settings))


if __name__ == "__main__":
    main()
