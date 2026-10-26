from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal, Self

from netpulse_network.topology import Link, TopologySpec

FaultKind = Literal["loss", "host_down"]
ScheduledEvent = Literal["traffic", "fault_start", "fault_end"]

DEFAULT_KINDS: tuple[FaultKind, ...] = ("loss", "host_down")


@dataclass(frozen=True, slots=True)
class Fault:
    kind: FaultKind
    link: Link
    duration_seconds: int
    loss_percent: int
    host: str | None = None

    def __post_init__(self) -> None:
        if (self.kind == "host_down") != (self.host is not None):
            raise ValueError(f"host must be set exactly when kind is host_down: {self}")

    @property
    def switch(self) -> str:
        return self.link.source if self.link.target == self.host else self.link.target


_LCG_MULTIPLIER = 1103515245
_LCG_INCREMENT = 12345
_LCG_MODULUS = 2**31


class _Shuffler:
    def __init__(self, seed: int) -> None:
        self._state = seed % _LCG_MODULUS

    def _draw(self, bound: int) -> int:
        self._state = (self._state * _LCG_MULTIPLIER + _LCG_INCREMENT) % _LCG_MODULUS
        return (self._state >> 16) % bound

    def shuffle(self, items: list[Link]) -> None:
        for index in range(len(items) - 1, 0, -1):
            other = self._draw(index + 1)
            items[index], items[other] = items[other], items[index]


def _link_host(link: Link, hosts: Collection[str]) -> str | None:
    if link.target in hosts:
        return link.target
    if link.source in hosts:
        return link.source
    return None


def _link_cycle(
    links: Sequence[Link],
    hosts: Collection[str],
    kinds: Sequence[FaultKind],
    shuffler: _Shuffler,
) -> list[Link]:
    host_links = [link for link in links if _link_host(link, hosts) is not None]
    switch_links = [link for link in links if _link_host(link, hosts) is None]
    shuffler.shuffle(host_links)
    shuffler.shuffle(switch_links)
    if "loss" not in kinds:
        return host_links
    return [*host_links, *switch_links]


def _fault_on(
    link: Link,
    hosts: Collection[str],
    kind: FaultKind,
    *,
    duration_seconds: int,
    loss_percent: int,
) -> Fault:
    host = _link_host(link, hosts)
    if host is None or kind == "loss":
        return Fault(
            kind="loss", link=link, duration_seconds=duration_seconds, loss_percent=loss_percent
        )
    return Fault(
        kind="host_down",
        link=link,
        duration_seconds=duration_seconds,
        loss_percent=loss_percent,
        host=host,
    )


def plan_faults(
    links: Sequence[Link],
    *,
    hosts: Collection[str],
    count: int,
    kinds: Sequence[FaultKind] = DEFAULT_KINDS,
    duration_seconds: int,
    loss_percent: int,
    seed: int,
) -> tuple[Fault, ...]:
    if not links:
        raise ValueError("links must not be empty")
    if count < 1:
        raise ValueError("count must be positive")
    if not kinds:
        raise ValueError("kinds must not be empty")
    if duration_seconds < 1:
        raise ValueError("duration_seconds must be positive")
    if not 1 <= loss_percent <= 100:
        raise ValueError("loss_percent must be between 1 and 100")
    if "loss" not in kinds and all(_link_host(link, hosts) is None for link in links):
        raise ValueError("host_down faults need at least one link that touches a host")
    shuffler = _Shuffler(seed)
    planned: list[Fault] = []
    cycle: list[Link] = []
    for index in range(count):
        if not cycle:
            cycle = _link_cycle(links, hosts, kinds, shuffler)
        planned.append(
            _fault_on(
                cycle.pop(0),
                hosts,
                kinds[index % len(kinds)],
                duration_seconds=duration_seconds,
                loss_percent=loss_percent,
            )
        )
    return tuple(planned)


def _hosts_behind(switch: str, spec: TopologySpec) -> list[str]:
    hosts = set(spec.hosts)
    return [
        host
        for link in spec.links
        for host in (link.source, link.target)
        if host in hosts and switch in (link.source, link.target)
    ]


def choose_probe_host(fault: Fault, spec: TopologySpec) -> str:
    siblings = [host for host in _hosts_behind(fault.switch, spec) if host != fault.host]
    others = [host for host in spec.hosts if host != fault.host]
    candidates = siblings or others
    if not candidates:
        raise ValueError(f"no other host can probe {fault.host}")
    return candidates[0]


def probe_commands(
    *, target_ip: str, target_mac: str, interface: str, duration_seconds: int
) -> tuple[tuple[str, ...], ...]:
    pin_neighbour = (
        "ip",
        "neigh",
        "replace",
        target_ip,
        "lladdr",
        target_mac,
        "dev",
        interface,
        "nud",
        "permanent",
    )
    flood = ("ping", "-f", "-q", "-w", str(duration_seconds), "-s", "1000", target_ip)
    return (pin_neighbour, flood)


def probe_cleanup_commands(*, target_ip: str, interface: str) -> tuple[str, ...]:
    return ("ip", "neigh", "del", target_ip, "dev", interface)


def describe_fault(fault: Fault) -> str:
    if fault.kind == "loss":
        link = f"{fault.link.source} <-> {fault.link.target}"
        return f"loss {fault.loss_percent}% on {link} for {fault.duration_seconds}s"
    return f"host down {fault.host} behind {fault.switch} for {fault.duration_seconds}s"


@dataclass(frozen=True, slots=True)
class Schedule:
    traffic_at: float | None = None
    fault_at: float | None = None
    fault_until: float | None = None

    @classmethod
    def start(cls, now: float, *, traffic: bool, first_fault_in: int | None) -> Self:
        return cls(
            traffic_at=now if traffic else None,
            fault_at=None if first_fault_in is None else now + first_fault_in,
        )

    def next_event(self) -> tuple[ScheduledEvent, float] | None:
        candidates: list[tuple[ScheduledEvent, float | None]] = [
            ("traffic", self.traffic_at),
            ("fault_end", self.fault_until),
            ("fault_start", self.fault_at),
        ]
        due = [(event, at) for event, at in candidates if at is not None]
        if not due:
            return None
        return min(due, key=lambda item: item[1])

    def traffic_launched(self, now: float, period_seconds: int) -> Self:
        return type(self)(
            traffic_at=now + period_seconds,
            fault_at=self.fault_at,
            fault_until=self.fault_until,
        )

    def fault_applied(self, now: float, duration_seconds: int) -> Self:
        return type(self)(
            traffic_at=self.traffic_at,
            fault_at=None,
            fault_until=now + duration_seconds,
        )

    def fault_cleared(self, now: float, period_seconds: int) -> Self:
        return type(self)(
            traffic_at=self.traffic_at,
            fault_at=now + period_seconds,
            fault_until=None,
        )
