import os
import signal
import threading
from types import FrameType

from netpulse_network.config import NetworkConfig
from netpulse_network.emulation import run
from netpulse_network.topology import build_tree


def main() -> None:
    config = NetworkConfig.from_env(os.environ)
    stop = threading.Event()

    def request_stop(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    spec = build_tree(
        depth=config.depth,
        fanout=config.fanout,
        link_bandwidth_mbps=config.link_bandwidth_mbps,
    )
    run(spec, config, stop)


if __name__ == "__main__":
    main()
