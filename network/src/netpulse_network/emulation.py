import socket
import threading

from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

from netpulse_network.config import NetworkConfig
from netpulse_network.topology import TopologySpec


def build_network(spec: TopologySpec, config: NetworkConfig) -> Mininet:
    controller_ip = socket.gethostbyname(config.controller_host)
    network = Mininet(
        controller=None,
        switch=OVSSwitch,
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
        network.addLink(link.source, link.target)
    return network


def run(spec: TopologySpec, config: NetworkConfig, stop: threading.Event) -> None:
    setLogLevel("info")
    network = build_network(spec, config)
    network.build()
    network.start()
    try:
        network.waitConnected(timeout=30)
        loss = network.pingAll(timeout="1")
        info(f"*** Initial reachability check: {loss}% packet loss\n")
        stop.wait()
    finally:
        network.stop()
