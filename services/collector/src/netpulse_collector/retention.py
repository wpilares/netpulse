import logging
from datetime import timedelta

from netpulse_collector.alerts import AlertRepository, AlertWriteError
from netpulse_core import PortStatsReport

logger = logging.getLogger(__name__)


class RetentionObserver:
    def __init__(
        self, repository: AlertRepository, *, older_than: timedelta, every_cycles: int
    ) -> None:
        self._repository = repository
        self._older_than = older_than
        self._every_cycles = every_cycles
        self._cycles = 0

    async def observe(self, report: PortStatsReport) -> None:
        self._cycles += 1
        if self._cycles % self._every_cycles:
            return
        try:
            purged = await self._repository.purge_resolved(self._older_than)
        except AlertWriteError:
            logger.exception("purging resolved alerts failed")
            return
        logger.info("purged %d resolved alerts older than %s", purged, self._older_than)
