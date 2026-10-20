import os
from datetime import UTC, datetime

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

from netpulse_controller.rest import create_rest_server
from netpulse_controller.settings import ControllerSettings
from netpulse_controller.stats_store import PortCounters, StatsStore


class NetPulseMonitor(app_manager.OSKenApp):
    OFP_VERSIONS = (ofproto_v1_3.OFP_VERSION,)

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

    def _request_stats_forever(self) -> None:
        while True:
            for datapath in tuple(self._datapaths.values()):
                parser = datapath.ofproto_parser
                datapath.send_msg(
                    parser.OFPPortStatsRequest(datapath, 0, datapath.ofproto.OFPP_ANY)
                )
            hub.sleep(self._settings.stats_interval_seconds)
