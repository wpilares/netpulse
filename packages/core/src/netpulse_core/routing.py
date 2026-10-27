from collections.abc import Sequence
from typing import Final

from pydantic import Field, TypeAdapter, ValidationError

from netpulse_core.alerts import SEVERITY_RANK, AlertEvent, AlertEventKind
from netpulse_core.anomaly import Metric, Severity
from netpulse_core.telemetry import TelemetryModel

DEFAULT_ROUTE_KINDS: Final[tuple[AlertEventKind, ...]] = ("opened", "escalated", "resolved")


class AlertRoute(TelemetryModel):
    name: str = Field(min_length=1)
    webhook_url: str | None = None
    min_severity: Severity = "warning"
    metrics: tuple[Metric, ...] | None = None
    kinds: tuple[AlertEventKind, ...] = DEFAULT_ROUTE_KINDS


type RoutedEvents = tuple[tuple[AlertRoute, tuple[AlertEvent, ...]], ...]

ROUTES_ADAPTER: Final = TypeAdapter(tuple[AlertRoute, ...])


def matches(route: AlertRoute, event: AlertEvent) -> bool:
    if event.kind not in route.kinds:
        return False
    if SEVERITY_RANK[event.state.severity] < SEVERITY_RANK[route.min_severity]:
        return False
    return route.metrics is None or event.state.key[2] in route.metrics


def route_events(events: Sequence[AlertEvent], routes: Sequence[AlertRoute]) -> RoutedEvents:
    routed = (
        (route, tuple(event for event in events if matches(route, event))) for route in routes
    )
    return tuple((route, matched) for route, matched in routed if matched)


def parse_routes(raw: str) -> tuple[AlertRoute, ...]:
    if not raw.strip():
        return ()
    try:
        return ROUTES_ADAPTER.validate_json(raw)
    except ValidationError as error:
        raise ValueError(f"alert routes must be a JSON array of route objects: {error}") from error
