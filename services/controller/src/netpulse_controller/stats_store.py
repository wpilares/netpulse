import threading
from dataclasses import asdict, dataclass
from datetime import datetime

type JsonScalar = str | int | float | bool | None
type Json = JsonScalar | list[Json] | dict[str, Json]


@dataclass(frozen=True, slots=True)
class PortCounters:
    port_no: int
    rx_packets: int
    tx_packets: int
    rx_bytes: int
    tx_bytes: int
    rx_dropped: int
    tx_dropped: int
    rx_errors: int
    tx_errors: int
    duration_sec: int

    def as_dict(self) -> dict[str, Json]:
        return dict(asdict(self))


@dataclass(frozen=True, slots=True)
class SwitchSample:
    collected_at: datetime
    ports: tuple[PortCounters, ...]


class StatsStore:
    def __init__(self) -> None:
        self._samples: dict[int, SwitchSample | None] = {}
        self._lock = threading.Lock()

    def register(self, dpid: int) -> None:
        with self._lock:
            self._samples.setdefault(dpid, None)

    def unregister(self, dpid: int) -> None:
        with self._lock:
            self._samples.pop(dpid, None)

    def switches(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(sorted(self._samples))

    def record(self, dpid: int, ports: tuple[PortCounters, ...], collected_at: datetime) -> None:
        ordered = tuple(sorted(ports, key=lambda port: port.port_no))
        with self._lock:
            if dpid in self._samples:
                self._samples[dpid] = SwitchSample(collected_at=collected_at, ports=ordered)

    def port_stats_report(self) -> dict[str, Json]:
        with self._lock:
            samples = sorted(self._samples.items())
        switches: list[Json] = [
            {
                "dpid": dpid,
                "collected_at": sample.collected_at.isoformat(),
                "ports": [port.as_dict() for port in sample.ports],
            }
            for dpid, sample in samples
            if sample is not None
        ]
        return {"switches": switches}
