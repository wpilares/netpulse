from datetime import datetime
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict

from netpulse_core import DatapathId, PortNumber, is_reserved_port

NodeKind = Literal["switch", "host"]


class TopologyUnavailableError(Exception):
    pass


class ControllerPort(BaseModel):
    model_config = ConfigDict(frozen=True)

    port_no: PortNumber
    name: str
    hw_addr: str


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


class TopologyEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    source_port: PortNumber | None
    target_port: PortNumber | None


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


def _switch_pairs(controller: ControllerTopology, known: set[int]) -> set[SwitchPair]:
    pairs: set[SwitchPair] = set()
    for link in controller.links:
        src: PortRef = (link.src.dpid, link.src.port_no)
        dst: PortRef = (link.dst.dpid, link.dst.port_no)
        if src[0] in known and dst[0] in known:
            pairs.add((min(src, dst), max(src, dst)))
    return pairs


def _host_label(switch: ControllerSwitch, port: ControllerPort) -> str:
    return port.name or f"h{switch.dpid}:{port.port_no}"


def build_topology(controller: ControllerTopology, *, generated_at: datetime) -> Topology:
    switches = sorted(controller.switches, key=lambda switch: switch.dpid)
    pairs = _switch_pairs(controller, {switch.dpid for switch in switches})
    linked: set[PortRef] = {end for pair in pairs for end in pair}

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
        )
        for (src_dpid, src_port), (dst_dpid, dst_port) in sorted(pairs)
    ]
    for switch in switches:
        for port in sorted(switch.ports, key=lambda port: port.port_no):
            if is_reserved_port(port.port_no) or (switch.dpid, port.port_no) in linked:
                continue
            host_id = host_node_id(switch.dpid, port.port_no)
            nodes.append(
                TopologyNode(
                    id=host_id,
                    kind="host",
                    dpid=switch.dpid,
                    port_no=port.port_no,
                    label=_host_label(switch, port),
                )
            )
            edges.append(
                TopologyEdge(
                    source=switch_node_id(switch.dpid),
                    target=host_id,
                    source_port=port.port_no,
                    target_port=None,
                )
            )
    return Topology(generated_at=generated_at, nodes=tuple(nodes), edges=tuple(edges))
