import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from netpulse_api.kpis import (
    KpiUnavailableError,
    SamplePair,
    latest_port_kpis,
    network_kpi_summary,
)
from netpulse_api.live import (
    HeartbeatFrame,
    KpiFrame,
    LiveKpiBroadcaster,
    StoreUnavailableFrame,
)
from netpulse_core import DatapathId

NOW = datetime(2026, 10, 20, 12, 5, tzinfo=UTC)
CAPACITY_BPS = 10_000_000

type Outcome = list[SamplePair] | Exception
type MakeSamplePair = Callable[[int, int], SamplePair]


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


def _broadcaster(query: ScriptedLatestSamplesQuery, *, queue_size: int = 4) -> LiveKpiBroadcaster:
    return LiveKpiBroadcaster(
        query,
        link_capacity_bps=CAPACITY_BPS,
        interval_seconds=0.001,
        queue_size=queue_size,
        clock=lambda: NOW,
    )


async def test_tick_broadcasts_a_kpi_frame_to_every_subscriber(
    make_sample_pair: MakeSamplePair,
) -> None:
    pairs = [make_sample_pair(2, 1), make_sample_pair(1, 2)]
    query = ScriptedLatestSamplesQuery(pairs)
    broadcaster = _broadcaster(query)
    first = broadcaster.subscribe()
    second = broadcaster.subscribe()

    frame = await broadcaster.tick()

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

    frame = await broadcaster.tick()

    assert frame == HeartbeatFrame(at=NOW)
    assert await anext(subscription) == frame


async def test_tick_reports_an_unavailable_store() -> None:
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery(KpiUnavailableError("database down")))
    subscription = broadcaster.subscribe()

    frame = await broadcaster.tick()

    assert frame == StoreUnavailableFrame(at=NOW)
    assert await anext(subscription) == frame


async def test_slow_subscriber_is_dropped_when_its_queue_is_full() -> None:
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery([], [], []), queue_size=1)
    slow = broadcaster.subscribe()
    fast = broadcaster.subscribe()

    first = await broadcaster.tick()
    assert await anext(fast) == first
    second = await broadcaster.tick()

    assert slow.dropped is True
    assert fast.dropped is False
    assert broadcaster.subscriber_count == 1
    with pytest.raises(StopAsyncIteration):
        await anext(slow)
    assert await anext(fast) == second
    assert await broadcaster.tick() == await anext(fast)


async def test_unsubscribe_removes_the_subscriber() -> None:
    broadcaster = _broadcaster(ScriptedLatestSamplesQuery([]))
    subscription = broadcaster.subscribe()

    broadcaster.unsubscribe(subscription)

    assert broadcaster.subscriber_count == 0
    assert subscription.dropped is False
    assert await broadcaster.tick() == HeartbeatFrame(at=NOW)


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
