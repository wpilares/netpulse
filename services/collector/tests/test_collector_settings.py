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


def test_repository_defaults_to_logging_without_a_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("REPOSITORY", "DATABASE_URL"):
        monkeypatch.delenv(f"NETPULSE_COLLECTOR_{name}", raising=False)

    settings = CollectorSettings()

    assert settings.repository == "log"
    assert settings.database_url is None
    assert settings.write_attempts == 3
    assert settings.write_retry_base_seconds == 0.5


def test_timescale_repository_reads_the_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_REPOSITORY", "timescale")
    monkeypatch.setenv(
        "NETPULSE_COLLECTOR_DATABASE_URL", "postgresql://netpulse:secret@db:5432/netpulse"
    )

    settings = CollectorSettings()

    assert settings.repository == "timescale"
    assert settings.database_url is not None
    assert settings.database_url.hosts()[0]["host"] == "db"


def test_timescale_repository_requires_a_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_REPOSITORY", "timescale")
    monkeypatch.delenv("NETPULSE_COLLECTOR_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError, match="database_url"):
        CollectorSettings()
