from collections.abc import Callable

from fastapi.testclient import TestClient

MakeClient = Callable[[bool | None], TestClient]


def test_websocket_handshake_greets_the_client(make_client: MakeClient) -> None:
    with make_client(None).websocket_connect("/ws/telemetry") as websocket:
        assert websocket.receive_json() == {"type": "hello", "version": "0.1.0"}


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
