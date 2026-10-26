from datetime import UTC, datetime, timedelta

from netpulse_api.capacity import ConfiguredCapacity, TopologyCapacity, resolve_capacity
from netpulse_api.topology import (
    ControllerPort,
    ControllerSwitch,
    ControllerTopology,
    TopologyUnavailableError,
)

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
FALLBACK_BPS = 10_000_000


class StubTopologyQuery:
    def __init__(self, *outcomes: ControllerTopology | Exception) -> None:
        self._outcomes = list(outcomes)
        self.fetches = 0

    async def fetch(self) -> ControllerTopology:
        self.fetches += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def _controller(port_speed_bps: int) -> ControllerTopology:
    ports = (
        ControllerPort(
            port_no=1, name="s1-eth1", hw_addr="00:00:00:00:00:01", curr_speed_bps=port_speed_bps
        ),
        ControllerPort(port_no=2, name="s1-eth2", hw_addr="00:00:00:00:00:02", curr_speed_bps=0),
        ControllerPort(port_no=3, name="s1-eth3", hw_addr="00:00:00:00:00:03"),
    )
    return ControllerTopology(switches=(ControllerSwitch(dpid=1, ports=ports),), links=())


async def test_configured_capacity_is_the_same_for_every_port() -> None:
    capacity = ConfiguredCapacity(FALLBACK_BPS)
    await capacity.refresh()

    assert capacity.capacity_for(1, 1) == FALLBACK_BPS
    assert capacity.capacity_for(7, 9) == FALLBACK_BPS
    assert ConfiguredCapacity(None).capacity_for(1, 1) is None


async def test_topology_capacity_uses_port_speed_and_falls_back_when_unknown() -> None:
    query = StubTopologyQuery(_controller(1_000_000_000))
    capacity = TopologyCapacity(query, fallback_bps=FALLBACK_BPS, ttl_seconds=30, clock=Clock())

    assert capacity.capacity_for(1, 1) == FALLBACK_BPS
    await capacity.refresh()

    assert capacity.capacity_for(1, 1) == 1_000_000_000
    assert capacity.capacity_for(1, 2) == FALLBACK_BPS
    assert capacity.capacity_for(1, 3) == FALLBACK_BPS
    assert capacity.capacity_for(9, 1) == FALLBACK_BPS
    assert query.fetches == 1


async def test_topology_capacity_refreshes_only_after_the_ttl() -> None:
    query = StubTopologyQuery(_controller(1_000_000_000), _controller(100_000_000))
    clock = Clock()
    capacity = TopologyCapacity(query, fallback_bps=FALLBACK_BPS, ttl_seconds=30, clock=clock)

    await capacity.refresh()
    clock.now += timedelta(seconds=29)
    await capacity.refresh()

    assert query.fetches == 1
    assert capacity.capacity_for(1, 1) == 1_000_000_000

    clock.now += timedelta(seconds=1)
    await capacity.refresh()

    assert query.fetches == 2
    assert capacity.capacity_for(1, 1) == 100_000_000


async def test_topology_capacity_keeps_the_last_speeds_when_the_controller_fails() -> None:
    query = StubTopologyQuery(
        _controller(1_000_000_000), TopologyUnavailableError("down"), _controller(100_000_000)
    )
    clock = Clock()
    capacity = TopologyCapacity(query, fallback_bps=FALLBACK_BPS, ttl_seconds=30, clock=clock)

    await capacity.refresh()
    clock.now += timedelta(seconds=30)
    await capacity.refresh()

    assert query.fetches == 2
    assert capacity.capacity_for(1, 1) == 1_000_000_000

    clock.now += timedelta(seconds=30)
    await capacity.refresh()

    assert query.fetches == 3
    assert capacity.capacity_for(1, 1) == 100_000_000


async def test_topology_capacity_without_fallback_has_no_capacity_for_unknown_ports() -> None:
    capacity = TopologyCapacity(StubTopologyQuery(_controller(1_000_000_000)), fallback_bps=None)

    await capacity.refresh()

    assert capacity.capacity_for(1, 1) == 1_000_000_000
    assert capacity.capacity_for(1, 2) is None


def test_resolve_capacity_wraps_numbers_and_passes_resolvers_through() -> None:
    resolver = ConfiguredCapacity(FALLBACK_BPS)

    assert resolve_capacity(resolver) is resolver
    assert resolve_capacity(FALLBACK_BPS).capacity_for(1, 1) == FALLBACK_BPS
    assert resolve_capacity(None).capacity_for(1, 1) is None
