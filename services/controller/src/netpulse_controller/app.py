import os
from datetime import UTC, datetime
from typing import ClassVar

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.controller import Datapath
from os_ken.controller.handler import (
    CONFIG_DISPATCHER,
    DEAD_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls,
)
from os_ken.lib import hub
from os_ken.ofproto import ofproto_v1_3
from os_ken.topology import event as topology_event
from os_ken.topology import switches as topology_switches

from netpulse_controller.rest import create_rest_server
from netpulse_controller.settings import ControllerSettings
from netpulse_controller.stats_store import PortCounters, PortDescription, StatsStore


def _describe_port(port: topology_switches.Port) -> PortDescription:
    name = port.name.decode("utf-8", "replace") if isinstance(port.name, bytes) else str(port.name)
    return PortDescription(port_no=int(port.port_no), name=name, hw_addr=str(port.hw_addr))


class NetPulseMonitor(app_manager.OSKenApp):
    OFP_VERSIONS = (ofproto_v1_3.OFP_VERSION,)
    _CONTEXTS: ClassVar[dict[str, type[app_manager.OSKenApp]]] = {
        "switches": topology_switches.Switches
    }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._settings = ControllerSettings.from_env(os.environ)
        self._store = StatsStore()
        self._datapaths: dict[int, Datapath] = {}
        rest_server = create_rest_server(
            self._store, self._settings.rest_host, self._settings.rest_port
        )
        self.threads.append(hub.spawn(rest_server.serve_forever))
        self.threads.append(hub.spawn(self._request_stats_forever))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def install_normal_forwarding(self, event: ofp_event.EventOFPSwitchFeatures) -> None:
        datapath = event.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(ofproto.OFPP_NORMAL)]
        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        datapath.send_msg(
            parser.OFPFlowMod(
                datapath=datapath,
                priority=0,
                match=parser.OFPMatch(),
                instructions=instructions,
            )
        )

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def track_datapath(self, event: ofp_event.EventOFPStateChange) -> None:
        datapath = event.datapath
        if datapath.id is None:
            return
        if event.state == MAIN_DISPATCHER:
            self._datapaths[datapath.id] = datapath
            self._store.register(datapath.id)
            self.logger.info("switch %016x connected", datapath.id)
        elif event.state == DEAD_DISPATCHER:
            self._datapaths.pop(datapath.id, None)
            self._store.unregister(datapath.id)
            self.logger.info("switch %016x disconnected", datapath.id)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def record_port_stats(self, event: ofp_event.EventOFPPortStatsReply) -> None:
        ports = tuple(
            PortCounters(
                port_no=stat.port_no,
                rx_packets=stat.rx_packets,
                tx_packets=stat.tx_packets,
                rx_bytes=stat.rx_bytes,
                tx_bytes=stat.tx_bytes,
                rx_dropped=stat.rx_dropped,
                tx_dropped=stat.tx_dropped,
                rx_errors=stat.rx_errors,
                tx_errors=stat.tx_errors,
                duration_sec=stat.duration_sec,
            )
            for stat in event.msg.body
        )
        self._store.record(event.msg.datapath.id, ports, datetime.now(UTC))

    @set_ev_cls(topology_event.EventSwitchEnter)
    def record_switch_ports(self, event: topology_event.EventSwitchEnter) -> None:
        switch = event.switch
        ports = tuple(_describe_port(port) for port in switch.ports if not port.is_reserved())
        self._store.record_ports(switch.dp.id, ports)

    @set_ev_cls(topology_event.EventSwitchLeave)
    def forget_switch(self, event: topology_event.EventSwitchLeave) -> None:
        self._store.unregister(event.switch.dp.id)

    @set_ev_cls([topology_event.EventPortAdd, topology_event.EventPortModify])
    def record_port(self, event: topology_event.EventPortBase) -> None:
        if event.port.is_reserved():
            return
        self._store.record_port(event.port.dpid, _describe_port(event.port))

    @set_ev_cls(topology_event.EventPortDelete)
    def forget_port(self, event: topology_event.EventPortDelete) -> None:
        self._store.remove_port(event.port.dpid, event.port.port_no)

    @set_ev_cls(topology_event.EventLinkAdd)
    def record_link(self, event: topology_event.EventLinkAdd) -> None:
        link = event.link
        self._store.record_link(link.src.dpid, link.src.port_no, link.dst.dpid, link.dst.port_no)
        self.logger.info(
            "link %s:%s -> %s:%s", link.src.dpid, link.src.port_no, link.dst.dpid, link.dst.port_no
        )

    @set_ev_cls(topology_event.EventLinkDelete)
    def forget_link(self, event: topology_event.EventLinkDelete) -> None:
        link = event.link
        self._store.remove_link(link.src.dpid, link.src.port_no, link.dst.dpid, link.dst.port_no)

    def _request_stats_forever(self) -> None:
        while True:
            for datapath in tuple(self._datapaths.values()):
                parser = datapath.ofproto_parser
                datapath.send_msg(
                    parser.OFPPortStatsRequest(datapath, 0, datapath.ofproto.OFPP_ANY)
                )
            hub.sleep(self._settings.stats_interval_seconds)
