import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol

from netpulse_api.topology import PortRef, TopologyQuery, TopologyUnavailableError, port_speeds
from netpulse_core import DatapathId, PortNumber

logger = logging.getLogger(__name__)

DEFAULT_CAPACITY_TTL_SECONDS: Final = 30.0

type Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


class LinkCapacityResolver(Protocol):
    async def refresh(self) -> None: ...

    def capacity_for(self, dpid: DatapathId, port_no: PortNumber) -> int | None: ...


type LinkCapacity = LinkCapacityResolver | int | None


class ConfiguredCapacity:
    def __init__(self, link_capacity_bps: int | None) -> None:
        self._link_capacity_bps = link_capacity_bps

    async def refresh(self) -> None:
        return None

    def capacity_for(self, dpid: DatapathId, port_no: PortNumber) -> int | None:
        return self._link_capacity_bps


class TopologyCapacity:
    def __init__(
        self,
        query: TopologyQuery,
        *,
        fallback_bps: int | None,
        ttl_seconds: float = DEFAULT_CAPACITY_TTL_SECONDS,
        clock: Clock = utc_now,
    ) -> None:
        self._query = query
        self._fallback_bps = fallback_bps
        self._ttl = timedelta(seconds=ttl_seconds)
        self._clock = clock
        self._speeds: dict[PortRef, int] = {}
        self._refreshed_at: datetime | None = None

    async def refresh(self) -> None:
        now = self._clock()
        if self._refreshed_at is not None and now - self._refreshed_at < self._ttl:
            return
        self._refreshed_at = now
        try:
            controller = await self._query.fetch()
        except TopologyUnavailableError:
            logger.warning("controller topology unavailable, keeping last known port speeds")
            return
        self._speeds = port_speeds(controller)

    def capacity_for(self, dpid: DatapathId, port_no: PortNumber) -> int | None:
        return self._speeds.get((dpid, port_no), self._fallback_bps)


def resolve_capacity(capacity: LinkCapacity) -> LinkCapacityResolver:
    if capacity is None or isinstance(capacity, int):
        return ConfiguredCapacity(capacity)
    return capacity
