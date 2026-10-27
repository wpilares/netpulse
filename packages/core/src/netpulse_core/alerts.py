from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Final, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from netpulse_core.anomaly import AnomalySignal, Metric, Severity
from netpulse_core.telemetry import DatapathId, PortNumber, TelemetryModel

AlertStatus = Literal["pending", "open", "resolved"]
AlertEventKind = Literal["opened", "escalated", "refreshed", "resolved", "suppressed"]

type AlertKey = tuple[DatapathId, PortNumber, Metric]
type AlertStates = Mapping[AlertKey, AlertState]

SEVERITY_RANK: Final[Mapping[Severity, int]] = {"warning": 1, "critical": 2}


class AlertState(TelemetryModel):
    key: AlertKey
    severity: Severity
    opened_at: AwareDatetime
    last_seen_at: AwareDatetime
    value: float
    expected: float
    zscore: float
    status: AlertStatus
    resolved_at: AwareDatetime | None
    signals: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _resolved_at_matches_status(self) -> Self:
        if (self.status == "resolved") != (self.resolved_at is not None):
            raise ValueError(f"resolved_at must be set exactly when status is resolved: {self}")
        return self


class AlertPolicy(TelemetryModel):
    resolve_after_seconds: float = Field(default=60.0, ge=0)
    cooldown_seconds: float = Field(default=120.0, ge=0)
    open_after_signals: int = Field(default=3, ge=1)


class AlertEvent(TelemetryModel):
    kind: AlertEventKind
    state: AlertState


def evaluate_alerts(
    states: AlertStates,
    signals: Sequence[AnomalySignal],
    *,
    now: AwareDatetime,
    policy: AlertPolicy,
) -> tuple[dict[AlertKey, AlertState], tuple[AlertEvent, ...]]:
    updated = dict(states)
    events: dict[AlertKey, AlertEvent] = {}
    signalled: set[AlertKey] = set()

    for signal in signals:
        key: AlertKey = (signal.dpid, signal.port_no, signal.metric)
        signalled.add(key)
        kind, state = _apply_signal(updated.get(key), signal, now=now, policy=policy)
        updated[key] = state
        if kind is not None:
            events[key] = AlertEvent(kind=kind, state=state)

    for key, state in states.items():
        if key in signalled:
            continue
        if state.status == "pending":
            del updated[key]
        elif _signal_timed_out(state, now, policy):
            resolved = state.model_copy(update={"status": "resolved", "resolved_at": now})
            updated[key] = resolved
            events[key] = AlertEvent(kind="resolved", state=resolved)
        elif _cooldown_expired(state, now, policy):
            del updated[key]

    return updated, tuple(events[key] for key in sorted(events))


def _apply_signal(
    state: AlertState | None, signal: AnomalySignal, *, now: AwareDatetime, policy: AlertPolicy
) -> tuple[AlertEventKind | None, AlertState]:
    if state is None or _cooldown_expired(state, now, policy):
        return _start(signal, now, policy)
    if state.status == "resolved":
        return "suppressed", state
    if state.status == "pending":
        return _confirm(state, signal, now, policy)
    severity = _highest(state.severity, signal.severity)
    kind: AlertEventKind = "escalated" if severity != state.severity else "refreshed"
    return kind, _seen(state, signal, now, severity=severity)


def _start(
    signal: AnomalySignal, now: AwareDatetime, policy: AlertPolicy
) -> tuple[AlertEventKind | None, AlertState]:
    started = AlertState(
        key=(signal.dpid, signal.port_no, signal.metric),
        severity=signal.severity,
        opened_at=now,
        last_seen_at=now,
        value=signal.value,
        expected=signal.expected,
        zscore=signal.zscore,
        status="pending",
        resolved_at=None,
        signals=1,
    )
    if policy.open_after_signals == 1:
        return "opened", started.model_copy(update={"status": "open"})
    return None, started


def _confirm(
    state: AlertState, signal: AnomalySignal, now: AwareDatetime, policy: AlertPolicy
) -> tuple[AlertEventKind | None, AlertState]:
    pending = _seen(state, signal, now, severity=_highest(state.severity, signal.severity))
    if pending.signals < policy.open_after_signals:
        return None, pending
    return "opened", pending.model_copy(update={"status": "open"})


def _seen(
    state: AlertState, signal: AnomalySignal, now: AwareDatetime, *, severity: Severity
) -> AlertState:
    return state.model_copy(
        update={
            "severity": severity,
            "last_seen_at": now,
            "value": signal.value,
            "expected": signal.expected,
            "zscore": signal.zscore,
            "signals": state.signals + 1,
        }
    )


def _highest(current: Severity, incoming: Severity) -> Severity:
    if SEVERITY_RANK[incoming] > SEVERITY_RANK[current]:
        return incoming
    return current


def _signal_timed_out(state: AlertState, now: AwareDatetime, policy: AlertPolicy) -> bool:
    return (
        state.status == "open" and _elapsed(state.last_seen_at, now) >= policy.resolve_after_seconds
    )


def _cooldown_expired(state: AlertState, now: AwareDatetime, policy: AlertPolicy) -> bool:
    return (
        state.resolved_at is not None
        and _elapsed(state.resolved_at, now) >= policy.cooldown_seconds
    )


def _elapsed(since: datetime, now: datetime) -> float:
    return (now - since).total_seconds()
