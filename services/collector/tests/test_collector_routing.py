import logging
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from pydantic import HttpUrl

from netpulse_collector.routing import RoutingAlertNotifier
from netpulse_core import AlertEvent, AlertEventKind, AlertRoute, AlertState, Metric, Severity

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _event(kind: AlertEventKind, metric: Metric, severity: Severity) -> AlertEvent:
    return AlertEvent(
        kind=kind,
        state=AlertState(
            key=(1, 2, metric),
            severity=severity,
            opened_at=T0,
            last_seen_at=T0,
            value=1.0,
            expected=0.0,
            zscore=6.0,
            status="open",
            resolved_at=None,
        ),
    )


OPENED_RX = _event("opened", "rx_bps", "warning")
OPENED_DROPS = _event("opened", "drop_rate", "critical")
REFRESHED_DROPS = _event("refreshed", "drop_rate", "critical")
PAGER = AlertRoute(
    name="pager", webhook_url=HttpUrl("https://pager.example.test"), min_severity="critical"
)
CHAT = AlertRoute(
    name="chat", webhook_url=HttpUrl("https://chat.example.test"), metrics=("rx_bps",)
)
AUDIT = AlertRoute(name="audit", kinds=("refreshed",))


class RecordingNotifier:
    def __init__(self) -> None:
        self.notified: list[Sequence[AlertEvent]] = []

    async def notify(self, events: Sequence[AlertEvent]) -> None:
        self.notified.append(events)


class FailingNotifier:
    async def notify(self, events: Sequence[AlertEvent]) -> None:
        raise RuntimeError("pager unreachable")


async def test_each_route_receives_only_its_matching_events() -> None:
    pager, chat = RecordingNotifier(), RecordingNotifier()
    notifier = RoutingAlertNotifier([PAGER, CHAT], {"pager": pager, "chat": chat})

    await notifier.notify([OPENED_RX, OPENED_DROPS, REFRESHED_DROPS])

    assert pager.notified == [(OPENED_DROPS,)]
    assert chat.notified == [(OPENED_RX,)]


async def test_routes_without_a_notifier_fall_back_to_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    chat = RecordingNotifier()
    notifier = RoutingAlertNotifier([CHAT, AUDIT], {"chat": chat})

    with caplog.at_level(logging.WARNING, logger="netpulse_collector.alerts"):
        await notifier.notify([OPENED_RX, REFRESHED_DROPS])

    assert chat.notified == [(OPENED_RX,)]
    assert [record.getMessage() for record in caplog.records] == [
        "alert refreshed critical alert dpid=1 port=2 metric=drop_rate "
        "value=1 expected=0 zscore=6.00"
    ]


async def test_unmatched_events_reach_no_route() -> None:
    pager = RecordingNotifier()
    notifier = RoutingAlertNotifier([PAGER], {"pager": pager})

    await notifier.notify([OPENED_RX, REFRESHED_DROPS])

    assert pager.notified == []


async def test_a_failing_route_does_not_block_the_others(
    caplog: pytest.LogCaptureFixture,
) -> None:
    chat = RecordingNotifier()
    notifier = RoutingAlertNotifier([PAGER, CHAT], {"pager": FailingNotifier(), "chat": chat})

    with caplog.at_level(logging.ERROR, logger="netpulse_collector.routing"):
        await notifier.notify([OPENED_RX, OPENED_DROPS])

    assert chat.notified == [(OPENED_RX,)]
    assert "pager" in caplog.text
    assert "pager unreachable" in caplog.text
