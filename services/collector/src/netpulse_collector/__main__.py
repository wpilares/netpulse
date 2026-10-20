import asyncio
import logging
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
import psycopg
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from netpulse_collector.controller_client import ControllerClient
from netpulse_collector.poller import run_polling
from netpulse_collector.repository import LoggingPortStatsRepository, PortStatsRepository
from netpulse_collector.retry import RetryingPortStatsRepository, RetryPolicy
from netpulse_collector.settings import CollectorSettings
from netpulse_collector.timescale_repository import TimescalePortStatsRepository

POOL_CONNECTION_TIMEOUT_SECONDS = 5.0


@asynccontextmanager
async def open_repository(settings: CollectorSettings) -> AsyncIterator[PortStatsRepository]:
    if settings.repository == "log" or settings.database_url is None:
        yield LoggingPortStatsRepository()
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
        yield RetryingPortStatsRepository(
            TimescalePortStatsRepository(pool),
            RetryPolicy(
                attempts=settings.write_attempts,
                base_delay_seconds=settings.write_retry_base_seconds,
            ),
        )


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
        open_repository(settings) as repository,
    ):
        await run_polling(
            ControllerClient(http),
            repository,
            interval_seconds=settings.poll_interval_seconds,
            stop=stop,
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
