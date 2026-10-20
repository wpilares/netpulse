import asyncio
import logging
import signal

import httpx2

from netpulse_collector.controller_client import ControllerClient
from netpulse_collector.poller import run_polling
from netpulse_collector.repository import LoggingPortStatsRepository
from netpulse_collector.settings import CollectorSettings


async def serve(settings: CollectorSettings) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop.set)

    async with httpx2.AsyncClient(
        base_url=str(settings.controller_url),
        timeout=settings.request_timeout_seconds,
    ) as http:
        await run_polling(
            ControllerClient(http),
            LoggingPortStatsRepository(),
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
