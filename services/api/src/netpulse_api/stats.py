from datetime import timedelta
from typing import Annotated, Final, Literal, Protocol, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from netpulse_core import DatapathId, PortNumber

Resolution = Literal["raw", "1m"]

MAX_RANGE: Final[dict[Resolution, timedelta]] = {
    "raw": timedelta(hours=24),
    "1m": timedelta(days=7),
}
DEFAULT_LIMIT = 1_000
MAX_LIMIT = 10_000

Counter = Annotated[int, Field(ge=0)] | None
Limit = Annotated[int, Field(ge=1, le=MAX_LIMIT)]


class PortStatsUnavailableError(Exception):
    pass


class PortStatsPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    time: AwareDatetime
    rx_packets: Counter
    tx_packets: Counter
    rx_bytes: Counter
    tx_bytes: Counter
    rx_dropped: Counter
    tx_dropped: Counter
    rx_errors: Counter
    tx_errors: Counter
    duration_sec: Counter
    samples: Annotated[int, Field(ge=1)]


class PortStatsSeries(BaseModel):
    model_config = ConfigDict(frozen=True)

    dpid: DatapathId
    port_no: PortNumber
    resolution: Resolution
    points: tuple[PortStatsPoint, ...]


class PortStatsParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    start: AwareDatetime = Field(alias="from")
    end: AwareDatetime = Field(alias="to")
    resolution: Resolution = "raw"
    limit: Limit = DEFAULT_LIMIT

    @model_validator(mode="after")
    def check_range(self) -> Self:
        if self.start >= self.end:
            raise ValueError("from must be earlier than to")
        if self.end - self.start > MAX_RANGE[self.resolution]:
            raise ValueError(
                f"range exceeds {MAX_RANGE[self.resolution]} for {self.resolution} resolution"
            )
        return self


class PortStatsRange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dpid: DatapathId
    port_no: PortNumber
    start: AwareDatetime
    end: AwareDatetime
    resolution: Resolution
    limit: Limit


class PortStatsQuery(Protocol):
    async def fetch(self, request: PortStatsRange) -> list[PortStatsPoint]: ...
