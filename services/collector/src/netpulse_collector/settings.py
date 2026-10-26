from typing import Annotated, Literal, Self

from pydantic import AnyHttpUrl, Field, HttpUrl, PostgresDsn, model_validator

from netpulse_core import AlertPolicy, DetectionConfig, ServiceSettings

RepositoryKind = Literal["log", "timescale"]


class CollectorSettings(ServiceSettings, env_prefix="NETPULSE_COLLECTOR_", env_ignore_empty=True):
    controller_url: AnyHttpUrl = AnyHttpUrl("http://controller:8080")
    poll_interval_seconds: Annotated[float, Field(gt=0)] = 5.0
    request_timeout_seconds: Annotated[float, Field(gt=0)] = 3.0
    repository: RepositoryKind = "log"
    database_url: PostgresDsn | None = None
    write_attempts: Annotated[int, Field(ge=1)] = 3
    write_retry_base_seconds: Annotated[float, Field(gt=0)] = 0.5
    detection_enabled: bool = True
    link_capacity_bps: Annotated[int, Field(gt=0)] | None = 10_000_000
    detection_alpha: Annotated[float, Field(gt=0, le=1)] = 0.2
    detection_warmup_samples: Annotated[int, Field(ge=1)] = 12
    detection_warning_z: Annotated[float, Field(gt=0)] = 3.0
    detection_critical_z: Annotated[float, Field(gt=0)] = 5.0
    alert_resolve_after_seconds: Annotated[float, Field(ge=0)] = 60.0
    alert_cooldown_seconds: Annotated[float, Field(ge=0)] = 120.0
    alert_webhook_url: HttpUrl | None = None

    @model_validator(mode="after")
    def require_database_for_timescale(self) -> Self:
        if self.repository == "timescale" and self.database_url is None:
            raise ValueError("database_url is required when repository is timescale")
        return self

    @model_validator(mode="after")
    def require_consistent_detection_thresholds(self) -> Self:
        self.detection_config()
        return self

    def detection_config(self) -> DetectionConfig:
        return DetectionConfig(
            alpha=self.detection_alpha,
            warmup_samples=self.detection_warmup_samples,
            warning_z=self.detection_warning_z,
            critical_z=self.detection_critical_z,
        )

    def alert_policy(self) -> AlertPolicy:
        return AlertPolicy(
            resolve_after_seconds=self.alert_resolve_after_seconds,
            cooldown_seconds=self.alert_cooldown_seconds,
        )
