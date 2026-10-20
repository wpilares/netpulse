import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from netpulse_collector.repository import PortStatsRepository, TransientPortStatsWriteError
from netpulse_core import PortStatsReport

logger = logging.getLogger(__name__)

type Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int
    base_delay_seconds: float

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("attempts must be at least 1")

    def delay_after(self, failed_attempt: int) -> float:
        return float(self.base_delay_seconds * 2 ** (failed_attempt - 1))


class RetryingPortStatsRepository:
    def __init__(
        self,
        inner: PortStatsRepository,
        policy: RetryPolicy,
        *,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._inner = inner
        self._policy = policy
        self._sleep = sleep

    async def save(self, report: PortStatsReport) -> None:
        for attempt in range(1, self._policy.attempts):
            try:
                await self._inner.save(report)
            except TransientPortStatsWriteError as error:
                delay = self._policy.delay_after(attempt)
                logger.warning(
                    "write attempt %d/%d failed, retrying in %.1fs: %s",
                    attempt,
                    self._policy.attempts,
                    delay,
                    error,
                )
                await self._sleep(delay)
            else:
                return
        await self._inner.save(report)
