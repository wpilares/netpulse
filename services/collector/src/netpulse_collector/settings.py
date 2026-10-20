from typing import Annotated, Literal, Self

from pydantic import AnyHttpUrl, Field, PostgresDsn, model_validator

from netpulse_core import ServiceSettings

RepositoryKind = Literal["log", "timescale"]


class CollectorSettings(ServiceSettings, env_prefix="NETPULSE_COLLECTOR_"):
    controller_url: AnyHttpUrl = AnyHttpUrl("http://controller:8080")
    poll_interval_seconds: Annotated[float, Field(gt=0)] = 5.0
    request_timeout_seconds: Annotated[float, Field(gt=0)] = 3.0
    repository: RepositoryKind = "log"
    database_url: PostgresDsn | None = None
    write_attempts: Annotated[int, Field(ge=1)] = 3
    write_retry_base_seconds: Annotated[float, Field(gt=0)] = 0.5

    @model_validator(mode="after")
    def require_database_for_timescale(self) -> Self:
        if self.repository == "timescale" and self.database_url is None:
            raise ValueError("database_url is required when repository is timescale")
        return self
