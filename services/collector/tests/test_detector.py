import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from netpulse_collector.alerts import AlertWriteError
from netpulse_collector.detector import AnomalyDetector, DetectionObserver
from netpulse_core import (
    AlertEvent,
    AlertPolicy,
    DetectionConfig,
    PortStats,
    PortStatsReport,
    SwitchPortStats,
)

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
INTERVAL = 5
WARMUP = 3
CONFIG = DetectionConfig(warmup_samples=WARMUP)
POLICY = AlertPolicy(resolve_after_seconds=10.0, cooldown_seconds=20.0)
RESERVED_PORT = 0xFFFFFFFE
STEADY_BYTES_PER_INTERVAL = 1_000
SPIKE_BYTES = 10_000_000
PACKETS_PER_INTERVAL = 100


def _port(port_no: int, cycle: int, *, extra_rx_bytes: int = 0, rx_dropped: int = 0) -> PortStats:
    return PortStats(
        port_no=port_no,
        rx_packets=PACKETS_PER_INTERVAL * cycle,
        tx_packets=PACKETS_PER_INTERVAL * cycle,
        rx_bytes=STEADY_BYTES_PER_INTERVAL * cycle + extra_rx_bytes,
        tx_bytes=STEADY_BYTES_PER_INTERVAL * cycle,
        rx_dropped=rx_dropped,
        tx_dropped=0,
        rx_errors=0,
        tx_errors=0,
        duration_sec=INTERVAL * cycle,
    )


def _report(cycle: int, *, ports: Sequence[PortStats] | None = None) -> PortStatsReport:
    collected_at = T0 + timedelta(seconds=INTERVAL * cycle)
    return PortStatsReport(
        switches=(
            SwitchPortStats(
                dpid=1,
                collected_at=collected_at,
                ports=tuple(ports) if ports is not None else (_port(1, cycle),),
            ),
        )
    )


def _detector() -> AnomalyDetector:
    return AnomalyDetector(config=CONFIG, policy=POLICY, link_capacity_bps=10_000_000)


def _warm_up(detector: AnomalyDetector) -> int:
    cycle = 0
    for cycle in range(1, WARMUP + 2):
        assert detector.observe(_report(cycle)) == ()
    return cycle


def test_spike_during_warm_up_produces_no_events() -> None:
    detector = _detector()

    assert detector.observe(_report(1)) == ()
    assert detector.observe(_report(2)) == ()
    assert detector.observe(_report(3, ports=[_port(1, 3, extra_rx_bytes=SPIKE_BYTES)])) == ()


def test_spike_after_warm_up_opens_a_critical_rx_alert() -> None:
    detector = _detector()
    cycle = _warm_up(detector) + 1

    events = detector.observe(_report(cycle, ports=[_port(1, cycle, extra_rx_bytes=SPIKE_BYTES)]))

    assert [event.kind for event in events] == ["opened"]
    state = events[0].state
    assert state.key == (1, 1, "rx_bps")
    assert state.severity == "critical"
    assert state.status == "open"
    assert state.opened_at == T0 + timedelta(seconds=INTERVAL * cycle)
    assert state.value == pytest.approx((STEADY_BYTES_PER_INTERVAL + SPIKE_BYTES) * 8 / INTERVAL)


def test_sustained_drops_refresh_the_open_alert() -> None:
    detector = _detector()
    cycle = _warm_up(detector)

    first = detector.observe(_report(cycle + 1, ports=[_port(1, cycle + 1, rx_dropped=20)]))
    second = detector.observe(_report(cycle + 2, ports=[_port(1, cycle + 2, rx_dropped=40)]))

    assert [(event.kind, event.state.key) for event in first] == [("opened", (1, 1, "drop_rate"))]
    assert [(event.kind, event.state.key) for event in second] == [
        ("refreshed", (1, 1, "drop_rate"))
    ]
    assert second[0].state.opened_at == first[0].state.opened_at
    assert second[0].state.last_seen_at == T0 + timedelta(seconds=INTERVAL * (cycle + 2))


def test_silence_resolves_the_alert_after_the_policy_window() -> None:
    detector = _detector()
    cycle = _warm_up(detector) + 1
    detector.observe(_report(cycle, ports=[_port(1, cycle, extra_rx_bytes=SPIKE_BYTES)]))

    quiet = [
        detector.observe(
            _report(cycle + offset, ports=[_port(1, cycle + offset, extra_rx_bytes=SPIKE_BYTES)])
        )
        for offset in (1, 2)
    ]

    assert quiet[0] == ()
    assert [event.kind for event in quiet[1]] == ["resolved"]
    assert quiet[1][0].state.resolved_at == T0 + timedelta(seconds=INTERVAL * (cycle + 2))


def test_counter_reset_yields_no_events() -> None:
    detector = _detector()
    cycle = _warm_up(detector) + 1

    events = detector.observe(_report(cycle, ports=[_port(1, 1)]))

    assert events == ()


def test_reserved_ports_are_ignored() -> None:
    detector = _detector()
    for cycle in range(1, WARMUP + 2):
        detector.observe(_report(cycle, ports=[_port(1, cycle), _port(RESERVED_PORT, cycle)]))
    cycle = WARMUP + 2

    events = detector.observe(
        _report(
            cycle,
            ports=[_port(1, cycle), _port(RESERVED_PORT, cycle, extra_rx_bytes=SPIKE_BYTES)],
        )
    )

    assert events == ()


def test_empty_report_resolves_with_the_clock() -> None:
    cycle = WARMUP + 2
    later = T0 + timedelta(seconds=INTERVAL * cycle + POLICY.resolve_after_seconds)
    detector = AnomalyDetector(
        config=CONFIG, policy=POLICY, link_capacity_bps=None, clock=lambda: later
    )
    _warm_up(detector)
    detector.observe(_report(cycle, ports=[_port(1, cycle, extra_rx_bytes=SPIKE_BYTES)]))

    events = detector.observe(PortStatsReport(switches=()))

    assert [event.kind for event in events] == ["resolved"]
    assert events[0].state.resolved_at == later


class RecordingAlertRepository:
    def __init__(self) -> None:
        self.applied: list[Sequence[AlertEvent]] = []

    async def apply(self, events: Sequence[AlertEvent]) -> None:
        self.applied.append(events)


class FailingAlertRepository:
    async def apply(self, events: Sequence[AlertEvent]) -> None:
        raise AlertWriteError("alerts table unavailable")


class RecordingAlertNotifier:
    def __init__(self) -> None:
        self.notified: list[Sequence[AlertEvent]] = []

    async def notify(self, events: Sequence[AlertEvent]) -> None:
        self.notified.append(events)


def _alerting_detector() -> tuple[AnomalyDetector, PortStatsReport]:
    detector = _detector()
    cycle = _warm_up(detector) + 1
    return detector, _report(cycle, ports=[_port(1, cycle, extra_rx_bytes=SPIKE_BYTES)])


async def test_observer_persists_and_notifies_events() -> None:
    detector, spike = _alerting_detector()
    repository = RecordingAlertRepository()
    notifier = RecordingAlertNotifier()
    observer = DetectionObserver(detector, repository, notifier)

    await observer.observe(spike)

    assert len(repository.applied) == 1
    assert repository.applied == notifier.notified
    assert [event.kind for event in repository.applied[0]] == ["opened"]


async def test_observer_skips_persistence_without_events() -> None:
    repository = RecordingAlertRepository()
    notifier = RecordingAlertNotifier()
    observer = DetectionObserver(_detector(), repository, notifier)

    await observer.observe(_report(1))

    assert repository.applied == []
    assert notifier.notified == []


async def test_observer_logs_write_failures_and_still_notifies(
    caplog: pytest.LogCaptureFixture,
) -> None:
    detector, spike = _alerting_detector()
    notifier = RecordingAlertNotifier()
    observer = DetectionObserver(detector, FailingAlertRepository(), notifier)

    with caplog.at_level(logging.ERROR, logger="netpulse_collector.detector"):
        await observer.observe(spike)

    assert len(notifier.notified) == 1
    assert "alerts table unavailable" in caplog.text
