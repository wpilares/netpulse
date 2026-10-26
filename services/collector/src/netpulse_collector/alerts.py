import logging
from collections.abc import Sequence
from typing import Protocol

from netpulse_core import AlertEvent

logger = logging.getLogger(__name__)


class AlertWriteError(Exception):
    pass


class AlertRepository(Protocol):
    async def apply(self, events: Sequence[AlertEvent]) -> None: ...


class AlertNotifier(Protocol):
    async def notify(self, events: Sequence[AlertEvent]) -> None: ...


def describe_event(event: AlertEvent) -> str:
    dpid, port_no, metric = event.state.key
    state = event.state
    return (
        f"{event.kind} {state.severity} alert dpid={dpid} port={port_no} metric={metric} "
        f"value={state.value:g} expected={state.expected:g} zscore={state.zscore:.2f}"
    )


class LoggingAlertRepository:
    async def apply(self, events: Sequence[AlertEvent]) -> None:
        logger.info("skipping persistence of %d alert events", len(events))


class LoggingAlertNotifier:
    async def notify(self, events: Sequence[AlertEvent]) -> None:
        for event in events:
            logger.warning("alert %s", describe_event(event))
