from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from netpulse_api.app import create_app
from netpulse_api.stats import (
    PortStatsPoint,
    PortStatsRange,
    PortStatsUnavailableError,
)

START = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
URL = "/api/v1/switches/1/ports/2/stats"


def _point(offset_seconds: int, samples: int = 1) -> PortStatsPoint:
    return PortStatsPoint(
        time=START + timedelta(seconds=offset_seconds),
        rx_packets=10 + offset_seconds,
        tx_packets=12,
        rx_bytes=1_500,
        tx_bytes=1_800,
        rx_dropped=0,
        tx_dropped=0,
        rx_errors=None,
        tx_errors=0,
        duration_sec=30 + offset_seconds,
        samples=samples,
    )


class InMemoryPortStatsQuery:
    def __init__(self, points: list[PortStatsPoint]) -> None:
        self.points = points
        self.requests: list[PortStatsRange] = []

    async def fetch(self, request: PortStatsRange) -> list[PortStatsPoint]:
        self.requests.append(request)
        return [p for p in self.points if request.start <= p.time < request.end][: request.limit]


class UnavailablePortStatsQuery:
    async def fetch(self, request: PortStatsRange) -> list[PortStatsPoint]:
        raise PortStatsUnavailableError("database down")


def _client(query: InMemoryPortStatsQuery | UnavailablePortStatsQuery | None) -> TestClient:
    return TestClient(create_app(database_probe=None, port_stats_query=query))


def _params(**overrides: str) -> dict[str, str]:
    params = {"from": "2026-10-20T12:00:00Z", "to": "2026-10-20T13:00:00Z"}
    params.update(overrides)
    return params


def test_returns_raw_points_within_the_range() -> None:
    query = InMemoryPortStatsQuery([_point(0), _point(5), _point(3_600)])

    response = _client(query).get(URL, params=_params())

    assert response.status_code == 200
    body = response.json()
    assert body["dpid"] == 1
    assert body["port_no"] == 2
    assert body["resolution"] == "raw"
    assert [point["rx_packets"] for point in body["points"]] == [10, 15]
    assert body["points"][0]["time"] == "2026-10-20T12:00:00Z"
    assert body["points"][0]["rx_errors"] is None
    assert query.requests == [
        PortStatsRange(
            dpid=1,
            port_no=2,
            start=START,
            end=START + timedelta(hours=1),
            resolution="raw",
            limit=1_000,
        )
    ]


def test_forwards_resolution_and_limit() -> None:
    query = InMemoryPortStatsQuery([_point(0, samples=12), _point(60, samples=12)])

    response = _client(query).get(URL, params=_params(resolution="1m", limit="1"))

    assert response.status_code == 200
    assert [point["samples"] for point in response.json()["points"]] == [12]
    assert query.requests[0].resolution == "1m"
    assert query.requests[0].limit == 1


def test_empty_range_returns_no_points() -> None:
    response = _client(InMemoryPortStatsQuery([])).get(URL, params=_params())

    assert response.status_code == 200
    assert response.json()["points"] == []


def test_one_minute_resolution_accepts_a_week() -> None:
    query = InMemoryPortStatsQuery([])

    response = _client(query).get(URL, params=_params(to="2026-10-27T12:00:00Z", resolution="1m"))

    assert response.status_code == 200


@pytest.mark.parametrize(
    "params",
    [
        pytest.param(_params(to="2026-10-20T12:00:00Z"), id="empty-range"),
        pytest.param(_params(to="2026-10-20T11:00:00Z"), id="reversed-range"),
        pytest.param(_params(to="2026-10-21T12:00:01Z"), id="raw-range-over-24h"),
        pytest.param(_params(to="2026-10-27T12:00:01Z", resolution="1m"), id="1m-range-over-7d"),
        pytest.param(_params(resolution="5m"), id="unknown-resolution"),
        pytest.param(_params(limit="0"), id="limit-too-small"),
        pytest.param(_params(limit="10001"), id="limit-too-large"),
        pytest.param(_params(**{"from": "2026-10-20T12:00:00"}), id="naive-from"),
        pytest.param({"to": "2026-10-20T13:00:00Z"}, id="missing-from"),
    ],
)
def test_rejects_invalid_parameters(params: dict[str, str]) -> None:
    query = InMemoryPortStatsQuery([])

    response = _client(query).get(URL, params=params)

    assert response.status_code == 422
    assert query.requests == []


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/switches/-1/ports/2/stats",
        f"/api/v1/switches/{2**64}/ports/2/stats",
        f"/api/v1/switches/1/ports/{2**32}/stats",
    ],
)
def test_rejects_out_of_range_identifiers(url: str) -> None:
    response = _client(InMemoryPortStatsQuery([])).get(url, params=_params())

    assert response.status_code == 422


def test_reports_unavailable_storage() -> None:
    response = _client(UnavailablePortStatsQuery()).get(URL, params=_params())

    assert response.status_code == 503


def test_reports_unavailable_when_no_database_is_configured() -> None:
    response = _client(None).get(URL, params=_params())

    assert response.status_code == 503
