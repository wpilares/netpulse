import pytest
from pydantic import ValidationError

from netpulse_api.settings import ApiSettings


def test_database_check_is_disabled_without_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NETPULSE_API_DATABASE_URL", raising=False)

    assert ApiSettings().database_url is None


def test_database_url_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_API_DATABASE_URL", "postgresql://netpulse:secret@db:5432/netpulse")

    settings = ApiSettings()

    assert settings.database_url is not None
    assert settings.database_url.hosts()[0]["host"] == "db"


def test_database_pool_size_defaults_and_rejects_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NETPULSE_API_DATABASE_POOL_SIZE", raising=False)
    assert ApiSettings().database_pool_size == 4

    monkeypatch.setenv("NETPULSE_API_DATABASE_POOL_SIZE", "0")
    with pytest.raises(ValidationError):
        ApiSettings()


def test_live_settings_have_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LIVE_INTERVAL_SECONDS", "LIVE_QUEUE_SIZE", "LIVE_LOOKBACK_SECONDS"):
        monkeypatch.delenv(f"NETPULSE_API_{name}", raising=False)

    settings = ApiSettings()

    assert settings.live_interval_seconds == 5.0
    assert settings.live_queue_size == 16
    assert settings.live_lookback_seconds == 120


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LIVE_INTERVAL_SECONDS", "0"),
        ("LIVE_QUEUE_SIZE", "0"),
        ("LIVE_LOOKBACK_SECONDS", "-1"),
    ],
)
def test_live_settings_reject_non_positive_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(f"NETPULSE_API_{name}", value)

    with pytest.raises(ValidationError):
        ApiSettings()


def test_controller_is_not_configured_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CONTROLLER_URL", "CONTROLLER_TIMEOUT_SECONDS"):
        monkeypatch.delenv(f"NETPULSE_API_{name}", raising=False)

    settings = ApiSettings()

    assert settings.controller_url is None
    assert settings.controller_timeout_seconds == 2.0


def test_controller_url_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_API_CONTROLLER_URL", "http://controller:8080")
    monkeypatch.setenv("NETPULSE_API_CONTROLLER_TIMEOUT_SECONDS", "0.5")

    settings = ApiSettings()

    assert settings.controller_url is not None
    assert settings.controller_url.host == "controller"
    assert settings.controller_timeout_seconds == 0.5


def test_controller_timeout_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_API_CONTROLLER_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        ApiSettings()
