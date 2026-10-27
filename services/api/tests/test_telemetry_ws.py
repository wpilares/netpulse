from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from netpulse_api.alerts import MAX_ALERT_LIMIT, Alert, AlertStatusFilter
from netpulse_api.app import create_app
from netpulse_api.kpis import SamplePair
from netpulse_api.live import LiveKpiBroadcaster
from netpulse_core import AlertStatus, DatapathId

MakeClient = Callable[[bool | None], TestClient]
MakeSamplePair = Callable[[int, int], SamplePair]
MakeAlert = Callable[[int, AlertStatus], Alert]

NOW = datetime(2026, 10, 20, 12, 5, tzinfo=UTC)
CAPACITY_BPS = 10_000_000


class StaticLatestSamplesQuery:
    def __init__(self, pairs: list[SamplePair]) -> None:
        self.pairs = pairs

    async def fetch(self, dpid: DatapathId | None) -> list[SamplePair]:
        return self.pairs


class StaticAlertsQuery:
    def __init__(self, alerts: list[Alert]) -> None:
        self.alerts = alerts

    async def fetch(self, status: AlertStatusFilter, *, limit: int) -> list[Alert]:
        return self.alerts

    async def fetch_after(self, seq: int, *, limit: int = MAX_ALERT_LIMIT) -> list[Alert]:
        return []


def _live_client(
    pairs: list[SamplePair], *, queue_size: int = 4, alerts: list[Alert] | None = None
) -> tuple[TestClient, LiveKpiBroadcaster]:
    broadcaster = LiveKpiBroadcaster(
        StaticLatestSamplesQuery(pairs),
        link_capacity_bps=CAPACITY_BPS,
        interval_seconds=60.0,
        queue_size=queue_size,
        clock=lambda: NOW,
        alerts=None if alerts is None else StaticAlertsQuery(alerts),
    )
    return TestClient(create_app(database_probe=None, live_broadcaster=broadcaster)), broadcaster


def test_websocket_handshake_greets_the_client(make_client: MakeClient) -> None:
    with make_client(None).websocket_connect("/ws/telemetry") as websocket:
        assert websocket.receive_json() == {"type": "hello", "version": "1.0.0"}


def test_websocket_answers_pings(make_client: MakeClient) -> None:
    with make_client(None).websocket_connect("/ws/telemetry") as websocket:
        websocket.receive_json()
        websocket.send_json({"type": "ping"})

        assert websocket.receive_json() == {"type": "pong"}


def test_websocket_reports_unsupported_messages(make_client: MakeClient) -> None:
    with make_client(None).websocket_connect("/ws/telemetry") as websocket:
        websocket.receive_json()
        websocket.send_json({"type": "subscribe"})

        assert websocket.receive_json() == {"type": "error", "reason": "unsupported message"}


def test_websocket_streams_kpi_frames_from_the_broadcaster(
    make_sample_pair: MakeSamplePair,
) -> None:
    client, broadcaster = _live_client([make_sample_pair(1, 2)])

    with client.websocket_connect("/ws/telemetry") as websocket:
        assert websocket.receive_json() == {"type": "hello", "version": "1.0.0"}
        assert broadcaster.subscriber_count == 1
        websocket.portal.call(broadcaster.tick)

        frame = websocket.receive_json()

        assert frame["type"] == "kpis"
        assert frame["generated_at"] == "2026-10-20T12:05:00Z"
        assert frame["summary"]["ports"] == 1
        assert frame["summary"]["rx_bps"] == 800.0
        assert frame["switches"][0]["dpid"] == 1
        assert frame["switches"][0]["ports"][0]["port_no"] == 2
        assert frame["switches"][0]["ports"][0]["utilization"] == 800.0 / CAPACITY_BPS

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}
    assert broadcaster.subscriber_count == 0


def test_websocket_streams_heartbeats_without_samples() -> None:
    client, broadcaster = _live_client([])

    with client.websocket_connect("/ws/telemetry") as websocket:
        websocket.receive_json()
        websocket.portal.call(broadcaster.tick)

        assert websocket.receive_json() == {"type": "heartbeat", "at": "2026-10-20T12:05:00Z"}


def test_websocket_streams_alert_frames_after_the_kpi_frame(make_alert: MakeAlert) -> None:
    client, broadcaster = _live_client([], alerts=[make_alert(1, "open")])

    with client.websocket_connect("/ws/telemetry") as websocket:
        websocket.receive_json()
        websocket.portal.call(broadcaster.tick)

        assert websocket.receive_json()["type"] == "heartbeat"
        assert websocket.receive_json() == {
            "type": "alerts",
            "generated_at": "2026-10-20T12:05:00Z",
            "alerts": [
                {
                    "id": 1,
                    "seq": 1,
                    "dpid": 1,
                    "port_no": 1,
                    "metric": "rx_bps",
                    "severity": "warning",
                    "status": "open",
                    "opened_at": "2026-10-20T11:01:00Z",
                    "last_seen_at": "2026-10-20T11:02:00Z",
                    "resolved_at": None,
                    "acknowledged_at": None,
                    "value": 1000000.0,
                    "expected": 100000.0,
                    "zscore": 6.5,
                    "updated_at": "2026-10-20T11:02:00Z",
                }
            ],
        }


def test_websocket_sends_the_open_alert_snapshot_right_after_hello(make_alert: MakeAlert) -> None:
    client, broadcaster = _live_client([], alerts=[make_alert(1, "open")])

    with client.websocket_connect("/ws/telemetry") as first:
        first.receive_json()
        first.portal.call(broadcaster.tick)
        first.receive_json()
        first.receive_json()

    with client.websocket_connect("/ws/telemetry") as websocket:
        assert websocket.receive_json() == {"type": "hello", "version": "1.0.0"}
        snapshot = websocket.receive_json()

        assert snapshot["type"] == "alerts"
        assert snapshot["generated_at"] == "2026-10-20T12:05:00Z"
        assert [alert["id"] for alert in snapshot["alerts"]] == [1]
        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}


def test_websocket_closes_slow_consumers() -> None:
    client, broadcaster = _live_client([], queue_size=1)

    async def tick_twice_without_yielding() -> None:
        await broadcaster.tick()
        await broadcaster.tick()

    with client.websocket_connect("/ws/telemetry") as websocket:
        websocket.receive_json()
        websocket.portal.call(tick_twice_without_yielding)

        with pytest.raises(WebSocketDisconnect) as disconnect:
            websocket.receive_json()

    assert disconnect.value.code == 1013
    assert disconnect.value.reason == "slow consumer"
    assert broadcaster.subscriber_count == 0
