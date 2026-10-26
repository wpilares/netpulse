from typing import Annotated

from pydantic import Field, HttpUrl, PostgresDsn

from netpulse_core import ServiceSettings


class ApiSettings(ServiceSettings, env_prefix="NETPULSE_API_"):
    host: str = "127.0.0.1"
    port: Annotated[int, Field(ge=1, le=65_535)] = 8000
    database_url: PostgresDsn | None = None
    database_timeout_seconds: Annotated[float, Field(gt=0)] = 2.0
    database_pool_size: Annotated[int, Field(ge=1)] = 4
    link_capacity_bps: Annotated[int, Field(gt=0)] | None = 10_000_000
    live_interval_seconds: Annotated[float, Field(gt=0)] = 5.0
    live_queue_size: Annotated[int, Field(ge=1)] = 16
    live_lookback_seconds: Annotated[int, Field(ge=1)] = 120
    controller_url: HttpUrl | None = None
    controller_timeout_seconds: Annotated[float, Field(gt=0)] = 2.0
