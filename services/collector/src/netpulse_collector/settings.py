from typing import Annotated

from pydantic import AnyHttpUrl, Field

from netpulse_core import ServiceSettings


class CollectorSettings(ServiceSettings, env_prefix="NETPULSE_COLLECTOR_"):
    controller_url: AnyHttpUrl = AnyHttpUrl("http://controller:8080")
    poll_interval_seconds: Annotated[float, Field(gt=0)] = 5.0
    request_timeout_seconds: Annotated[float, Field(gt=0)] = 3.0
