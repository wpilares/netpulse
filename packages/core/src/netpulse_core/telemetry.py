from typing import Annotated, Final

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

DatapathId = Annotated[int, Field(ge=0, le=2**64 - 1)]
PortNumber = Annotated[int, Field(ge=0, le=2**32 - 1)]
Counter = Annotated[int, Field(ge=0)]

RESERVED_PORT_START: Final = 0xFFFFFF00


def is_reserved_port(port_no: int) -> bool:
    return port_no >= RESERVED_PORT_START


class TelemetryModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PortStats(TelemetryModel):
    port_no: PortNumber
    rx_packets: Counter
    tx_packets: Counter
    rx_bytes: Counter
    tx_bytes: Counter
    rx_dropped: Counter
    tx_dropped: Counter
    rx_errors: Counter
    tx_errors: Counter
    duration_sec: Counter


class SwitchPortStats(TelemetryModel):
    dpid: DatapathId
    collected_at: AwareDatetime
    ports: tuple[PortStats, ...]


class PortStatsReport(TelemetryModel):
    switches: tuple[SwitchPortStats, ...]
