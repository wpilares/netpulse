import json
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from types import TracebackType
from wsgiref.types import WSGIEnvironment
from wsgiref.util import setup_testing_defaults

from netpulse_controller.rest import create_rest_app
from netpulse_controller.stats_store import PortCounters, StatsStore

type OptExcInfo = tuple[type[BaseException], BaseException, TracebackType] | tuple[None, None, None]


class Captured:
    status = ""
    headers: list[tuple[str, str]]

    def __call__(
        self, status: str, headers: list[tuple[str, str]], _exc_info: OptExcInfo | None = None, /
    ) -> Callable[[bytes], object]:
        self.status = status
        self.headers = headers
        return self.write

    def write(self, _data: bytes) -> object:
        return None


def _call(store: StatsStore, path: str, method: str = "GET") -> tuple[str, object]:
    environ: WSGIEnvironment = {}
    setup_testing_defaults(environ)
    environ["PATH_INFO"] = path
    environ["REQUEST_METHOD"] = method
    captured = Captured()
    body: Iterable[bytes] = create_rest_app(store)(environ, captured)
    return captured.status, json.loads(b"".join(body))


def test_health_is_ok() -> None:
    assert _call(StatsStore(), "/health") == ("200 OK", {"status": "ok"})


def test_switches_lists_connected_datapaths() -> None:
    store = StatsStore()
    store.register(3)

    assert _call(store, "/switches") == ("200 OK", {"switches": [3]})


def test_port_stats_returns_the_store_report() -> None:
    store = StatsStore()
    store.register(1)
    store.record(
        1,
        (PortCounters(1, 1, 1, 1, 1, 0, 0, 0, 0, 5),),
        datetime(2026, 10, 20, tzinfo=UTC),
    )

    status, payload = _call(store, "/stats/ports")

    assert status == "200 OK"
    assert payload == store.port_stats_report()


def test_unknown_paths_are_not_found() -> None:
    assert _call(StatsStore(), "/nope") == ("404 Not Found", {"error": "not found"})


def test_only_get_is_allowed() -> None:
    assert _call(StatsStore(), "/health", method="POST") == (
        "405 Method Not Allowed",
        {"error": "method not allowed"},
    )
