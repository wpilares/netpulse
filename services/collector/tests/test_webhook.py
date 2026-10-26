import json
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import httpx2
import pytest

from netpulse_collector.webhook import WebhookAlertNotifier, alert_payload
from netpulse_core import AlertEvent, AlertState
from netpulse_core.settings import HTTP_CLIENT_LOGGER, quiet_http_client_logging

WEBHOOK_URL = "https://hooks.example.test/netpulse"
Handler = Callable[[httpx2.Request], httpx2.Response]
T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

OPENED = AlertEvent(
    kind="opened",
    state=AlertState(
        key=(1, 2, "rx_bps"),
        severity="critical",
        opened_at=T0,
        last_seen_at=T0,
        value=16_000_000.0,
        expected=1_600.0,
        zscore=1_599.84,
        status="open",
        resolved_at=None,
    ),
)
RESOLVED = AlertEvent(
    kind="resolved",
    state=OPENED.state.model_copy(
        update={"status": "resolved", "resolved_at": datetime(2026, 10, 20, 12, 1, tzinfo=UTC)}
    ),
)


@pytest.fixture
def service_logging() -> Iterator[None]:
    http_logger = logging.getLogger(HTTP_CLIENT_LOGGER)
    previous = http_logger.level
    quiet_http_client_logging()
    yield
    http_logger.setLevel(previous)


def _notifier(
    handler: Handler, requests: list[httpx2.Request] | None = None
) -> WebhookAlertNotifier:
    def transport(request: httpx2.Request) -> httpx2.Response:
        if requests is not None:
            requests.append(request)
        return handler(request)

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(transport))
    return WebhookAlertNotifier(http, WEBHOOK_URL)


def test_alert_payload_flattens_the_key_and_serializes_timestamps() -> None:
    assert alert_payload(RESOLVED.state) == {
        "dpid": 1,
        "port_no": 2,
        "metric": "rx_bps",
        "severity": "critical",
        "status": "resolved",
        "opened_at": "2026-10-20T12:00:00Z",
        "last_seen_at": "2026-10-20T12:00:00Z",
        "resolved_at": "2026-10-20T12:01:00Z",
        "value": 16_000_000.0,
        "expected": 1_600.0,
        "zscore": 1_599.84,
    }


async def test_notify_posts_every_event_in_one_json_body() -> None:
    requests: list[httpx2.Request] = []
    notifier = _notifier(lambda _: httpx2.Response(202), requests)

    await notifier.notify([OPENED, RESOLVED])

    assert [str(request.url) for request in requests] == [WEBHOOK_URL]
    assert requests[0].method == "POST"
    assert requests[0].headers["content-type"] == "application/json"
    assert json.loads(requests[0].content) == {
        "events": [
            {"kind": "opened", "alert": alert_payload(OPENED.state)},
            {"kind": "resolved", "alert": alert_payload(RESOLVED.state)},
        ]
    }


async def test_notify_skips_the_request_without_events() -> None:
    requests: list[httpx2.Request] = []
    notifier = _notifier(lambda _: httpx2.Response(202), requests)

    await notifier.notify([])

    assert requests == []


@pytest.mark.usefixtures("service_logging")
async def test_server_errors_are_logged_without_the_url(caplog: pytest.LogCaptureFixture) -> None:
    notifier = _notifier(lambda _: httpx2.Response(500))

    with caplog.at_level(logging.DEBUG):
        await notifier.notify([OPENED])

    assert "HTTPStatusError" in caplog.text
    assert "500" in caplog.text
    assert WEBHOOK_URL not in caplog.text
    assert "hooks.example.test" not in caplog.text


@pytest.mark.usefixtures("service_logging")
async def test_transport_errors_are_logged_without_the_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError(f"connection refused by {WEBHOOK_URL}")

    notifier = _notifier(handler)

    with caplog.at_level(logging.DEBUG):
        await notifier.notify([OPENED])

    assert "ConnectError" in caplog.text
    assert WEBHOOK_URL not in caplog.text
    assert "hooks.example.test" not in caplog.text
