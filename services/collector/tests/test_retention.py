import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from netpulse_collector.alerts import AlertWriteError
from netpulse_collector.retention import RetentionObserver
from netpulse_core import AlertEvent, AlertState, PortStatsReport, SwitchPortStats

OLDER_THAN = timedelta(days=7)
EVERY_CYCLES = 3


class RecordingAlertRepository:
    def __init__(self, purged_per_call: int = 2) -> None:
        self.purged: list[timedelta] = []
        self._purged_per_call = purged_per_call

    async def load_open(self) -> tuple[AlertState, ...]:
        return ()

    async def apply(self, events: Sequence[AlertEvent]) -> None:
        raise AssertionError("retention never applies events")

    async def purge_resolved(self, older_than: timedelta) -> int:
        self.purged.append(older_than)
        return self._purged_per_call


class FailingAlertRepository:
    async def load_open(self) -> tuple[AlertState, ...]:
        return ()

    async def apply(self, events: Sequence[AlertEvent]) -> None:
        raise AssertionError("retention never applies events")

    async def purge_resolved(self, older_than: timedelta) -> int:
        raise AlertWriteError("alerts table locked")


def _report(cycle: int) -> PortStatsReport:
    collected_at = datetime(2026, 10, 20, 12, 0, tzinfo=UTC) + timedelta(seconds=5 * cycle)
    return PortStatsReport(switches=(SwitchPortStats(dpid=1, collected_at=collected_at, ports=()),))


async def test_observer_purges_resolved_alerts_every_n_cycles(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = RecordingAlertRepository()
    observer = RetentionObserver(repository, older_than=OLDER_THAN, every_cycles=EVERY_CYCLES)

    with caplog.at_level(logging.INFO, logger="netpulse_collector.retention"):
        for cycle in range(1, 2 * EVERY_CYCLES + 1):
            await observer.observe(_report(cycle))

    assert repository.purged == [OLDER_THAN, OLDER_THAN]
    assert caplog.text.count("purged 2 resolved alerts older than 7 days") == 2


async def test_observer_does_not_purge_before_the_first_due_cycle() -> None:
    repository = RecordingAlertRepository()
    observer = RetentionObserver(repository, older_than=OLDER_THAN, every_cycles=EVERY_CYCLES)

    for cycle in range(1, EVERY_CYCLES):
        await observer.observe(_report(cycle))

    assert repository.purged == []


async def test_observer_logs_purge_failures_and_keeps_counting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    observer = RetentionObserver(
        FailingAlertRepository(), older_than=OLDER_THAN, every_cycles=EVERY_CYCLES
    )

    with caplog.at_level(logging.ERROR, logger="netpulse_collector.retention"):
        for cycle in range(1, 2 * EVERY_CYCLES + 1):
            await observer.observe(_report(cycle))

    assert [record.getMessage() for record in caplog.records] == [
        "purging resolved alerts failed",
        "purging resolved alerts failed",
    ]
    assert "alerts table locked" in caplog.text
