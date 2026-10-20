import pytest
from pydantic import ValidationError

from netpulse_collector.settings import CollectorSettings


def test_defaults_target_the_compose_controller(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CONTROLLER_URL", "POLL_INTERVAL_SECONDS", "REQUEST_TIMEOUT_SECONDS"):
        monkeypatch.delenv(f"NETPULSE_COLLECTOR_{name}", raising=False)

    settings = CollectorSettings()

    assert str(settings.controller_url) == "http://controller:8080/"
    assert settings.poll_interval_seconds == 5.0
    assert settings.request_timeout_seconds == 3.0


def test_values_are_read_from_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_CONTROLLER_URL", "http://localhost:9090")
    monkeypatch.setenv("NETPULSE_COLLECTOR_POLL_INTERVAL_SECONDS", "0.5")

    settings = CollectorSettings()

    assert str(settings.controller_url) == "http://localhost:9090/"
    assert settings.poll_interval_seconds == 0.5


@pytest.mark.parametrize("interval", ["0", "-1"])
def test_poll_interval_must_be_positive(monkeypatch: pytest.MonkeyPatch, interval: str) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_POLL_INTERVAL_SECONDS", interval)

    with pytest.raises(ValidationError):
        CollectorSettings()


def test_controller_url_must_be_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_CONTROLLER_URL", "ftp://controller")

    with pytest.raises(ValidationError):
        CollectorSettings()
