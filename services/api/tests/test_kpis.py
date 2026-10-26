from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from netpulse_api.app import create_app
from netpulse_api.kpis import (
    KpiHistoryQuery,
    KpiRange,
    KpiUnavailableError,
    LatestSamplesQuery,
    SamplePair,
    latest_port_kpis,
    network_kpi_summary,
)
from netpulse_api.settings import ApiSettings
from netpulse_core import (
    DatapathId,
    PortCounters,
    PortKpis,
    PortSample,
    compute_port_kpis,
    summarize_kpis,
)

START = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
CAPACITY_BPS = 10_000_000
HISTORY_URL = "/api/v1/switches/1/ports/2/kpis"
SWITCH_URL = "/api/v1/switches/1/kpis"
SUMMARY_URL = "/api/v1/kpis/summary"


def _sample(
    dpid: int, port_no: int, offset_seconds: int, *, rx_bytes: int, duration_sec: int | None
) -> PortSample:
    return PortSample(
        dpid=dpid,
        collected_at=START + timedelta(seconds=offset_seconds),
        stats=PortCounters(
            port_no=port_no,
            rx_packets=offset_seconds,
            tx_packets=offset_seconds,
            rx_bytes=rx_bytes,
            tx_bytes=rx_bytes // 2,
            rx_dropped=0,
            tx_dropped=0,
            rx_errors=None,
            tx_errors=0,
            duration_sec=duration_sec,
        ),
    )


def _pair(dpid: int, port_no: int, *, reset: bool = False) -> SamplePair:
    previous = _sample(dpid, port_no, 0, rx_bytes=1_000, duration_sec=100)
    current = _sample(
        dpid, port_no, 10, rx_bytes=0 if reset else 2_000, duration_sec=0 if reset else 110
    )
    return previous, current


def _kpi(dpid: int, port_no: int, offset_seconds: int) -> PortKpis:
    return PortKpis(
        dpid=dpid,
        port_no=port_no,
        computed_at=START + timedelta(seconds=offset_seconds),
        interval_seconds=60.0,
        rx_bps=800.0,
        tx_bps=400.0,
        rx_pps=1.0,
        tx_pps=1.0,
        drop_rate=0.0,
        error_rate=None,
        utilization=0.00008,
        counter_reset=False,
    )


class InMemoryKpiHistoryQuery:
    def __init__(self, points: list[PortKpis]) -> None:
        self.points = points
        self.requests: list[KpiRange] = []

    async def fetch(self, request: KpiRange) -> list[PortKpis]:
        self.requests.append(request)
        matching = [
            point
            for point in self.points
            if point.dpid == request.dpid
            and point.port_no == request.port_no
            and request.start <= point.computed_at < request.end
        ]
        return matching[: request.limit]


class UnavailableKpiHistoryQuery:
    async def fetch(self, request: KpiRange) -> list[PortKpis]:
        raise KpiUnavailableError("database down")


class InMemoryLatestSamplesQuery:
    def __init__(self, pairs: list[SamplePair]) -> None:
        self.pairs = pairs
        self.requests: list[DatapathId | None] = []

    async def fetch(self, dpid: DatapathId | None) -> list[SamplePair]:
        self.requests.append(dpid)
        return [pair for pair in self.pairs if dpid is None or pair[1].dpid == dpid]


class UnavailableLatestSamplesQuery:
    async def fetch(self, dpid: DatapathId | None) -> list[SamplePair]:
        raise KpiUnavailableError("database down")


class PortCapacityStub:
    def __init__(self, capacities: dict[tuple[int, int], int]) -> None:
        self._capacities = capacities
        self.refreshes = 0

    async def refresh(self) -> None:
        self.refreshes += 1

    def capacity_for(self, dpid: int, port_no: int) -> int | None:
        return self._capacities.get((dpid, port_no))


def _client(
    history: KpiHistoryQuery | None = None,
    latest: LatestSamplesQuery | None = None,
    *,
    link_capacity_bps: int | None = CAPACITY_BPS,
    capacity: PortCapacityStub | None = None,
) -> TestClient:
    return TestClient(
        create_app(
            database_probe=None,
            kpi_history=history,
            latest_samples=latest,
            link_capacity_bps=link_capacity_bps,
            capacity=capacity,
        )
    )


def _params(**overrides: str) -> dict[str, str]:
    params = {"from": "2026-10-20T12:00:00Z", "to": "2026-10-20T13:00:00Z"}
    params.update(overrides)
    return params


def test_history_returns_points_within_the_range() -> None:
    history = InMemoryKpiHistoryQuery(
        [_kpi(1, 2, 60), _kpi(1, 2, 120), _kpi(1, 2, 3_600), _kpi(1, 3, 60), _kpi(2, 2, 60)]
    )

    response = _client(history).get(HISTORY_URL, params=_params())

    assert response.status_code == 200
    body = response.json()
    assert body["dpid"] == 1
    assert body["port_no"] == 2
    assert [point["computed_at"] for point in body["points"]] == [
        "2026-10-20T12:01:00Z",
        "2026-10-20T12:02:00Z",
    ]
    assert body["points"][0]["rx_bps"] == 800.0
    assert body["points"][0]["error_rate"] is None
    assert body["points"][0]["counter_reset"] is False
    assert history.requests == [
        KpiRange(dpid=1, port_no=2, start=START, end=START + timedelta(hours=1), limit=1_000)
    ]


def test_history_forwards_limit() -> None:
    history = InMemoryKpiHistoryQuery([_kpi(1, 2, 60), _kpi(1, 2, 120)])

    response = _client(history).get(HISTORY_URL, params=_params(limit="1"))

    assert response.status_code == 200
    assert len(response.json()["points"]) == 1
    assert history.requests[0].limit == 1


def test_history_accepts_a_week() -> None:
    response = _client(InMemoryKpiHistoryQuery([])).get(
        HISTORY_URL, params=_params(to="2026-10-27T12:00:00Z")
    )

    assert response.status_code == 200
    assert response.json()["points"] == []


@pytest.mark.parametrize(
    "params",
    [
        pytest.param(_params(to="2026-10-20T12:00:00Z"), id="empty-range"),
        pytest.param(_params(to="2026-10-20T11:00:00Z"), id="reversed-range"),
        pytest.param(_params(to="2026-10-27T12:00:01Z"), id="range-over-7d"),
        pytest.param(_params(limit="0"), id="limit-too-small"),
        pytest.param(_params(limit="10001"), id="limit-too-large"),
        pytest.param(_params(**{"from": "2026-10-20T12:00:00"}), id="naive-from"),
        pytest.param({"to": "2026-10-20T13:00:00Z"}, id="missing-from"),
        pytest.param(_params(resolution="1m"), id="unknown-parameter"),
    ],
)
def test_history_rejects_invalid_parameters(params: dict[str, str]) -> None:
    history = InMemoryKpiHistoryQuery([])

    response = _client(history).get(HISTORY_URL, params=params)

    assert response.status_code == 422
    assert history.requests == []


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/switches/-1/ports/2/kpis",
        f"/api/v1/switches/{2**64}/ports/2/kpis",
        f"/api/v1/switches/1/ports/{2**32}/kpis",
        "/api/v1/switches/-1/kpis",
        f"/api/v1/switches/{2**64}/kpis",
    ],
)
def test_rejects_out_of_range_identifiers(url: str) -> None:
    response = _client(InMemoryKpiHistoryQuery([]), InMemoryLatestSamplesQuery([])).get(
        url, params=_params()
    )

    assert response.status_code == 422


def test_switch_kpis_computes_the_latest_kpi_per_port() -> None:
    latest = InMemoryLatestSamplesQuery([_pair(1, 2), _pair(1, 1), _pair(2, 1)])

    response = _client(latest=latest).get(SWITCH_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["dpid"] == 1
    assert datetime.fromisoformat(body["generated_at"]).tzinfo is not None
    assert [port["port_no"] for port in body["ports"]] == [1, 2]
    port = body["ports"][0]
    assert port["computed_at"] == "2026-10-20T12:00:10Z"
    assert port["interval_seconds"] == 10.0
    assert port["rx_bps"] == 800.0
    assert port["tx_bps"] == 400.0
    assert port["rx_pps"] == 1.0
    assert port["utilization"] == 800.0 / CAPACITY_BPS
    assert port["error_rate"] is None
    assert port["counter_reset"] is False
    assert latest.requests == [1]


def test_switch_kpis_reports_counter_resets() -> None:
    latest = InMemoryLatestSamplesQuery([_pair(1, 2, reset=True)])

    response = _client(latest=latest).get(SWITCH_URL)

    port = response.json()["ports"][0]
    assert port["counter_reset"] is True
    assert port["rx_bps"] is None
    assert port["utilization"] is None


def test_switch_kpis_without_capacity_has_no_utilization() -> None:
    latest = InMemoryLatestSamplesQuery([_pair(1, 2)])

    response = _client(latest=latest, link_capacity_bps=None).get(SWITCH_URL)

    port = response.json()["ports"][0]
    assert port["rx_bps"] == 800.0
    assert port["utilization"] is None


def test_switch_kpis_use_the_capacity_resolver_per_port() -> None:
    latest = InMemoryLatestSamplesQuery([_pair(1, 1), _pair(1, 2)])
    capacity = PortCapacityStub({(1, 1): 1_000})

    response = _client(latest=latest, capacity=capacity).get(SWITCH_URL)

    assert [port["utilization"] for port in response.json()["ports"]] == [0.8, None]
    assert capacity.refreshes == 1


def test_switch_without_samples_has_no_ports() -> None:
    response = _client(latest=InMemoryLatestSamplesQuery([_pair(2, 1)])).get(SWITCH_URL)

    assert response.status_code == 200
    assert response.json()["ports"] == []


def test_summary_aggregates_every_switch_with_core_semantics() -> None:
    pairs = [_pair(2, 1), _pair(1, 2, reset=True), _pair(1, 1)]
    latest = InMemoryLatestSamplesQuery(pairs)
    expected_kpis = [
        compute_port_kpis(previous, current, link_capacity_bps=CAPACITY_BPS)
        for previous, current in pairs
    ]

    response = _client(latest=latest).get(SUMMARY_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == summarize_kpis(expected_kpis).model_dump(mode="json")
    assert body["summary"]["ports"] == 3
    assert body["summary"]["switches"] == 2
    assert body["summary"]["rx_bps"] == 1_600.0
    assert body["summary"]["counter_resets"] == 1
    assert [switch["dpid"] for switch in body["switches"]] == [1, 2]
    assert [[port["port_no"] for port in switch["ports"]] for switch in body["switches"]] == [
        [1, 2],
        [1],
    ]
    assert body["switches"][0]["generated_at"] == body["generated_at"]
    assert latest.requests == [None]


def test_summary_without_samples_is_empty() -> None:
    response = _client(latest=InMemoryLatestSamplesQuery([])).get(SUMMARY_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["switches"] == []
    assert body["summary"]["ports"] == 0
    assert body["summary"]["rx_bps"] is None


@pytest.mark.parametrize("url", [HISTORY_URL, SWITCH_URL, SUMMARY_URL])
def test_reports_unavailable_storage(url: str) -> None:
    client = _client(UnavailableKpiHistoryQuery(), UnavailableLatestSamplesQuery())

    response = client.get(url, params=_params())

    assert response.status_code == 503


@pytest.mark.parametrize("url", [HISTORY_URL, SWITCH_URL, SUMMARY_URL])
def test_reports_unavailable_when_no_database_is_configured(url: str) -> None:
    response = _client().get(url, params=_params())

    assert response.status_code == 503


def test_latest_port_kpis_keeps_pair_order_and_core_semantics() -> None:
    pairs = [_pair(1, 2), _pair(1, 1, reset=True)]

    kpis = latest_port_kpis(pairs, capacity=CAPACITY_BPS)

    assert kpis == [
        compute_port_kpis(*pairs[0], link_capacity_bps=CAPACITY_BPS),
        compute_port_kpis(*pairs[1], link_capacity_bps=CAPACITY_BPS),
    ]


def test_network_kpi_summary_groups_sorted_switches_and_ports() -> None:
    kpis = [_kpi(2, 1, 60), _kpi(1, 3, 60), _kpi(1, 1, 60)]

    summary = network_kpi_summary(kpis, generated_at=START)

    assert summary.generated_at == START
    assert summary.summary == summarize_kpis(kpis)
    assert [(switch.dpid, switch.generated_at) for switch in summary.switches] == [
        (1, START),
        (2, START),
    ]
    assert [[port.port_no for port in switch.ports] for switch in summary.switches] == [
        [1, 3],
        [1],
    ]


def test_link_capacity_setting_defaults_to_ten_megabits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NETPULSE_API_LINK_CAPACITY_BPS", raising=False)
    assert ApiSettings().link_capacity_bps == 10_000_000

    monkeypatch.setenv("NETPULSE_API_LINK_CAPACITY_BPS", "0")
    with pytest.raises(ValidationError):
        ApiSettings()
