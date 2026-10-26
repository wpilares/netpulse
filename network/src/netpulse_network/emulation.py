import socket
import threading
from collections.abc import Iterator

from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

from netpulse_network.config import NetworkConfig
from netpulse_network.topology import TopologySpec
from netpulse_network.traffic import (
    TrafficRound,
    iperf_client_command,
    iperf_server_command,
    plan_rounds,
    tournament_rounds,
)


def build_network(spec: TopologySpec, config: NetworkConfig) -> Mininet:
    controller_ip = socket.gethostbyname(config.controller_host)
    network = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
        build=False,
    )
    network.addController(
        "c0",
        controller=RemoteController,
        ip=controller_ip,
        port=config.controller_port,
    )
    for switch in spec.switches:
        network.addSwitch(
            switch,
            dpid=spec.datapath_id(switch),
            datapath=config.datapath,
            protocols="OpenFlow13",
        )
    for host in spec.hosts:
        network.addHost(host)
    for link in spec.links:
        network.addLink(link.source, link.target, bw=spec.link_bandwidth_mbps)
    return network


def _rounds(spec: TopologySpec, config: NetworkConfig) -> Iterator[TrafficRound]:
    generation = 0
    while True:
        yield from plan_rounds(
            spec.hosts,
            rounds=max(1, tournament_rounds(len(spec.hosts))),
            min_mbps=config.traffic_min_mbps,
            max_mbps=config.traffic_max_mbps,
            duration_seconds=config.traffic_duration_seconds,
            seed=config.traffic_seed + generation,
        )
        generation += 1


def _shell(command: tuple[str, ...]) -> str:
    return " ".join(command)


def _start_servers(network: Mininet, spec: TopologySpec) -> None:
    for name in spec.hosts:
        network.get(name).cmd(_shell(iperf_server_command()))
    info(f"*** Started iperf3 servers on {len(spec.hosts)} hosts\n")


def _stop_traffic(network: Mininet, spec: TopologySpec) -> None:
    for name in spec.hosts:
        network.get(name).cmd("pkill -x iperf3")


def _launch_round(network: Mininet, traffic_round: TrafficRound) -> None:
    for flow in traffic_round.flows:
        server_ip = str(network.get(flow.server).IP())
        command = _shell(iperf_client_command(server_ip, flow))
        network.get(flow.client).cmd(f"{command} > /dev/null 2>&1 &")
        info(
            f"*** {flow.client} -> {flow.server}: {flow.bandwidth_mbps} Mbit/s "
            f"for {flow.duration_seconds}s\n"
        )


def _generate_traffic(
    network: Mininet, spec: TopologySpec, config: NetworkConfig, stop: threading.Event
) -> None:
    _start_servers(network, spec)
    rounds = _rounds(spec, config)
    try:
        while not stop.is_set():
            _launch_round(network, next(rounds))
            stop.wait(config.traffic_round_seconds)
    finally:
        _stop_traffic(network, spec)


def run(spec: TopologySpec, config: NetworkConfig, stop: threading.Event) -> None:
    setLogLevel("info")
    network = build_network(spec, config)
    network.build()
    network.start()
    try:
        network.waitConnected(timeout=30)
        loss = network.pingAll(timeout="1")
        info(f"*** Initial reachability check: {loss}% packet loss\n")
        if config.traffic_enabled:
            _generate_traffic(network, spec, config, stop)
        else:
            stop.wait()
    finally:
        network.stop()
