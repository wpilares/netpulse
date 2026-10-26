import socket
import threading
import time
from collections.abc import Iterator
from typing import Literal

from mininet.link import TCIntf, TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

from netpulse_network.config import NetworkConfig
from netpulse_network.faults import Fault, Schedule, describe_fault, plan_faults
from netpulse_network.topology import Link, TopologySpec
from netpulse_network.traffic import (
    TrafficRound,
    disable_tx_offload_command,
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
        autoStaticArp=False,
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


def _faults(spec: TopologySpec, config: NetworkConfig) -> Iterator[Fault]:
    generation = 0
    while True:
        yield from plan_faults(
            spec.links,
            hosts=spec.hosts,
            count=len(spec.links),
            duration_seconds=config.fault_duration_seconds,
            loss_percent=config.fault_loss_percent,
            seed=config.fault_seed + generation,
        )
        generation += 1


def _shell(command: tuple[str, ...]) -> str:
    return " ".join(command)


def _disable_tx_offload(network: Mininet) -> None:
    for node in (*network.hosts, *network.switches):
        interfaces = [intf.name for intf in node.intfList() if intf.name != "lo"]
        for interface in interfaces:
            node.cmd(_shell(disable_tx_offload_command(interface)))
        info(f"*** Disabled TX checksum offload on {len(interfaces)} interfaces of {node.name}\n")


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


def _link_interfaces(network: Mininet, link: Link) -> list[TCIntf]:
    source, target = network.get(link.source), network.get(link.target)
    return [
        interface
        for mininet_link in network.linksBetween(source, target)
        for interface in (mininet_link.intf1, mininet_link.intf2)
    ]


def _set_link_loss(network: Mininet, spec: TopologySpec, link: Link, loss_percent: int) -> None:
    for interface in _link_interfaces(network, link):
        interface.config(bw=spec.link_bandwidth_mbps, loss=loss_percent, txo=False)
    info("\n")


def _set_host_interface(network: Mininet, host: str, status: Literal["up", "down"]) -> None:
    network.get(host).intf().ifconfig(status)


def _switch_port_facing(network: Mininet, host: str) -> str:
    host_interface = network.get(host).intf()
    link = host_interface.link
    peer = link.intf2 if link.intf1 is host_interface else link.intf1
    return str(peer.name)


def _apply_fault(network: Mininet, spec: TopologySpec, fault: Fault) -> None:
    if fault.kind == "loss":
        _set_link_loss(network, spec, fault.link, fault.loss_percent)
        info(f"*** Fault: {describe_fault(fault)}\n")
    elif fault.host is not None:
        _set_host_interface(network, fault.host, "down")
        port = _switch_port_facing(network, fault.host)
        info(f"*** Fault: {describe_fault(fault)} ({port} counts the drops)\n")


def _clear_fault(network: Mininet, spec: TopologySpec, fault: Fault) -> None:
    if fault.kind == "loss":
        _set_link_loss(network, spec, fault.link, 0)
    elif fault.host is not None:
        _set_host_interface(network, fault.host, "up")
    info("*** Fault cleared\n")


def _run_schedule(
    network: Mininet, spec: TopologySpec, config: NetworkConfig, stop: threading.Event
) -> None:
    rounds = _rounds(spec, config)
    faults = _faults(spec, config)
    inject_faults = config.fault_enabled and bool(spec.links)
    schedule = Schedule.start(
        time.monotonic(),
        traffic=config.traffic_enabled,
        first_fault_in=config.fault_period_seconds if inject_faults else None,
    )
    active_fault: Fault | None = None
    if config.traffic_enabled:
        _start_servers(network, spec)
    try:
        while not stop.is_set():
            due = schedule.next_event()
            if due is None:
                stop.wait()
                break
            event, at = due
            if stop.wait(max(0.0, at - time.monotonic())):
                break
            now = time.monotonic()
            if event == "traffic":
                _launch_round(network, next(rounds))
                schedule = schedule.traffic_launched(now, config.traffic_round_seconds)
            elif event == "fault_start":
                active_fault = next(faults)
                _apply_fault(network, spec, active_fault)
                schedule = schedule.fault_applied(now, active_fault.duration_seconds)
            else:
                if active_fault is not None:
                    _clear_fault(network, spec, active_fault)
                active_fault = None
                schedule = schedule.fault_cleared(now, config.fault_period_seconds)
    finally:
        if active_fault is not None:
            _clear_fault(network, spec, active_fault)
        if config.traffic_enabled:
            _stop_traffic(network, spec)


def run(spec: TopologySpec, config: NetworkConfig, stop: threading.Event) -> None:
    setLogLevel("info")
    network = build_network(spec, config)
    network.build()
    network.start()
    try:
        _disable_tx_offload(network)
        network.waitConnected(timeout=30)
        loss = network.pingAll(timeout="1")
        info(f"*** Initial reachability check: {loss}% packet loss\n")
        _run_schedule(network, spec, config, stop)
    finally:
        network.stop()
