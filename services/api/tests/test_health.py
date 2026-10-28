from collections.abc import Callable

from fastapi.testclient import TestClient

MakeClient = Callable[[bool | None], TestClient]


def test_health_reports_ok_when_database_check_is_disabled(make_client: MakeClient) -> None:
    response = make_client(None).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "disabled", "version": "1.1.0"}


def test_health_reports_ok_when_database_is_reachable(make_client: MakeClient) -> None:
    response = make_client(True).get("/health")

    assert response.status_code == 200
    assert response.json()["database"] == "up"


def test_health_is_unavailable_when_database_is_down(make_client: MakeClient) -> None:
    response = make_client(False).get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "down", "version": "1.1.0"}


def test_v1_info_exposes_service_metadata(make_client: MakeClient) -> None:
    response = make_client(None).get("/api/v1/info")

    assert response.status_code == 200
    assert response.json() == {"name": "netpulse", "version": "1.1.0"}
