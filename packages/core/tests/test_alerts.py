from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from netpulse_core.alerts import (
    AlertEvent,
    AlertKey,
    AlertPolicy,
    AlertState,
    AlertStatus,
    evaluate_alerts,
)
from netpulse_core.anomaly import AnomalySignal, Metric, Severity

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
POLICY = AlertPolicy()
IMMEDIATE = AlertPolicy(open_after_signals=1)
RX_KEY: AlertKey = (1, 1, "rx_bps")


def _at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def _signal(
    *,
    metric: Metric = "rx_bps",
    severity: Severity = "warning",
    dpid: int = 1,
    port_no: int = 1,
    value: float = 2_000_000.0,
    expected: float = 1_000_000.0,
    zscore: float = 4.0,
) -> AnomalySignal:
    return AnomalySignal(
        dpid=dpid,
        port_no=port_no,
        metric=metric,
        observed_at=T0,
        value=value,
        expected=expected,
        zscore=zscore,
        severity=severity,
    )


def _state(
    *,
    key: AlertKey = RX_KEY,
    severity: Severity = "warning",
    opened_at: datetime = T0,
    last_seen_at: datetime = T0,
    status: AlertStatus = "open",
    resolved_at: datetime | None = None,
    signals: int = 1,
) -> AlertState:
    return AlertState(
        key=key,
        severity=severity,
        opened_at=opened_at,
        last_seen_at=last_seen_at,
        value=2_000_000.0,
        expected=1_000_000.0,
        zscore=4.0,
        status=status,
        resolved_at=resolved_at,
        signals=signals,
    )


def _resolved(resolved_at: datetime, *, severity: Severity = "warning") -> AlertState:
    return _state(
        severity=severity,
        opened_at=_at(-300),
        last_seen_at=_at(-60),
        status="resolved",
        resolved_at=resolved_at,
    )


def test_policy_defaults() -> None:
    assert POLICY.resolve_after_seconds == 60.0
    assert POLICY.cooldown_seconds == 120.0
    assert POLICY.open_after_signals == 3


@pytest.mark.parametrize(
    "overrides",
    [{"resolve_after_seconds": -1.0}, {"cooldown_seconds": -0.5}, {"open_after_signals": 0}],
)
def test_invalid_policy_is_rejected(overrides: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        AlertPolicy.model_validate(overrides)


@pytest.mark.parametrize(
    ("status", "resolved_at"), [("open", T0), ("pending", T0), ("resolved", None)]
)
def test_state_requires_resolved_at_only_when_resolved(
    status: AlertStatus, resolved_at: datetime | None
) -> None:
    with pytest.raises(ValidationError, match="resolved_at"):
        _state(status=status, resolved_at=resolved_at)


def test_state_counts_at_least_one_signal() -> None:
    with pytest.raises(ValidationError, match="signals"):
        _state(signals=0)


def test_first_signal_creates_pending_state_without_event() -> None:
    states, events = evaluate_alerts({}, [_signal()], now=_at(5), policy=POLICY)

    pending = _state(status="pending", opened_at=_at(5), last_seen_at=_at(5), signals=1)
    assert states == {RX_KEY: pending}
    assert events == ()


def test_default_policy_opens_after_three_consecutive_signals() -> None:
    states, first = evaluate_alerts({}, [_signal()], now=_at(5), policy=POLICY)
    states, second = evaluate_alerts(states, [_signal()], now=_at(10), policy=POLICY)
    states, third = evaluate_alerts(states, [_signal(zscore=4.5)], now=_at(15), policy=POLICY)

    assert first == second == ()
    opened = states[RX_KEY]
    assert third == (AlertEvent(kind="opened", state=opened),)
    assert opened.status == "open"
    assert opened.signals == 3
    assert opened.opened_at == _at(15)
    assert opened.last_seen_at == _at(15)
    assert opened.zscore == 4.5
    assert opened.resolved_at is None


def test_pending_alert_is_dropped_after_a_gap() -> None:
    states, _ = evaluate_alerts({}, [_signal()], now=_at(5), policy=POLICY)
    states, _ = evaluate_alerts(states, [_signal()], now=_at(10), policy=POLICY)

    states, gap = evaluate_alerts(states, [], now=_at(15), policy=POLICY)
    assert states == {}
    assert gap == ()

    states, after_gap = evaluate_alerts(states, [_signal()], now=_at(20), policy=POLICY)
    assert after_gap == ()
    assert states[RX_KEY].status == "pending"
    assert states[RX_KEY].signals == 1


def test_severity_escalates_while_pending_and_opened_event_carries_the_maximum() -> None:
    states, _ = evaluate_alerts({}, [_signal()], now=_at(5), policy=POLICY)
    states, _ = evaluate_alerts(
        states, [_signal(severity="critical", zscore=8.0)], now=_at(10), policy=POLICY
    )
    assert states[RX_KEY].severity == "critical"
    assert states[RX_KEY].status == "pending"

    states, events = evaluate_alerts(states, [_signal()], now=_at(15), policy=POLICY)

    assert [event.kind for event in events] == ["opened"]
    assert events[0].state.severity == "critical"
    assert events[0].state.zscore == 4.0


def test_pending_alert_updates_its_measurement_each_signal() -> None:
    states, _ = evaluate_alerts({}, [_signal()], now=_at(5), policy=POLICY)
    states, _ = evaluate_alerts(
        states,
        [_signal(value=3_000_000.0, expected=1_100_000.0, zscore=3.5)],
        now=_at(10),
        policy=POLICY,
    )

    pending = states[RX_KEY]
    assert pending.signals == 2
    assert pending.opened_at == _at(5)
    assert pending.last_seen_at == _at(10)
    assert pending.value == 3_000_000.0
    assert pending.expected == 1_100_000.0
    assert pending.zscore == 3.5


def test_signal_after_cooldown_reenters_pending_before_reopening() -> None:
    states, after_cooldown = evaluate_alerts(
        {RX_KEY: _resolved(T0)}, [_signal()], now=_at(120), policy=POLICY
    )
    assert after_cooldown == ()
    assert states[RX_KEY].status == "pending"
    assert states[RX_KEY].signals == 1
    assert states[RX_KEY].resolved_at is None

    states, _ = evaluate_alerts(states, [_signal()], now=_at(125), policy=POLICY)
    states, events = evaluate_alerts(states, [_signal()], now=_at(130), policy=POLICY)

    assert [event.kind for event in events] == ["opened"]
    assert states[RX_KEY].status == "open"
    assert states[RX_KEY].opened_at == _at(130)


def test_signal_without_state_opens_alert() -> None:
    states, events = evaluate_alerts({}, [_signal()], now=_at(5), policy=IMMEDIATE)

    opened = AlertState(
        key=RX_KEY,
        severity="warning",
        opened_at=_at(5),
        last_seen_at=_at(5),
        value=2_000_000.0,
        expected=1_000_000.0,
        zscore=4.0,
        status="open",
        resolved_at=None,
    )
    assert states == {RX_KEY: opened}
    assert events == (AlertEvent(kind="opened", state=opened),)


def test_signal_refreshes_open_alert() -> None:
    signal = _signal(value=3_000_000.0, expected=1_100_000.0, zscore=3.5)

    states, events = evaluate_alerts({RX_KEY: _state()}, [signal], now=_at(10), policy=POLICY)

    refreshed = states[RX_KEY]
    assert [event.kind for event in events] == ["refreshed"]
    assert events[0].state == refreshed
    assert refreshed.opened_at == T0
    assert refreshed.last_seen_at == _at(10)
    assert refreshed.value == 3_000_000.0
    assert refreshed.expected == 1_100_000.0
    assert refreshed.zscore == 3.5
    assert refreshed.severity == "warning"
    assert refreshed.status == "open"


def test_critical_signal_escalates_warning_alert() -> None:
    states, events = evaluate_alerts(
        {RX_KEY: _state()}, [_signal(severity="critical", zscore=8.0)], now=_at(10), policy=POLICY
    )

    assert [event.kind for event in events] == ["escalated"]
    assert states[RX_KEY].severity == "critical"
    assert states[RX_KEY].zscore == 8.0
    assert states[RX_KEY].opened_at == T0


def test_warning_signal_never_lowers_critical_alert() -> None:
    states, events = evaluate_alerts(
        {RX_KEY: _state(severity="critical")}, [_signal()], now=_at(10), policy=POLICY
    )

    assert [event.kind for event in events] == ["refreshed"]
    assert states[RX_KEY].severity == "critical"


def test_open_alert_stays_open_before_timeout() -> None:
    states, events = evaluate_alerts({RX_KEY: _state()}, [], now=_at(59.9), policy=POLICY)

    assert states == {RX_KEY: _state()}
    assert events == ()


def test_open_alert_resolves_after_timeout_without_signal() -> None:
    states, events = evaluate_alerts({RX_KEY: _state()}, [], now=_at(60), policy=POLICY)

    resolved = states[RX_KEY]
    assert events == (AlertEvent(kind="resolved", state=resolved),)
    assert resolved.status == "resolved"
    assert resolved.resolved_at == _at(60)
    assert resolved.last_seen_at == T0
    assert resolved.severity == "warning"


def test_signal_within_cooldown_is_suppressed() -> None:
    states, events = evaluate_alerts(
        {RX_KEY: _resolved(T0)}, [_signal()], now=_at(119.9), policy=POLICY
    )

    assert states == {RX_KEY: _resolved(T0)}
    assert events == (AlertEvent(kind="suppressed", state=_resolved(T0)),)


def test_signal_after_cooldown_reopens_alert() -> None:
    states, events = evaluate_alerts(
        {RX_KEY: _resolved(T0, severity="critical")}, [_signal()], now=_at(120), policy=IMMEDIATE
    )

    reopened = states[RX_KEY]
    assert [event.kind for event in events] == ["opened"]
    assert reopened.status == "open"
    assert reopened.severity == "warning"
    assert reopened.opened_at == _at(120)
    assert reopened.last_seen_at == _at(120)
    assert reopened.resolved_at is None


def test_resolved_alert_is_kept_during_cooldown() -> None:
    states, events = evaluate_alerts({RX_KEY: _resolved(T0)}, [], now=_at(119.9), policy=POLICY)

    assert states == {RX_KEY: _resolved(T0)}
    assert events == ()


def test_resolved_alert_is_pruned_after_cooldown() -> None:
    states, events = evaluate_alerts({RX_KEY: _resolved(T0)}, [], now=_at(120), policy=POLICY)

    assert states == {}
    assert events == ()


def test_events_are_sorted_by_key() -> None:
    signals = [
        _signal(dpid=2, port_no=1, metric="rx_bps"),
        _signal(dpid=1, port_no=2, metric="drop_rate"),
        _signal(dpid=1, port_no=1, metric="tx_bps"),
        _signal(dpid=1, port_no=1, metric="rx_bps"),
    ]

    _, events = evaluate_alerts({}, signals, now=_at(5), policy=IMMEDIATE)

    assert [event.state.key for event in events] == [
        (1, 1, "rx_bps"),
        (1, 1, "tx_bps"),
        (1, 2, "drop_rate"),
        (2, 1, "rx_bps"),
    ]
    assert {event.kind for event in events} == {"opened"}


def test_mixed_round_refreshes_resolves_and_prunes_independently() -> None:
    tx_key: AlertKey = (1, 1, "tx_bps")
    drop_key: AlertKey = (1, 1, "drop_rate")
    error_key: AlertKey = (1, 1, "error_rate")
    states = {
        tx_key: _state(key=tx_key),
        RX_KEY: _state(),
        drop_key: _resolved(_at(-120)).model_copy(update={"key": drop_key}),
        error_key: _state(key=error_key, status="pending", opened_at=_at(55), signals=2),
    }

    updated, events = evaluate_alerts(
        states, [_signal(metric="rx_bps")], now=_at(60), policy=POLICY
    )

    assert [(event.state.key, event.kind) for event in events] == [
        (RX_KEY, "refreshed"),
        (tx_key, "resolved"),
    ]
    assert set(updated) == {RX_KEY, tx_key}
    assert updated[tx_key].status == "resolved"
    assert updated[RX_KEY].last_seen_at == _at(60)
