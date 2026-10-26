from datetime import UTC, datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from netpulse_api.app import create_app
from netpulse_api.topology import (
    ControllerHost,
    ControllerLink,
    ControllerLinkEnd,
    ControllerPort,
    ControllerSwitch,
    ControllerTopology,
    Topology,
    TopologyEdge,
    TopologyNode,
    TopologyUnavailableError,
    build_topology,
)
from netpulse_core import RESERVED_PORT_START

GENERATED_AT = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
LOCAL_PORT = 0xFFFFFFFE


def _switch(dpid: int, *port_nos: int) -> ControllerSwitch:
    return ControllerSwitch(
        dpid=dpid,
        ports=tuple(
            ControllerPort(
                port_no=port_no, name=f"s{dpid}-eth{port_no}", hw_addr="00:00:00:00:00:01"
            )
            for port_no in port_nos
        ),
    )


def _link(src_dpid: int, src_port: int, dst_dpid: int, dst_port: int) -> ControllerLink:
    return ControllerLink(
        src=ControllerLinkEnd(dpid=src_dpid, port_no=src_port),
        dst=ControllerLinkEnd(dpid=dst_dpid, port_no=dst_port),
    )


def _tree() -> ControllerTopology:
    return ControllerTopology(
        switches=(_switch(3, 1, 2, 3), _switch(1, 1, 2), _switch(2, 1, 2, 3)),
        links=(
            _link(2, 3, 1, 1),
            _link(1, 1, 2, 3),
            _link(1, 2, 3, 3),
            _link(3, 3, 1, 2),
        ),
    )


def test_tree_becomes_switch_and_host_nodes_with_undirected_edges() -> None:
    topology = build_topology(_tree(), generated_at=GENERATED_AT)

    assert topology.generated_at == GENERATED_AT
    assert [node.id for node in topology.nodes] == [
        "s:1",
        "s:2",
        "s:3",
        "h:2:1",
        "h:2:2",
        "h:3:1",
        "h:3:2",
    ]
    assert topology.nodes[0] == TopologyNode(
        id="s:1", kind="switch", dpid=1, port_no=None, label="s1", address=None, mac=None
    )
    assert topology.nodes[3] == TopologyNode(
        id="h:2:1", kind="host", dpid=2, port_no=1, label="s2-eth1", address=None, mac=None
    )
    assert topology.edges == (
        TopologyEdge(source="s:1", target="s:2", source_port=1, target_port=3),
        TopologyEdge(source="s:1", target="s:3", source_port=2, target_port=3),
        TopologyEdge(source="s:2", target="h:2:1", source_port=1, target_port=None),
        TopologyEdge(source="s:2", target="h:2:2", source_port=2, target_port=None),
        TopologyEdge(source="s:3", target="h:3:1", source_port=1, target_port=None),
        TopologyEdge(source="s:3", target="h:3:2", source_port=2, target_port=None),
    )


def test_one_directed_link_is_enough_and_the_lower_dpid_is_the_source() -> None:
    controller = ControllerTopology(
        switches=(_switch(1, 1), _switch(2, 1)), links=(_link(2, 1, 1, 1),)
    )

    topology = build_topology(controller, generated_at=GENERATED_AT)

    assert topology.edges == (
        TopologyEdge(source="s:1", target="s:2", source_port=1, target_port=1),
    )
    assert [node.kind for node in topology.nodes] == ["switch", "switch"]


def test_reserved_ports_never_become_hosts() -> None:
    controller = ControllerTopology(
        switches=(_switch(1, 1, RESERVED_PORT_START, LOCAL_PORT),), links=()
    )

    topology = build_topology(controller, generated_at=GENERATED_AT)

    assert [node.id for node in topology.nodes] == ["s:1", "h:1:1"]


def test_links_to_unknown_switches_are_dropped() -> None:
    controller = ControllerTopology(switches=(_switch(1, 1),), links=(_link(1, 1, 9, 1),))

    topology = build_topology(controller, generated_at=GENERATED_AT)

    assert topology.edges == (
        TopologyEdge(source="s:1", target="h:1:1", source_port=1, target_port=None),
    )


def test_empty_controller_topology_yields_no_nodes() -> None:
    topology = build_topology(ControllerTopology(switches=(), links=()), generated_at=GENERATED_AT)

    assert topology == Topology(generated_at=GENERATED_AT, nodes=(), edges=())


def test_host_label_falls_back_to_the_port_number() -> None:
    controller = ControllerTopology(
        switches=(
            ControllerSwitch(
                dpid=5, ports=(ControllerPort(port_no=7, name="", hw_addr="00:00:00:00:00:05"),)
            ),
        ),
        links=(),
    )

    topology = build_topology(controller, generated_at=GENERATED_AT)

    assert topology.nodes[1].label == "h5:7"


def _host(mac: str, *ipv4: str) -> ControllerHost:
    return ControllerHost(mac=mac, ipv4=ipv4)


def _hosted_switch(*hosts: ControllerHost) -> ControllerTopology:
    port = ControllerPort(port_no=1, name="s1-eth1", hw_addr="00:00:00:00:00:01", hosts=hosts)
    return ControllerTopology(switches=(ControllerSwitch(dpid=1, ports=(port,)),), links=())


def test_host_nodes_are_labelled_by_their_first_ipv4_address() -> None:
    controller = _hosted_switch(_host("00:00:00:00:00:11", "10.0.0.1", "10.0.0.101"))

    topology = build_topology(controller, generated_at=GENERATED_AT)

    assert topology.nodes[1] == TopologyNode(
        id="h:1:1",
        kind="host",
        dpid=1,
        port_no=1,
        label="10.0.0.1",
        address="10.0.0.1",
        mac="00:00:00:00:00:11",
    )


def test_a_host_without_ipv4_keeps_the_port_label_but_exposes_its_mac() -> None:
    controller = _hosted_switch(_host("00:00:00:00:00:11"))

    topology = build_topology(controller, generated_at=GENERATED_AT)

    assert topology.nodes[1].label == "s1-eth1"
    assert topology.nodes[1].address is None
    assert topology.nodes[1].mac == "00:00:00:00:00:11"


def test_several_hosts_on_one_port_show_the_first_address_and_a_count() -> None:
    controller = _hosted_switch(
        _host("00:00:00:00:00:12"),
        _host("00:00:00:00:00:13", "10.0.0.3"),
        _host("00:00:00:00:00:14", "10.0.0.4"),
    )

    topology = build_topology(controller, generated_at=GENERATED_AT)

    assert topology.nodes[1].label == "10.0.0.3 +2"
    assert topology.nodes[1].address == "10.0.0.3"
    assert topology.nodes[1].mac == "00:00:00:00:00:13"


def test_controller_ports_default_to_no_hosts() -> None:
    port = ControllerPort(port_no=1, name="s1-eth1", hw_addr="00:00:00:00:00:01")

    assert port.hosts == ()


class StubTopologyQuery:
    def __init__(self, result: ControllerTopology | Exception) -> None:
        self.result = result

    async def fetch(self) -> ControllerTopology:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_topology_endpoint_returns_nodes_and_edges() -> None:
    client = TestClient(create_app(database_probe=None, topology_query=StubTopologyQuery(_tree())))

    response = client.get("/api/v1/topology")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert Topology.model_validate(payload)
    assert payload["nodes"][0] == {
        "id": "s:1",
        "kind": "switch",
        "dpid": 1,
        "port_no": None,
        "label": "s1",
        "address": None,
        "mac": None,
    }
    assert payload["edges"][0] == {
        "source": "s:1",
        "target": "s:2",
        "source_port": 1,
        "target_port": 3,
    }
    assert len(payload["nodes"]) == 7
    assert len(payload["edges"]) == 6


def test_topology_endpoint_is_unavailable_without_a_controller() -> None:
    client = TestClient(create_app(database_probe=None))

    response = client.get("/api/v1/topology")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "controller is not configured"}


@pytest.mark.parametrize("error", [TopologyUnavailableError("boom")])
def test_topology_endpoint_is_unavailable_when_the_controller_fails(error: Exception) -> None:
    client = TestClient(create_app(database_probe=None, topology_query=StubTopologyQuery(error)))

    response = client.get("/api/v1/topology")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "controller is unavailable"}
