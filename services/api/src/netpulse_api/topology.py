from datetime import datetime
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict

from netpulse_core import DatapathId, PortNumber, is_reserved_port

NodeKind = Literal["switch", "host"]


class TopologyUnavailableError(Exception):
    pass


class ControllerHost(BaseModel):
    model_config = ConfigDict(frozen=True)

    mac: str
    ipv4: tuple[str, ...] = ()


class ControllerPort(BaseModel):
    model_config = ConfigDict(frozen=True)

    port_no: PortNumber
    name: str
    hw_addr: str
    curr_speed_bps: int | None = None
    hosts: tuple[ControllerHost, ...] = ()


class ControllerSwitch(BaseModel):
    model_config = ConfigDict(frozen=True)

    dpid: DatapathId
    ports: tuple[ControllerPort, ...]


class ControllerLinkEnd(BaseModel):
    model_config = ConfigDict(frozen=True)

    dpid: DatapathId
    port_no: PortNumber


class ControllerLink(BaseModel):
    model_config = ConfigDict(frozen=True)

    src: ControllerLinkEnd
    dst: ControllerLinkEnd


class ControllerTopology(BaseModel):
    model_config = ConfigDict(frozen=True)

    switches: tuple[ControllerSwitch, ...]
    links: tuple[ControllerLink, ...]


class TopologyQuery(Protocol):
    async def fetch(self) -> ControllerTopology: ...


class TopologyNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: NodeKind
    dpid: DatapathId | None
    port_no: PortNumber | None
    label: str
    address: str | None = None
    mac: str | None = None


class TopologyEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    source_port: PortNumber | None
    target_port: PortNumber | None
    source_speed_bps: int | None = None
    target_speed_bps: int | None = None


class Topology(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: AwareDatetime
    nodes: tuple[TopologyNode, ...]
    edges: tuple[TopologyEdge, ...]


type PortRef = tuple[int, int]
type SwitchPair = tuple[PortRef, PortRef]


def switch_node_id(dpid: int) -> str:
    return f"s:{dpid}"


def host_node_id(dpid: int, port_no: int) -> str:
    return f"h:{dpid}:{port_no}"


def port_speeds(controller: ControllerTopology) -> dict[PortRef, int]:
    return {
        (switch.dpid, port.port_no): port.curr_speed_bps
        for switch in controller.switches
        for port in switch.ports
        if port.curr_speed_bps
    }


def _switch_pairs(controller: ControllerTopology, known: set[int]) -> set[SwitchPair]:
    pairs: set[SwitchPair] = set()
    for link in controller.links:
        src: PortRef = (link.src.dpid, link.src.port_no)
        dst: PortRef = (link.dst.dpid, link.dst.port_no)
        if src[0] in known and dst[0] in known:
            pairs.add((min(src, dst), max(src, dst)))
    return pairs


def _primary_host(port: ControllerPort) -> ControllerHost | None:
    addressed = (host for host in port.hosts if host.ipv4)
    return next(addressed, port.hosts[0] if port.hosts else None)


def _host_label(switch: ControllerSwitch, port: ControllerPort, host: ControllerHost | None) -> str:
    if host is None or not host.ipv4:
        return port.name or f"h{switch.dpid}:{port.port_no}"
    others = len(port.hosts) - 1
    return host.ipv4[0] if others == 0 else f"{host.ipv4[0]} +{others}"


def _host_node(switch: ControllerSwitch, port: ControllerPort) -> TopologyNode:
    host = _primary_host(port)
    return TopologyNode(
        id=host_node_id(switch.dpid, port.port_no),
        kind="host",
        dpid=switch.dpid,
        port_no=port.port_no,
        label=_host_label(switch, port, host),
        address=host.ipv4[0] if host is not None and host.ipv4 else None,
        mac=None if host is None else host.mac,
    )


def build_topology(controller: ControllerTopology, *, generated_at: datetime) -> Topology:
    switches = sorted(controller.switches, key=lambda switch: switch.dpid)
    pairs = _switch_pairs(controller, {switch.dpid for switch in switches})
    linked: set[PortRef] = {end for pair in pairs for end in pair}
    speeds = port_speeds(controller)

    nodes: list[TopologyNode] = [
        TopologyNode(
            id=switch_node_id(switch.dpid),
            kind="switch",
            dpid=switch.dpid,
            port_no=None,
            label=f"s{switch.dpid}",
        )
        for switch in switches
    ]
    edges: list[TopologyEdge] = [
        TopologyEdge(
            source=switch_node_id(src_dpid),
            target=switch_node_id(dst_dpid),
            source_port=src_port,
            target_port=dst_port,
            source_speed_bps=speeds.get((src_dpid, src_port)),
            target_speed_bps=speeds.get((dst_dpid, dst_port)),
        )
        for (src_dpid, src_port), (dst_dpid, dst_port) in sorted(pairs)
    ]
    for switch in switches:
        for port in sorted(switch.ports, key=lambda port: port.port_no):
            if is_reserved_port(port.port_no) or (switch.dpid, port.port_no) in linked:
                continue
            host = _host_node(switch, port)
            nodes.append(host)
            edges.append(
                TopologyEdge(
                    source=switch_node_id(switch.dpid),
                    target=host.id,
                    source_port=port.port_no,
                    target_port=None,
                    source_speed_bps=speeds.get((switch.dpid, port.port_no)),
                    target_speed_bps=None,
                )
            )
    return Topology(generated_at=generated_at, nodes=tuple(nodes), edges=tuple(edges))
