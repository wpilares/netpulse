import asyncio
from collections.abc import Callable

import httpx2
import pytest

from netpulse_collector.controller_client import ControllerClient
from netpulse_collector.poller import poll_once, run_polling
from netpulse_core import PortStatsReport

REPORT_PAYLOAD = {
    "switches": [
        {
            "dpid": 1,
            "collected_at": "2026-10-20T12:00:00Z",
            "ports": [
                {
                    "port_no": 1,
                    "rx_packets": 10,
                    "tx_packets": 12,
                    "rx_bytes": 1500,
                    "tx_bytes": 1800,
                    "rx_dropped": 0,
                    "tx_dropped": 0,
                    "rx_errors": 0,
                    "tx_errors": 0,
                    "duration_sec": 30,
                }
            ],
        }
    ]
}

Handler = Callable[[httpx2.Request], httpx2.Response]


class RecordingRepository:
    def __init__(self) -> None:
        self.saved: list[PortStatsReport] = []

    async def save(self, report: PortStatsReport) -> None:
        self.saved.append(report)


def _client(handler: Handler) -> ControllerClient:
    transport = httpx2.MockTransport(handler)
    http = httpx2.AsyncClient(transport=transport, base_url="http://controller:8080")
    return ControllerClient(http)


async def test_poll_once_fetches_port_stats_and_stores_them() -> None:
    requested: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requested.append(request.url.path)
        return httpx2.Response(200, json=REPORT_PAYLOAD)

    repository = RecordingRepository()

    report = await poll_once(_client(handler), repository)

    assert requested == ["/stats/ports"]
    assert repository.saved == [report]
    assert report.switches[0].ports[0].tx_bytes == 1800


async def test_poll_once_raises_on_controller_errors() -> None:
    client = _client(lambda _: httpx2.Response(503))

    with pytest.raises(httpx2.HTTPStatusError):
        await poll_once(client, RecordingRepository())


async def test_run_polling_survives_failures_until_stopped() -> None:
    responses = iter([httpx2.Response(500), httpx2.Response(200, json=REPORT_PAYLOAD)])
    repository = RecordingRepository()
    stop = asyncio.Event()

    def handler(_: httpx2.Request) -> httpx2.Response:
        response = next(responses)
        if response.status_code == 200:
            stop.set()
        return response

    await asyncio.wait_for(
        run_polling(_client(handler), repository, interval_seconds=0.01, stop=stop),
        timeout=1,
    )

    assert len(repository.saved) == 1
