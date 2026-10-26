from typing import Annotated, Final, Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from netpulse_core import AlertStatus, DatapathId, Metric, PortNumber, Severity

AlertStatusFilter = Literal["open", "resolved", "all"]

DEFAULT_ALERT_LIMIT: Final = 100
MAX_ALERT_LIMIT: Final = 500

AlertLimit = Annotated[int, Field(ge=1, le=MAX_ALERT_LIMIT)]


class AlertsUnavailableError(Exception):
    pass


class Alert(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    dpid: DatapathId
    port_no: PortNumber
    metric: Metric
    severity: Severity
    status: AlertStatus
    opened_at: AwareDatetime
    last_seen_at: AwareDatetime
    resolved_at: AwareDatetime | None
    acknowledged_at: AwareDatetime | None
    value: float
    expected: float
    zscore: float
    updated_at: AwareDatetime


class AlertListParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: AlertStatusFilter = "open"
    limit: AlertLimit = DEFAULT_ALERT_LIMIT


class AlertList(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: AwareDatetime
    alerts: tuple[Alert, ...]


class AlertsQuery(Protocol):
    async def fetch(self, status: AlertStatusFilter, *, limit: int) -> list[Alert]: ...

    async def fetch_updated_since(self, since: AwareDatetime) -> list[Alert]: ...


class AlertCommand(Protocol):
    async def acknowledge(self, alert_id: int, *, at: AwareDatetime) -> Alert | None: ...
