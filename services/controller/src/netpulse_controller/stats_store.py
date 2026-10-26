import threading
from collections.abc import Iterable
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


@dataclass(frozen=True, slots=True)
class PortDescription:
    port_no: int
    name: str
    hw_addr: str

    def as_dict(self) -> dict[str, Json]:
        return dict(asdict(self))


@dataclass(frozen=True, slots=True)
class HostDescription:
    mac: str
    ipv4: tuple[str, ...]
    dpid: int
    port_no: int

    def as_dict(self) -> dict[str, Json]:
        return {"mac": self.mac, "ipv4": list(self.ipv4)}


type Link = tuple[int, int, int, int]


def _sorted_hosts(hosts: Iterable[HostDescription]) -> tuple[HostDescription, ...]:
    return tuple(sorted(hosts, key=lambda host: (host.port_no, host.mac)))


class StatsStore:
    def __init__(self) -> None:
        self._samples: dict[int, SwitchSample | None] = {}
        self._ports: dict[int, dict[int, PortDescription]] = {}
        self._links: set[Link] = set()
        self._hosts: dict[str, HostDescription] = {}
        self._lock = threading.Lock()

    def register(self, dpid: int) -> None:
        with self._lock:
            self._samples.setdefault(dpid, None)

    def unregister(self, dpid: int) -> None:
        with self._lock:
            self._samples.pop(dpid, None)
            self._ports.pop(dpid, None)
            self._links = {link for link in self._links if dpid not in (link[0], link[2])}
            self._hosts = {mac: host for mac, host in self._hosts.items() if host.dpid != dpid}

    def record_ports(self, dpid: int, ports: tuple[PortDescription, ...]) -> None:
        with self._lock:
            self._samples.setdefault(dpid, None)
            self._ports[dpid] = {port.port_no: port for port in ports}

    def record_port(self, dpid: int, port: PortDescription) -> None:
        with self._lock:
            self._samples.setdefault(dpid, None)
            self._ports.setdefault(dpid, {})[port.port_no] = port

    def remove_port(self, dpid: int, port_no: int) -> None:
        with self._lock:
            self._ports.get(dpid, {}).pop(port_no, None)
            self._hosts = {
                mac: host
                for mac, host in self._hosts.items()
                if (host.dpid, host.port_no) != (dpid, port_no)
            }

    def ports(self, dpid: int) -> tuple[PortDescription, ...]:
        with self._lock:
            return tuple(sorted(self._ports.get(dpid, {}).values(), key=lambda p: p.port_no))

    def record_host(self, host: HostDescription) -> None:
        with self._lock:
            self._hosts[host.mac] = host

    def remove_host(self, mac: str) -> None:
        with self._lock:
            self._hosts.pop(mac, None)

    def hosts(self, dpid: int) -> tuple[HostDescription, ...]:
        with self._lock:
            return _sorted_hosts(host for host in self._hosts.values() if host.dpid == dpid)

    def record_link(self, src_dpid: int, src_port: int, dst_dpid: int, dst_port: int) -> None:
        with self._lock:
            self._links.add((src_dpid, src_port, dst_dpid, dst_port))

    def remove_link(self, src_dpid: int, src_port: int, dst_dpid: int, dst_port: int) -> None:
        with self._lock:
            self._links.discard((src_dpid, src_port, dst_dpid, dst_port))

    def links(self) -> tuple[Link, ...]:
        with self._lock:
            return tuple(sorted(self._links))

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

    def topology_report(self) -> dict[str, Json]:
        with self._lock:
            dpids = sorted(self._samples)
            ports = {
                dpid: sorted(self._ports.get(dpid, {}).values(), key=lambda p: p.port_no)
                for dpid in dpids
            }
            links = sorted(self._links)
            hosts = _sorted_hosts(self._hosts.values())
        switches: list[Json] = [
            {
                "dpid": dpid,
                "ports": [
                    {
                        **port.as_dict(),
                        "hosts": [
                            host.as_dict()
                            for host in hosts
                            if (host.dpid, host.port_no) == (dpid, port.port_no)
                        ],
                    }
                    for port in ports[dpid]
                ],
            }
            for dpid in dpids
        ]
        return {
            "switches": switches,
            "links": [
                {
                    "src": {"dpid": src_dpid, "port_no": src_port},
                    "dst": {"dpid": dst_dpid, "port_no": dst_port},
                }
                for src_dpid, src_port, dst_dpid, dst_port in links
            ],
        }
