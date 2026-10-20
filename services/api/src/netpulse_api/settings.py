from typing import Annotated

from pydantic import Field, PostgresDsn

from netpulse_core import ServiceSettings


class ApiSettings(ServiceSettings, env_prefix="NETPULSE_API_"):
    host: str = "127.0.0.1"
    port: Annotated[int, Field(ge=1, le=65_535)] = 8000
    database_url: PostgresDsn | None = None
    database_timeout_seconds: Annotated[float, Field(gt=0)] = 2.0
