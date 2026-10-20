import asyncio
import contextlib
import logging
from typing import Protocol

import httpx2
from pydantic import ValidationError

from netpulse_collector.repository import PortStatsRepository, PortStatsWriteError
from netpulse_core import PortStatsReport

logger = logging.getLogger(__name__)


class PortStatsSource(Protocol):
    async def fetch_port_stats(self) -> PortStatsReport: ...


async def poll_once(source: PortStatsSource, repository: PortStatsRepository) -> PortStatsReport:
    report = await source.fetch_port_stats()
    await repository.save(report)
    return report


async def run_polling(
    source: PortStatsSource,
    repository: PortStatsRepository,
    *,
    interval_seconds: float,
    stop: asyncio.Event,
) -> None:
    while not stop.is_set():
        try:
            await poll_once(source, repository)
        except (httpx2.HTTPError, ValidationError, PortStatsWriteError):
            logger.exception("polling cycle failed")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
