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
