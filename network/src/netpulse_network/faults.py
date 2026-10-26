from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal, Self

from netpulse_network.topology import Link

FaultKind = Literal["loss", "link_down"]
ScheduledEvent = Literal["traffic", "fault_start", "fault_end"]

DEFAULT_KINDS: tuple[FaultKind, ...] = ("loss", "link_down")


@dataclass(frozen=True, slots=True)
class Fault:
    kind: FaultKind
    link: Link
    duration_seconds: int
    loss_percent: int


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


def _touches_host(link: Link, hosts: Collection[str]) -> bool:
    return link.source in hosts or link.target in hosts


def _link_cycle(links: Sequence[Link], hosts: Collection[str], shuffler: _Shuffler) -> list[Link]:
    host_links = [link for link in links if _touches_host(link, hosts)]
    switch_links = [link for link in links if not _touches_host(link, hosts)]
    shuffler.shuffle(host_links)
    shuffler.shuffle(switch_links)
    return [*host_links, *switch_links]


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
    shuffler = _Shuffler(seed)
    planned: list[Fault] = []
    cycle: list[Link] = []
    for index in range(count):
        if not cycle:
            cycle = _link_cycle(links, hosts, shuffler)
        planned.append(
            Fault(
                kind=kinds[index % len(kinds)],
                link=cycle.pop(0),
                duration_seconds=duration_seconds,
                loss_percent=loss_percent,
            )
        )
    return tuple(planned)


def describe_fault(fault: Fault) -> str:
    link = f"{fault.link.source} <-> {fault.link.target}"
    if fault.kind == "loss":
        return f"loss {fault.loss_percent}% on {link} for {fault.duration_seconds}s"
    return f"link down {link} for {fault.duration_seconds}s"


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
