import logging
from collections.abc import Mapping, Sequence

from netpulse_collector.alerts import AlertNotifier, LoggingAlertNotifier
from netpulse_core import AlertEvent, AlertRoute, route_events

logger = logging.getLogger(__name__)


class RoutingAlertNotifier:
    def __init__(
        self, routes: Sequence[AlertRoute], notifiers: Mapping[str, AlertNotifier]
    ) -> None:
        self._routes = tuple(routes)
        self._notifiers = dict(notifiers)
        self._fallback = LoggingAlertNotifier()

    async def notify(self, events: Sequence[AlertEvent]) -> None:
        for route, matched in route_events(events, self._routes):
            notifier = self._notifiers.get(route.name, self._fallback)
            try:
                await notifier.notify(matched)
            except Exception:
                logger.exception(
                    "alert route %s failed to deliver %d events", route.name, len(matched)
                )
