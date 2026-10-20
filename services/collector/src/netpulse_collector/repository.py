import logging
from typing import Protocol

from netpulse_core import PortStatsReport

logger = logging.getLogger(__name__)


class PortStatsRepository(Protocol):
    async def save(self, report: PortStatsReport) -> None: ...


class LoggingPortStatsRepository:
    async def save(self, report: PortStatsReport) -> None:
        port_count = sum(len(switch.ports) for switch in report.switches)
        logger.info(
            "collected stats for %d ports across %d switches",
            port_count,
            len(report.switches),
        )
