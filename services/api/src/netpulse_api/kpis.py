from collections.abc import Iterable, Sequence
from datetime import timedelta
from itertools import groupby
from typing import Annotated, Final, Protocol, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from netpulse_api.capacity import LinkCapacity, resolve_capacity
from netpulse_core import (
    DatapathId,
    NetworkSummary,
    PortKpis,
    PortNumber,
    PortSample,
    compute_port_kpis,
    summarize_kpis,
)

MAX_RANGE: Final = timedelta(days=7)
DEFAULT_LIMIT = 1_000
MAX_LIMIT = 10_000

Limit = Annotated[int, Field(ge=1, le=MAX_LIMIT)]

type SamplePair = tuple[PortSample, PortSample]


class KpiUnavailableError(Exception):
    pass


class KpiRangeParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    start: AwareDatetime = Field(alias="from")
    end: AwareDatetime = Field(alias="to")
    limit: Limit = DEFAULT_LIMIT

    @model_validator(mode="after")
    def check_range(self) -> Self:
        if self.start >= self.end:
            raise ValueError("from must be earlier than to")
        if self.end - self.start > MAX_RANGE:
            raise ValueError(f"range exceeds {MAX_RANGE}")
        return self


class KpiRange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dpid: DatapathId
    port_no: PortNumber
    start: AwareDatetime
    end: AwareDatetime
    limit: Limit


class KpiHistoryQuery(Protocol):
    async def fetch(self, request: KpiRange) -> list[PortKpis]: ...


class LatestSamplesQuery(Protocol):
    async def fetch(self, dpid: DatapathId | None) -> list[SamplePair]: ...


class PortKpiSeries(BaseModel):
    model_config = ConfigDict(frozen=True)

    dpid: DatapathId
    port_no: PortNumber
    points: tuple[PortKpis, ...]


class SwitchKpis(BaseModel):
    model_config = ConfigDict(frozen=True)

    dpid: DatapathId
    generated_at: AwareDatetime
    ports: tuple[PortKpis, ...]


class NetworkKpiSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: AwareDatetime
    summary: NetworkSummary
    switches: tuple[SwitchKpis, ...]


def latest_port_kpis(pairs: Iterable[SamplePair], *, capacity: LinkCapacity) -> list[PortKpis]:
    resolver = resolve_capacity(capacity)
    return [
        compute_port_kpis(
            previous,
            current,
            link_capacity_bps=resolver.capacity_for(current.dpid, current.stats.port_no),
        )
        for previous, current in pairs
    ]


def switch_kpis(
    dpid: DatapathId, kpis: Iterable[PortKpis], *, generated_at: AwareDatetime
) -> SwitchKpis:
    ports = sorted((kpi for kpi in kpis if kpi.dpid == dpid), key=lambda kpi: kpi.port_no)
    return SwitchKpis(dpid=dpid, generated_at=generated_at, ports=tuple(ports))


def network_kpi_summary(
    kpis: Sequence[PortKpis], *, generated_at: AwareDatetime
) -> NetworkKpiSummary:
    by_switch = groupby(sorted(kpis, key=lambda kpi: kpi.dpid), key=lambda kpi: kpi.dpid)
    switches = tuple(
        switch_kpis(dpid, ports, generated_at=generated_at) for dpid, ports in by_switch
    )
    return NetworkKpiSummary(
        generated_at=generated_at, summary=summarize_kpis(kpis), switches=switches
    )
