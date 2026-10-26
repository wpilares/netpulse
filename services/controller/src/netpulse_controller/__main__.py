import logging
import os

from os_ken import cfg
from os_ken.base import app_manager

from netpulse_controller.app import NetPulseMonitor
from netpulse_controller.settings import ControllerSettings

APPLICATIONS = (NetPulseMonitor.__module__,)


def main() -> None:
    settings = ControllerSettings.from_env(os.environ)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg.CONF(args=[], project="os_ken")
    cfg.CONF.set_override("ofp_tcp_listen_port", settings.openflow_port)
    cfg.CONF.set_override("observe_links", True)
    app_manager.AppManager.run_apps(list(APPLICATIONS))


if __name__ == "__main__":
    main()
