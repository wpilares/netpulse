from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from netpulse_api.app import create_app
from netpulse_api.kpis import SamplePair
from netpulse_core import PortCounters, PortSample

SAMPLE_START = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

MakeSamplePair = Callable[[int, int], SamplePair]


class StubProbe:
    def __init__(self, *, reachable: bool) -> None:
        self.reachable = reachable

    async def is_reachable(self) -> bool:
        return self.reachable


@pytest.fixture
def make_client() -> Callable[[bool | None], TestClient]:
    def factory(database_reachable: bool | None) -> TestClient:
        probe = None if database_reachable is None else StubProbe(reachable=database_reachable)
        return TestClient(create_app(database_probe=probe))

    return factory


def _sample(dpid: int, port_no: int, offset_seconds: int, *, rx_bytes: int) -> PortSample:
    return PortSample(
        dpid=dpid,
        collected_at=SAMPLE_START + timedelta(seconds=offset_seconds),
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
            duration_sec=100 + offset_seconds,
        ),
    )


@pytest.fixture
def make_sample_pair() -> MakeSamplePair:
    def factory(dpid: int, port_no: int) -> SamplePair:
        return _sample(dpid, port_no, 0, rx_bytes=1_000), _sample(dpid, port_no, 10, rx_bytes=2_000)

    return factory
