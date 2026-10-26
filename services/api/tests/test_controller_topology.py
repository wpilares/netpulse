from collections.abc import Callable

import httpx2
import pytest

from netpulse_api.controller_topology import ControllerTopologyQuery
from netpulse_api.topology import ControllerTopology, TopologyUnavailableError

Handler = Callable[[httpx2.Request], httpx2.Response]

PAYLOAD = {
    "switches": [
        {"dpid": 1, "ports": [{"port_no": 1, "name": "s1-eth1", "hw_addr": "00:00:00:00:00:01"}]},
        {"dpid": 2, "ports": []},
    ],
    "links": [{"src": {"dpid": 1, "port_no": 1}, "dst": {"dpid": 2, "port_no": 1}}],
}


def _query(handler: Handler) -> ControllerTopologyQuery:
    http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handler), base_url="http://controller:8080"
    )
    return ControllerTopologyQuery(http)


async def test_fetch_returns_the_validated_controller_topology() -> None:
    requested: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requested.append(request.url.path)
        return httpx2.Response(200, json=PAYLOAD)

    topology = await _query(handler).fetch()

    assert requested == ["/topology"]
    assert topology == ControllerTopology.model_validate(PAYLOAD)
    assert topology.links[0].dst.port_no == 1


async def test_server_errors_are_unavailable() -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(500, text="boom")

    with pytest.raises(TopologyUnavailableError):
        await _query(handler).fetch()


async def test_timeouts_are_unavailable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("timed out", request=request)

    with pytest.raises(TopologyUnavailableError):
        await _query(handler).fetch()


async def test_invalid_payloads_are_unavailable() -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"switches": "nope", "links": []})

    with pytest.raises(TopologyUnavailableError):
        await _query(handler).fetch()
