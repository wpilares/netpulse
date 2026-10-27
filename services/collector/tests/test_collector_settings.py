import logging

import pytest
from pydantic import HttpUrl, ValidationError

from netpulse_collector.settings import CollectorSettings
from netpulse_core import DEFAULT_ROUTE_KINDS, AlertPolicy, AlertRoute, DetectionConfig
from netpulse_core.settings import HTTP_CLIENT_LOGGER, quiet_http_client_logging


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


def test_detection_defaults_match_the_core_models(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DETECTION_ENABLED",
        "LINK_CAPACITY_BPS",
        "DETECTION_ALPHA",
        "DETECTION_WARMUP_SAMPLES",
        "DETECTION_WARNING_Z",
        "DETECTION_CRITICAL_Z",
        "DETECTION_MIN_BPS_DELTA",
        "DETECTION_MIN_SIGMA_BPS",
        "DETECTION_MIN_SIGMA_RATE",
        "DETECTION_DROP_RATE_FLOOR",
        "DETECTION_ERROR_RATE_FLOOR",
        "ALERT_RESOLVE_AFTER_SECONDS",
        "ALERT_COOLDOWN_SECONDS",
        "ALERT_OPEN_AFTER_SIGNALS",
        "ALERT_WEBHOOK_URL",
    ):
        monkeypatch.delenv(f"NETPULSE_COLLECTOR_{name}", raising=False)

    settings = CollectorSettings()

    assert settings.detection_enabled is True
    assert settings.link_capacity_bps == 10_000_000
    assert settings.alert_webhook_url is None
    assert settings.detection_config() == DetectionConfig(min_bps_delta=1_000_000.0)
    assert settings.alert_policy() == AlertPolicy()


def test_throughput_floor_is_raised_above_the_core_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NETPULSE_COLLECTOR_DETECTION_MIN_BPS_DELTA", raising=False)

    settings = CollectorSettings()

    assert settings.detection_min_bps_delta == 1_000_000.0
    assert settings.detection_min_bps_delta > DetectionConfig().min_bps_delta


def test_detection_values_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_ENABLED", "false")
    monkeypatch.setenv("NETPULSE_COLLECTOR_LINK_CAPACITY_BPS", "1000000000")
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_ALPHA", "0.5")
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_WARMUP_SAMPLES", "3")
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_WARNING_Z", "2.5")
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_CRITICAL_Z", "4")
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_MIN_BPS_DELTA", "250000")
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_MIN_SIGMA_BPS", "20000")
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_MIN_SIGMA_RATE", "0.01")
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_DROP_RATE_FLOOR", "0.05")
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_ERROR_RATE_FLOOR", "0.001")
    monkeypatch.setenv("NETPULSE_COLLECTOR_ALERT_RESOLVE_AFTER_SECONDS", "30")
    monkeypatch.setenv("NETPULSE_COLLECTOR_ALERT_COOLDOWN_SECONDS", "45")
    monkeypatch.setenv("NETPULSE_COLLECTOR_ALERT_OPEN_AFTER_SIGNALS", "2")
    monkeypatch.setenv("NETPULSE_COLLECTOR_ALERT_WEBHOOK_URL", "https://hooks.example.test/x")

    settings = CollectorSettings()

    assert settings.detection_enabled is False
    assert settings.link_capacity_bps == 1_000_000_000
    assert settings.detection_config() == DetectionConfig(
        alpha=0.5,
        warmup_samples=3,
        warning_z=2.5,
        critical_z=4.0,
        min_bps_delta=250_000.0,
        min_sigma_bps=20_000.0,
        min_sigma_rate=0.01,
        drop_rate_floor=0.05,
        error_rate_floor=0.001,
    )
    assert settings.alert_policy() == AlertPolicy(
        resolve_after_seconds=30.0, cooldown_seconds=45.0, open_after_signals=2
    )
    assert str(settings.alert_webhook_url) == "https://hooks.example.test/x"


def test_empty_webhook_url_means_no_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_ALERT_WEBHOOK_URL", "")

    settings = CollectorSettings()

    assert settings.alert_webhook_url is None


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DETECTION_MIN_BPS_DELTA", "0"),
        ("DETECTION_MIN_BPS_DELTA", "-1"),
        ("DETECTION_MIN_SIGMA_BPS", "0"),
        ("DETECTION_MIN_SIGMA_RATE", "0"),
        ("DETECTION_DROP_RATE_FLOOR", "-0.1"),
        ("DETECTION_DROP_RATE_FLOOR", "1.5"),
        ("DETECTION_ERROR_RATE_FLOOR", "-0.1"),
        ("DETECTION_ERROR_RATE_FLOOR", "1.5"),
        ("ALERT_OPEN_AFTER_SIGNALS", "0"),
    ],
)
def test_floors_and_confirmation_reject_out_of_range_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(f"NETPULSE_COLLECTOR_{name}", value)

    with pytest.raises(ValidationError, match=name.lower()):
        CollectorSettings()


def test_critical_z_must_exceed_warning_z(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_WARNING_Z", "5")
    monkeypatch.setenv("NETPULSE_COLLECTOR_DETECTION_CRITICAL_Z", "5")

    with pytest.raises(ValidationError, match="critical_z"):
        CollectorSettings()


def test_quiet_http_client_logging_hides_request_lines(caplog: pytest.LogCaptureFixture) -> None:
    http_logger = logging.getLogger(HTTP_CLIENT_LOGGER)
    previous = http_logger.level
    try:
        quiet_http_client_logging()
        with caplog.at_level(logging.DEBUG):
            http_logger.info("HTTP Request: POST https://hooks.example.test/secret-token")
            http_logger.warning("HTTP Request: retrying")
    finally:
        http_logger.setLevel(previous)

    assert [record.getMessage() for record in caplog.records] == ["HTTP Request: retrying"]


def test_no_webhook_and_no_routes_means_no_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ALERT_WEBHOOK_URL", "ALERT_ROUTES"):
        monkeypatch.delenv(f"NETPULSE_COLLECTOR_{name}", raising=False)

    settings = CollectorSettings()

    assert settings.alert_routes == ""
    assert settings.routes() == ()


def test_webhook_url_becomes_the_default_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_ALERT_WEBHOOK_URL", "https://hooks.example.test/x")
    monkeypatch.delenv("NETPULSE_COLLECTOR_ALERT_ROUTES", raising=False)

    settings = CollectorSettings()

    assert settings.routes() == (
        AlertRoute(name="default", webhook_url=HttpUrl("https://hooks.example.test/x")),
    )
    assert settings.routes()[0].kinds == DEFAULT_ROUTE_KINDS


def test_routes_are_parsed_after_the_default_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_ALERT_WEBHOOK_URL", "https://hooks.example.test/x")
    monkeypatch.setenv(
        "NETPULSE_COLLECTOR_ALERT_ROUTES",
        '[{"name": "pager", "webhook_url": "https://pager.example.test", '
        '"min_severity": "critical", "metrics": ["drop_rate"], "kinds": ["opened", "resolved"]}, '
        '{"name": "audit"}]',
    )

    settings = CollectorSettings()

    assert settings.routes() == (
        AlertRoute(name="default", webhook_url=HttpUrl("https://hooks.example.test/x")),
        AlertRoute(
            name="pager",
            webhook_url=HttpUrl("https://pager.example.test"),
            min_severity="critical",
            metrics=("drop_rate",),
            kinds=("opened", "resolved"),
        ),
        AlertRoute(name="audit"),
    )


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"name": "pager"}',
        '[{"webhook_url": "x"}]',
        '[{"name": "pager", "webhook_url": "not a url"}]',
        '[{"name": "pager", "metrics": []}]',
    ],
)
def test_invalid_routes_fail_at_settings_time(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("NETPULSE_COLLECTOR_ALERT_ROUTES", raw)

    with pytest.raises(ValidationError, match="alert routes must be a JSON array"):
        CollectorSettings()


def test_retention_defaults_to_a_week_checked_hourly(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ALERT_RETENTION_DAYS", "ALERT_RETENTION_EVERY_CYCLES"):
        monkeypatch.delenv(f"NETPULSE_COLLECTOR_{name}", raising=False)

    settings = CollectorSettings()

    assert settings.alert_retention_days == 7
    assert settings.alert_retention_every_cycles == 720


@pytest.mark.parametrize("name", ["ALERT_RETENTION_DAYS", "ALERT_RETENTION_EVERY_CYCLES"])
def test_retention_values_must_be_at_least_one(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(f"NETPULSE_COLLECTOR_{name}", "0")

    with pytest.raises(ValidationError, match=name.lower()):
        CollectorSettings()
