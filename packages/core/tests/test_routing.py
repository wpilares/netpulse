from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from netpulse_core.alerts import AlertEvent, AlertEventKind, AlertState
from netpulse_core.anomaly import Metric, Severity
from netpulse_core.routing import (
    DEFAULT_ROUTE_KINDS,
    AlertRoute,
    matches,
    parse_routes,
    route_events,
)

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _event(
    kind: AlertEventKind = "opened",
    *,
    metric: Metric = "rx_bps",
    severity: Severity = "warning",
) -> AlertEvent:
    resolved = kind == "resolved"
    return AlertEvent(
        kind=kind,
        state=AlertState(
            key=(1, 1, metric),
            severity=severity,
            opened_at=T0,
            last_seen_at=T0,
            value=2.0,
            expected=1.0,
            zscore=4.0,
            status="resolved" if resolved else "open",
            resolved_at=T0 if resolved else None,
        ),
    )


def test_route_defaults() -> None:
    route = AlertRoute(name="ops")

    assert route.webhook_url is None
    assert route.min_severity == "warning"
    assert route.metrics is None
    assert route.kinds == DEFAULT_ROUTE_KINDS == ("opened", "escalated", "resolved")


def test_route_name_must_not_be_empty() -> None:
    with pytest.raises(ValidationError, match="name"):
        AlertRoute(name="")


@pytest.mark.parametrize(
    ("min_severity", "severity", "expected"),
    [
        ("warning", "warning", True),
        ("warning", "critical", True),
        ("critical", "warning", False),
        ("critical", "critical", True),
    ],
)
def test_severity_threshold(min_severity: Severity, severity: Severity, expected: bool) -> None:
    route = AlertRoute(name="ops", min_severity=min_severity)

    assert matches(route, _event(severity=severity)) is expected


def test_metric_filter_limits_to_listed_metrics() -> None:
    route = AlertRoute(name="quality", metrics=("drop_rate", "error_rate"))

    assert matches(route, _event(metric="drop_rate"))
    assert matches(route, _event(metric="error_rate"))
    assert not matches(route, _event(metric="rx_bps"))


def test_metrics_none_matches_every_metric() -> None:
    route = AlertRoute(name="all")

    assert all(
        matches(route, _event(metric=metric))
        for metric in ("rx_bps", "tx_bps", "drop_rate", "error_rate")
    )


def test_default_kinds_exclude_refreshed_and_suppressed() -> None:
    route = AlertRoute(name="ops")

    assert matches(route, _event("opened"))
    assert matches(route, _event("escalated"))
    assert matches(route, _event("resolved"))
    assert not matches(route, _event("refreshed"))
    assert not matches(route, _event("suppressed"))


def test_explicit_kinds_override_the_default() -> None:
    route = AlertRoute(name="audit", kinds=("refreshed", "suppressed"))

    assert matches(route, _event("refreshed"))
    assert not matches(route, _event("opened"))


def test_route_events_keeps_route_order_and_drops_empty_routes() -> None:
    critical_only = AlertRoute(name="pager", min_severity="critical")
    quality = AlertRoute(name="quality", metrics=("drop_rate",))
    everything = AlertRoute(name="log")
    events = (
        _event("opened", metric="rx_bps"),
        _event("refreshed", metric="rx_bps"),
        _event("escalated", metric="tx_bps", severity="critical"),
    )

    routed = route_events(events, (critical_only, quality, everything))

    assert routed == (
        (critical_only, (events[2],)),
        (everything, (events[0], events[2])),
    )


def test_route_events_without_routes_or_events_is_empty() -> None:
    assert route_events((_event(),), ()) == ()
    assert route_events((), (AlertRoute(name="ops"),)) == ()


def test_parse_routes_reads_a_json_array() -> None:
    raw = (
        '[{"name": "pager", "webhook_url": "http://pager/hook", "min_severity": "critical"},'
        ' {"name": "quality", "metrics": ["drop_rate"], "kinds": ["opened"]}]'
    )

    assert parse_routes(raw) == (
        AlertRoute(name="pager", webhook_url="http://pager/hook", min_severity="critical"),
        AlertRoute(name="quality", metrics=("drop_rate",), kinds=("opened",)),
    )


@pytest.mark.parametrize("raw", ["", "   "])
def test_parse_routes_empty_input_is_no_routes(raw: str) -> None:
    assert parse_routes(raw) == ()


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"name": "ops"}',
        '[{"name": ""}]',
        '[{"name": "ops", "min_severity": "fatal"}]',
        '[{"name": "ops", "metrics": ["latency"]}]',
        '[{"name": "ops", "extra": 1}]',
    ],
)
def test_parse_routes_rejects_invalid_input(raw: str) -> None:
    with pytest.raises(ValueError, match="alert routes"):
        parse_routes(raw)


def test_routing_names_are_exported_from_the_package() -> None:
    import netpulse_core

    assert netpulse_core.AlertRoute is AlertRoute
    assert netpulse_core.route_events is route_events
    assert netpulse_core.parse_routes is parse_routes
    assert netpulse_core.DEFAULT_ROUTE_KINDS is DEFAULT_ROUTE_KINDS
