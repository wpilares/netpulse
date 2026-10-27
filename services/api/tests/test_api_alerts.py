from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from netpulse_api.alerts import (
    MAX_ALERT_LIMIT,
    Alert,
    AlertCommand,
    AlertsQuery,
    AlertStatusFilter,
    AlertsUnavailableError,
)
from netpulse_api.app import create_app
from netpulse_core import AlertStatus

ALERTS_URL = "/api/v1/alerts"

MakeAlert = Callable[[int, AlertStatus], Alert]


class InMemoryAlertStore:
    def __init__(self, alerts: list[Alert]) -> None:
        self.alerts = {alert.id: alert for alert in alerts}
        self.fetches: list[tuple[AlertStatusFilter, int]] = []
        self.acknowledgements: list[tuple[int, datetime]] = []

    async def fetch(self, status: AlertStatusFilter, *, limit: int) -> list[Alert]:
        self.fetches.append((status, limit))
        matching = [
            alert for alert in self.alerts.values() if status == "all" or alert.status == status
        ]
        return sorted(matching, key=lambda alert: alert.opened_at, reverse=True)[:limit]

    async def fetch_after(self, seq: int, *, limit: int = MAX_ALERT_LIMIT) -> list[Alert]:
        changed = [alert for alert in self.alerts.values() if alert.seq > seq]
        return sorted(changed, key=lambda alert: alert.seq)[:limit]

    async def acknowledge(self, alert_id: int, *, at: datetime) -> Alert | None:
        self.acknowledgements.append((alert_id, at))
        alert = self.alerts.get(alert_id)
        if alert is None:
            return None
        if alert.acknowledged_at is None:
            next_seq = max(stored.seq for stored in self.alerts.values()) + 1
            alert = alert.model_copy(
                update={"acknowledged_at": at, "updated_at": at, "seq": next_seq}
            )
            self.alerts[alert_id] = alert
        return alert


class UnavailableAlertStore:
    async def fetch(self, status: AlertStatusFilter, *, limit: int) -> list[Alert]:
        raise AlertsUnavailableError("database down")

    async def fetch_after(self, seq: int, *, limit: int = MAX_ALERT_LIMIT) -> list[Alert]:
        raise AlertsUnavailableError("database down")

    async def acknowledge(self, alert_id: int, *, at: datetime) -> Alert | None:
        raise AlertsUnavailableError("database down")


def _client(query: AlertsQuery | None = None, command: AlertCommand | None = None) -> TestClient:
    return TestClient(create_app(database_probe=None, alerts_query=query, alert_command=command))


def _store(make_alert: MakeAlert) -> InMemoryAlertStore:
    return InMemoryAlertStore(
        [make_alert(1, "open"), make_alert(2, "resolved"), make_alert(3, "open")]
    )


def test_lists_open_alerts_newest_first_by_default(make_alert: MakeAlert) -> None:
    store = _store(make_alert)

    response = _client(store).get(ALERTS_URL)

    assert response.status_code == 200
    body = response.json()
    assert datetime.fromisoformat(body["generated_at"]).tzinfo is not None
    assert [alert["id"] for alert in body["alerts"]] == [3, 1]
    assert body["alerts"][1] == {
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
    assert store.fetches == [("open", 100)]


@pytest.mark.parametrize(
    ("status", "expected_ids"),
    [("open", [3, 1]), ("resolved", [2]), ("all", [3, 2, 1])],
)
def test_filters_alerts_by_status(
    make_alert: MakeAlert, status: str, expected_ids: list[int]
) -> None:
    response = _client(_store(make_alert)).get(ALERTS_URL, params={"status": status})

    assert response.status_code == 200
    assert [alert["id"] for alert in response.json()["alerts"]] == expected_ids


def test_forwards_the_limit(make_alert: MakeAlert) -> None:
    store = _store(make_alert)

    response = _client(store).get(ALERTS_URL, params={"status": "all", "limit": "2"})

    assert response.status_code == 200
    assert [alert["id"] for alert in response.json()["alerts"]] == [3, 2]
    assert store.fetches == [("all", 2)]


@pytest.mark.parametrize(
    "params",
    [{"status": "closed"}, {"limit": "0"}, {"limit": "501"}, {"limit": "ten"}],
)
def test_rejects_invalid_parameters(make_alert: MakeAlert, params: dict[str, str]) -> None:
    response = _client(_store(make_alert)).get(ALERTS_URL, params=params)

    assert response.status_code == 422


def test_acknowledges_an_alert(make_alert: MakeAlert) -> None:
    store = _store(make_alert)

    response = _client(command=store).post(f"{ALERTS_URL}/3/ack")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 3
    assert body["status"] == "open"
    acknowledged_at = datetime.fromisoformat(body["acknowledged_at"])
    assert acknowledged_at.tzinfo is not None
    assert body["updated_at"] == body["acknowledged_at"]
    assert body["seq"] == 4
    assert store.acknowledgements == [(3, acknowledged_at)]
    assert store.acknowledgements[0][1].tzinfo is UTC


def test_acknowledging_twice_keeps_the_first_timestamp(make_alert: MakeAlert) -> None:
    client = _client(command=_store(make_alert))

    first = client.post(f"{ALERTS_URL}/1/ack").json()
    second = client.post(f"{ALERTS_URL}/1/ack").json()

    assert second == first
    assert first["acknowledged_at"] is not None
    assert first["seq"] == 4


def test_reports_unknown_alerts(make_alert: MakeAlert) -> None:
    response = _client(command=_store(make_alert)).post(f"{ALERTS_URL}/42/ack")

    assert response.status_code == 404
    assert response.json() == {"detail": "alert not found"}


def test_reports_unavailable_storage() -> None:
    client = _client(UnavailableAlertStore(), UnavailableAlertStore())

    listing = client.get(ALERTS_URL)
    acknowledgement = client.post(f"{ALERTS_URL}/1/ack")

    assert listing.status_code == 503
    assert listing.json() == {"detail": "storage is unavailable"}
    assert acknowledgement.status_code == 503
    assert acknowledgement.json() == {"detail": "storage is unavailable"}


def test_reports_unavailable_when_no_database_is_configured() -> None:
    client = _client()

    listing = client.get(ALERTS_URL)
    acknowledgement = client.post(f"{ALERTS_URL}/1/ack")

    assert listing.status_code == 503
    assert listing.json() == {"detail": "storage is not configured"}
    assert acknowledgement.status_code == 503
    assert acknowledgement.json() == {"detail": "storage is not configured"}
