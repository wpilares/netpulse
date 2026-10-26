from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrafficFlow:
    client: str
    server: str
    duration_seconds: int
    bandwidth_mbps: int


@dataclass(frozen=True, slots=True)
class TrafficRound:
    flows: tuple[TrafficFlow, ...]


def tournament_rounds(host_count: int) -> int:
    if host_count < 2:
        return 0
    return host_count - 1 if host_count % 2 == 0 else host_count


def _pairings(hosts: Sequence[str]) -> list[list[tuple[str, str]]]:
    seats: list[str | None] = list(hosts)
    if len(seats) % 2 == 1:
        seats.append(None)
    if len(seats) < 2:
        return [[]]
    pinned, rotating = seats[0], seats[1:]
    schedule: list[list[tuple[str, str]]] = []
    for round_index in range(len(seats) - 1):
        table = [pinned, *rotating]
        pairs: list[tuple[str, str]] = []
        for seat in range(len(table) // 2):
            left, right = table[seat], table[-1 - seat]
            if left is None or right is None:
                continue
            flipped = (round_index + seat) % 2 == 1
            pairs.append((right, left) if flipped else (left, right))
        schedule.append(pairs)
        rotating = [rotating[-1], *rotating[:-1]]
    return schedule


_LCG_MULTIPLIER = 1103515245
_LCG_INCREMENT = 12345
_LCG_MODULUS = 2**31


class _BandwidthWalk:
    def __init__(self, *, min_mbps: int, max_mbps: int, seed: int) -> None:
        self._min = min_mbps
        self._max = max_mbps
        self._state = seed % _LCG_MODULUS
        self._step = max(1, (max_mbps - min_mbps) // 3)
        self._value = min_mbps + self._draw(max_mbps - min_mbps + 1)

    def _draw(self, bound: int) -> int:
        self._state = (self._state * _LCG_MULTIPLIER + _LCG_INCREMENT) % _LCG_MODULUS
        return (self._state >> 16) % bound

    def next(self) -> int:
        delta = self._draw(2 * self._step + 1) - self._step
        self._value = min(self._max, max(self._min, self._value + delta))
        return self._value


def plan_rounds(
    hosts: Sequence[str],
    *,
    rounds: int,
    min_mbps: int,
    max_mbps: int,
    duration_seconds: int,
    seed: int,
) -> tuple[TrafficRound, ...]:
    if rounds < 1:
        raise ValueError("rounds must be positive")
    if min_mbps < 1:
        raise ValueError("min_mbps must be positive")
    if max_mbps < min_mbps:
        raise ValueError("max_mbps must be at least min_mbps")
    if duration_seconds < 1:
        raise ValueError("duration_seconds must be positive")
    schedule = _pairings(hosts)
    walk = _BandwidthWalk(min_mbps=min_mbps, max_mbps=max_mbps, seed=seed)
    planned: list[TrafficRound] = []
    for round_index in range(rounds):
        cycle, position = divmod(round_index, len(schedule))
        pairs = schedule[position]
        if cycle % 2 == 1:
            pairs = [(server, client) for client, server in pairs]
        flows = tuple(
            TrafficFlow(
                client=client,
                server=server,
                duration_seconds=duration_seconds,
                bandwidth_mbps=walk.next(),
            )
            for client, server in pairs
        )
        planned.append(TrafficRound(flows=flows))
    return tuple(planned)


_CONNECT_TIMEOUT_MS = 3000


def iperf_server_command() -> tuple[str, ...]:
    return ("iperf3", "-s", "-D")


def iperf_client_command(server_ip: str, flow: TrafficFlow) -> tuple[str, ...]:
    return (
        "iperf3",
        "-c",
        server_ip,
        "--connect-timeout",
        str(_CONNECT_TIMEOUT_MS),
        "-u",
        "-b",
        f"{flow.bandwidth_mbps}M",
        "-t",
        str(flow.duration_seconds),
    )


def disable_tx_offload_command(interface: str) -> tuple[str, ...]:
    return ("ethtool", "-K", interface, "tx", "off")
