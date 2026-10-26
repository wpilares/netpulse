import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from netpulse_api.alerts import Alert, AlertStatusFilter, AlertsUnavailableError
from netpulse_api.kpis import (
    KpiUnavailableError,
    SamplePair,
    latest_port_kpis,
    network_kpi_summary,
)
from netpulse_api.live import (
    AlertFrame,
    HeartbeatFrame,
    KpiFrame,
    LiveKpiBroadcaster,
    StoreUnavailableFrame,
)
from netpulse_core import AlertStatus, DatapathId

NOW = datetime(2026, 10, 20, 12, 5, tzinfo=UTC)
CAPACITY_BPS = 10_000_000

type Outcome = list[SamplePair] | Exception
type AlertOutcome = list[Alert] | Exception
type MakeSamplePair = Callable[[int, int], SamplePair]
type MakeAlert = Callable[[int, AlertStatus], Alert]


class ScriptedLatestSamplesQuery:
    def __init__(self, *outcomes: Outcome, stop: asyncio.Event | None = None) -> None:
        self._outcomes = list(outcomes)
        self._stop = stop
        self.requests: list[DatapathId | None] = []

    async def fetch(self, dpid: DatapathId | None) -> list[SamplePair]:
        self.requests.append(dpid)
        outcome = self._outcomes.pop(0)
        if not self._outcomes and self._stop is not None:
            self._stop.set()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class ScriptedAlertsQuery:
    def __init__(self, *outcomes: AlertOutcome) -> None:
        self._outcomes = list(outcomes)
        self.snapshots: list[tuple[AlertStatusFilter, int]] = []
        self.cursors: list[datetime] = []

    async def fetch(self, status: AlertStatusFilter, *, limit: int) -> list[Alert]:
        self.snapshots.append((status, limit))
        return self._next()

    async def fetch_updated_since(self, since: datetime) -> list[Alert]:
        self.cursors.append(since)
        return self._next()

    def _next(self) -> list[Alert]:
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _broadcaster(
    query: ScriptedLatestSamplesQuery,
    *,
    queue_size: int = 4,
    alerts: ScriptedAlertsQuery | None = None,
) -> LiveKpiBroadcaster:
    return LiveKpiBroadcaster(
        query,
        link_capacity_bps=CAPACITY_BPS,
        interval_seconds=0.001,
        queue_size=queue_size,
        clock=lambda: NOW,
        alerts=alerts,
    )


def _updated(alert: Alert, *, minutes: int) -> Alert:
    return alert.model_copy(update={"updated_at": alert.updated_at + timedelta(minutes=minutes)})


async def test_tick_broadcasts_a_kpi_frame_to_every_subscriber(
    make_sample_pair: MakeSamplePair,
) -> None:
    pairs = [make_sample_pair(2, 1), make_sample_pair(1, 2)]
    query = ScriptedLatestSamplesQuery(pairs)
    broadcaster = _broadcaster(query)
    first = broadcaster.subscribe()
    second = broadcaster.subscribe()

    (frame,) = await broadcaster.tick()

    expected = network_kpi_summary(
        latest_port_kpis(pairs, link_capacity_bps=CAPACITY_BPS), generated_at=NOW
    )
    assert isinstance(frame, KpiFrame)
    assert frame.type == "kpis"
    assert frame.generated_at == NOW
    assert frame.summary == expected.summary
    assert frame.switches == expected.switches
    assert await anext(first) == frame
    assert await anext(second) == frame
    assert query.requests == [None]
    assert broadcaster.subscriber_count == 2


async def test_tick_emits_a_heartbeat_without_samples() -> None:
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery([]))
    subscription = broadcaster.subscribe()

    (frame,) = await broadcaster.tick()

    assert frame == HeartbeatFrame(at=NOW)
    assert await anext(subscription) == frame


async def test_tick_reports_an_unavailable_store() -> None:
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery(KpiUnavailableError("database down")))
    subscription = broadcaster.subscribe()

    (frame,) = await broadcaster.tick()

    assert frame == StoreUnavailableFrame(at=NOW)
    assert await anext(subscription) == frame


async def test_slow_subscriber_is_dropped_when_its_queue_is_full() -> None:
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery([], [], []), queue_size=1)
    slow = broadcaster.subscribe()
    fast = broadcaster.subscribe()

    (first,) = await broadcaster.tick()
    assert await anext(fast) == first
    (second,) = await broadcaster.tick()

    assert slow.dropped is True
    assert fast.dropped is False
    assert broadcaster.subscriber_count == 1
    with pytest.raises(StopAsyncIteration):
        await anext(slow)
    assert await anext(fast) == second
    assert await broadcaster.tick() == (await anext(fast),)


async def test_unsubscribe_removes_the_subscriber() -> None:
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery([]))
    subscription = broadcaster.subscribe()

    broadcaster.unsubscribe(subscription)

    assert broadcaster.subscriber_count == 0
    assert subscription.dropped is False
    assert await broadcaster.tick() == (HeartbeatFrame(at=NOW),)


async def test_run_ticks_until_stopped(make_sample_pair: MakeSamplePair) -> None:
    stop = asyncio.Event()
    query = ScriptedLatestSamplesQuery([make_sample_pair(1, 1)], [], [], stop=stop)
    broadcaster = _broadcaster(query)
    subscription = broadcaster.subscribe()

    await broadcaster.run(stop)

    assert len(query.requests) == 3
    assert [(await anext(subscription)).type for _ in range(3)] == [
        "kpis",
        "heartbeat",
        "heartbeat",
    ]


async def test_run_logs_and_continues_after_unexpected_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop = asyncio.Event()
    query = ScriptedLatestSamplesQuery(RuntimeError("boom"), [], stop=stop)
    broadcaster = _broadcaster(query)
    subscription = broadcaster.subscribe()

    await broadcaster.run(stop)

    assert len(query.requests) == 2
    assert "live kpi cycle failed" in caplog.text
    assert await anext(subscription) == HeartbeatFrame(at=NOW)


async def test_first_tick_streams_the_open_alerts(make_alert: MakeAlert) -> None:
    open_alerts = [make_alert(2, "open"), make_alert(1, "open")]
    alerts = ScriptedAlertsQuery(open_alerts)
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery([]), alerts=alerts)
    subscription = broadcaster.subscribe()

    frames = await broadcaster.tick()

    assert frames == (
        HeartbeatFrame(at=NOW),
        AlertFrame(generated_at=NOW, alerts=tuple(open_alerts)),
    )
    assert frames[1].type == "alerts"
    assert await anext(subscription) == frames[0]
    assert await anext(subscription) == frames[1]
    assert alerts.snapshots == [("open", 500)]
    assert alerts.cursors == []


async def test_no_alert_frame_when_nothing_changed(make_alert: MakeAlert) -> None:
    alert = make_alert(1, "open")
    alerts = ScriptedAlertsQuery([alert], [])
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery([], []), alerts=alerts)

    first = await broadcaster.tick()
    second = await broadcaster.tick()

    assert len(first) == 2
    assert second == (HeartbeatFrame(at=NOW),)
    assert alerts.cursors == [alert.updated_at]


async def test_alert_cursor_advances_to_the_newest_update(make_alert: MakeAlert) -> None:
    opened = make_alert(1, "open")
    refreshed = _updated(opened, minutes=3)
    resolved = _updated(make_alert(2, "resolved"), minutes=5)
    alerts = ScriptedAlertsQuery([opened], [resolved, refreshed], [])
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery([], [], []), alerts=alerts)

    await broadcaster.tick()
    second = await broadcaster.tick()
    await broadcaster.tick()

    assert second[1] == AlertFrame(generated_at=NOW, alerts=(resolved, refreshed))
    assert alerts.snapshots == [("open", 500)]
    assert alerts.cursors == [opened.updated_at, resolved.updated_at]


async def test_snapshot_repeats_until_an_alert_exists(make_alert: MakeAlert) -> None:
    alert = make_alert(1, "open")
    alerts = ScriptedAlertsQuery([], [alert], [])
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery([], [], []), alerts=alerts)

    first = await broadcaster.tick()
    second = await broadcaster.tick()
    third = await broadcaster.tick()

    assert (len(first), len(second), len(third)) == (1, 2, 1)
    assert alerts.snapshots == [("open", 500), ("open", 500)]
    assert alerts.cursors == [alert.updated_at]


async def test_unavailable_alerts_are_skipped_and_retried(
    make_alert: MakeAlert, caplog: pytest.LogCaptureFixture
) -> None:
    alert = make_alert(1, "open")
    alerts = ScriptedAlertsQuery(
        AlertsUnavailableError("database down"), [alert], AlertsUnavailableError("database down")
    )
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery([], [], []), alerts=alerts)
    subscription = broadcaster.subscribe()

    first = await broadcaster.tick()
    second = await broadcaster.tick()
    third = await broadcaster.tick()

    assert first == (HeartbeatFrame(at=NOW),)
    assert second == (HeartbeatFrame(at=NOW), AlertFrame(generated_at=NOW, alerts=(alert,)))
    assert third == (HeartbeatFrame(at=NOW),)
    assert "alert query failed" in caplog.text
    assert alerts.snapshots == [("open", 500), ("open", 500)]
    assert alerts.cursors == [alert.updated_at]
    assert [frame.type for frame in [await anext(subscription) for _ in range(4)]] == [
        "heartbeat",
        "heartbeat",
        "alerts",
        "heartbeat",
    ]
