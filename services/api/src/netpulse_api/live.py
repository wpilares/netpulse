import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict

from netpulse_api.kpis import (
    KpiUnavailableError,
    LatestSamplesQuery,
    NetworkKpiSummary,
    SwitchKpis,
    latest_port_kpis,
    network_kpi_summary,
)
from netpulse_core import NetworkSummary

logger = logging.getLogger(__name__)

SLOW_CONSUMER_CLOSE_CODE: Final = 1013
SLOW_CONSUMER_REASON: Final = "slow consumer"

type Clock = Callable[[], datetime]


class KpiFrame(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["kpis"] = "kpis"
    generated_at: AwareDatetime
    summary: NetworkSummary
    switches: tuple[SwitchKpis, ...]


class HeartbeatFrame(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["heartbeat"] = "heartbeat"
    at: AwareDatetime


class StoreUnavailableFrame(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["store_unavailable"] = "store_unavailable"
    at: AwareDatetime


type LiveFrame = KpiFrame | HeartbeatFrame | StoreUnavailableFrame


def kpi_frame(summary: NetworkKpiSummary) -> KpiFrame:
    return KpiFrame(
        generated_at=summary.generated_at, summary=summary.summary, switches=summary.switches
    )


def utc_now() -> datetime:
    return datetime.now(UTC)


class Subscription:
    def __init__(self, *, queue_size: int) -> None:
        self._frames: asyncio.Queue[LiveFrame] = asyncio.Queue(maxsize=queue_size)
        self._dropped = False

    @property
    def dropped(self) -> bool:
        return self._dropped

    def publish(self, frame: LiveFrame) -> bool:
        try:
            self._frames.put_nowait(frame)
        except asyncio.QueueFull:
            self.drop()
            return False
        return True

    def drop(self) -> None:
        self._dropped = True
        self._frames.shutdown(immediate=True)

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> LiveFrame:
        try:
            return await self._frames.get()
        except asyncio.QueueShutDown:
            raise StopAsyncIteration from None


class LiveKpiBroadcaster:
    def __init__(
        self,
        latest_samples: LatestSamplesQuery,
        *,
        link_capacity_bps: int | None,
        interval_seconds: float,
        queue_size: int,
        clock: Clock = utc_now,
    ) -> None:
        self._latest_samples = latest_samples
        self._link_capacity_bps = link_capacity_bps
        self._interval_seconds = interval_seconds
        self._queue_size = queue_size
        self._clock = clock
        self._subscriptions: set[Subscription] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscriptions)

    def subscribe(self) -> Subscription:
        subscription = Subscription(queue_size=self._queue_size)
        self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        self._subscriptions.discard(subscription)

    async def tick(self) -> LiveFrame:
        frame = await self._next_frame()
        for subscription in list(self._subscriptions):
            if not subscription.publish(frame):
                self._subscriptions.discard(subscription)
                logger.warning("dropped slow live telemetry subscriber")
        return frame

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.tick()
            except Exception:
                logger.exception("live kpi cycle failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self._interval_seconds)

    async def _next_frame(self) -> LiveFrame:
        try:
            pairs = await self._latest_samples.fetch(None)
        except KpiUnavailableError:
            return StoreUnavailableFrame(at=self._clock())
        generated_at = self._clock()
        if not pairs:
            return HeartbeatFrame(at=generated_at)
        kpis = latest_port_kpis(pairs, link_capacity_bps=self._link_capacity_bps)
        return kpi_frame(network_kpi_summary(kpis, generated_at=generated_at))
