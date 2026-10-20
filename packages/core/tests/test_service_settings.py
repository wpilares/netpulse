import pytest
from pydantic import ValidationError

from netpulse_core.settings import ServiceSettings


class ExampleSettings(ServiceSettings, env_prefix="NETPULSE_EXAMPLE_"):
    pass


def test_log_level_defaults_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NETPULSE_EXAMPLE_LOG_LEVEL", raising=False)

    assert ExampleSettings().log_level == "INFO"


def test_log_level_is_read_from_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_EXAMPLE_LOG_LEVEL", "debug")

    assert ExampleSettings().log_level == "DEBUG"


def test_invalid_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_EXAMPLE_LOG_LEVEL", "verbose")

    with pytest.raises(ValidationError):
        ExampleSettings()
