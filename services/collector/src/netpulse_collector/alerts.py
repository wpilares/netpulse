import logging
from collections.abc import Iterable, Mapping, Sequence
from datetime import timedelta
from typing import Protocol

from netpulse_core import AlertEvent, AlertState, Baseline, BaselineKey

logger = logging.getLogger(__name__)


class AlertWriteError(Exception):
    pass


class AlertReadError(Exception):
    pass


class AlertRepository(Protocol):
    async def load_open(self) -> tuple[AlertState, ...]: ...

    async def apply(self, events: Sequence[AlertEvent]) -> None: ...

    async def purge_resolved(self, older_than: timedelta) -> int: ...


class BaselineRepository(Protocol):
    async def load(self) -> dict[BaselineKey, Baseline]: ...

    async def save(self, baselines: Mapping[BaselineKey, Baseline]) -> None: ...

    async def delete(self, keys: Iterable[BaselineKey]) -> None: ...


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
    async def load_open(self) -> tuple[AlertState, ...]:
        return ()

    async def apply(self, events: Sequence[AlertEvent]) -> None:
        logger.info("skipping persistence of %d alert events", len(events))

    async def purge_resolved(self, older_than: timedelta) -> int:
        return 0


class LoggingBaselineRepository:
    async def load(self) -> dict[BaselineKey, Baseline]:
        return {}

    async def save(self, baselines: Mapping[BaselineKey, Baseline]) -> None:
        logger.debug("skipping persistence of %d baselines", len(baselines))

    async def delete(self, keys: Iterable[BaselineKey]) -> None:
        logger.debug("skipping deletion of %d baselines", len(tuple(keys)))


class LoggingAlertNotifier:
    async def notify(self, events: Sequence[AlertEvent]) -> None:
        for event in events:
            logger.warning("alert %s", describe_event(event))
