from collections.abc import Iterable, Sequence

from pydantic import AwareDatetime

from netpulse_core.telemetry import (
    Counter,
    DatapathId,
    PortNumber,
    SwitchPortStats,
    TelemetryModel,
)

type Rate = float | None
type Delta = int | None


class PortCounters(TelemetryModel):
    port_no: PortNumber
    rx_packets: Counter | None
    tx_packets: Counter | None
    rx_bytes: Counter | None
    tx_bytes: Counter | None
    rx_dropped: Counter | None
    tx_dropped: Counter | None
    rx_errors: Counter | None
    tx_errors: Counter | None
    duration_sec: Counter | None


class PortSample(TelemetryModel):
    dpid: DatapathId
    collected_at: AwareDatetime
    stats: PortCounters


class PortKpis(TelemetryModel):
    dpid: DatapathId
    port_no: PortNumber
    computed_at: AwareDatetime
    interval_seconds: float
    rx_bps: Rate
    tx_bps: Rate
    rx_pps: Rate
    tx_pps: Rate
    drop_rate: Rate
    error_rate: Rate
    utilization: Rate
    counter_reset: bool


class NetworkSummary(TelemetryModel):
    ports: Counter
    switches: Counter
    rx_bps: Rate
    tx_bps: Rate
    drop_rate: Rate
    error_rate: Rate
    max_utilization: Rate
    counter_resets: Counter


def port_samples(report: SwitchPortStats) -> tuple[PortSample, ...]:
    return tuple(
        PortSample(
            dpid=report.dpid,
            collected_at=report.collected_at,
            stats=PortCounters(
                port_no=port.port_no,
                rx_packets=port.rx_packets,
                tx_packets=port.tx_packets,
                rx_bytes=port.rx_bytes,
                tx_bytes=port.tx_bytes,
                rx_dropped=port.rx_dropped,
                tx_dropped=port.tx_dropped,
                rx_errors=port.rx_errors,
                tx_errors=port.tx_errors,
                duration_sec=port.duration_sec,
            ),
        )
        for port in report.ports
    )


def compute_port_kpis(
    previous: PortSample, current: PortSample, *, link_capacity_bps: int | None
) -> PortKpis:
    if previous.dpid != current.dpid:
        raise ValueError(f"dpid mismatch: {previous.dpid} != {current.dpid}")
    if previous.stats.port_no != current.stats.port_no:
        raise ValueError(f"port mismatch: {previous.stats.port_no} != {current.stats.port_no}")

    interval = _interval_seconds(previous, current)
    rx_packets = _delta(previous.stats.rx_packets, current.stats.rx_packets)
    tx_packets = _delta(previous.stats.tx_packets, current.stats.tx_packets)
    rx_bytes = _delta(previous.stats.rx_bytes, current.stats.rx_bytes)
    tx_bytes = _delta(previous.stats.tx_bytes, current.stats.tx_bytes)
    rx_dropped = _delta(previous.stats.rx_dropped, current.stats.rx_dropped)
    tx_dropped = _delta(previous.stats.tx_dropped, current.stats.tx_dropped)
    rx_errors = _delta(previous.stats.rx_errors, current.stats.rx_errors)
    tx_errors = _delta(previous.stats.tx_errors, current.stats.tx_errors)
    deltas = (
        rx_packets,
        tx_packets,
        rx_bytes,
        tx_bytes,
        rx_dropped,
        tx_dropped,
        rx_errors,
        tx_errors,
    )

    if interval <= 0 or any(delta is not None and delta < 0 for delta in deltas):
        return PortKpis(
            dpid=current.dpid,
            port_no=current.stats.port_no,
            computed_at=current.collected_at,
            interval_seconds=interval,
            rx_bps=None,
            tx_bps=None,
            rx_pps=None,
            tx_pps=None,
            drop_rate=None,
            error_rate=None,
            utilization=None,
            counter_reset=True,
        )

    rx_bps = _bits_per_second(rx_bytes, interval)
    tx_bps = _bits_per_second(tx_bytes, interval)
    packets = _total_delta(rx_packets, tx_packets)
    return PortKpis(
        dpid=current.dpid,
        port_no=current.stats.port_no,
        computed_at=current.collected_at,
        interval_seconds=interval,
        rx_bps=rx_bps,
        tx_bps=tx_bps,
        rx_pps=_per_second(rx_packets, interval),
        tx_pps=_per_second(tx_packets, interval),
        drop_rate=_ratio(_total_delta(rx_dropped, tx_dropped), packets),
        error_rate=_ratio(_total_delta(rx_errors, tx_errors), packets),
        utilization=_utilization(rx_bps, tx_bps, link_capacity_bps),
        counter_reset=False,
    )


def summarize_kpis(kpis: Sequence[PortKpis]) -> NetworkSummary:
    return NetworkSummary(
        ports=len(kpis),
        switches=len({port.dpid for port in kpis}),
        rx_bps=_total(port.rx_bps for port in kpis),
        tx_bps=_total(port.tx_bps for port in kpis),
        drop_rate=_mean(port.drop_rate for port in kpis),
        error_rate=_mean(port.error_rate for port in kpis),
        max_utilization=_maximum(port.utilization for port in kpis),
        counter_resets=sum(1 for port in kpis if port.counter_reset),
    )


def _interval_seconds(previous: PortSample, current: PortSample) -> float:
    if previous.stats.duration_sec is not None and current.stats.duration_sec is not None:
        return float(current.stats.duration_sec - previous.stats.duration_sec)
    return (current.collected_at - previous.collected_at).total_seconds()


def _delta(previous: int | None, current: int | None) -> Delta:
    if previous is None or current is None:
        return None
    return current - previous


def _total_delta(first: Delta, second: Delta) -> Delta:
    if first is None or second is None:
        return None
    return first + second


def _per_second(delta: Delta, interval: float) -> Rate:
    if delta is None:
        return None
    return delta / interval


def _bits_per_second(byte_delta: Delta, interval: float) -> Rate:
    if byte_delta is None:
        return None
    return byte_delta * 8 / interval


def _ratio(numerator: Delta, denominator: Delta) -> Rate:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _utilization(rx_bps: Rate, tx_bps: Rate, link_capacity_bps: int | None) -> Rate:
    if rx_bps is None or tx_bps is None or not link_capacity_bps:
        return None
    return max(rx_bps, tx_bps) / link_capacity_bps


def _known(values: Iterable[Rate]) -> list[float]:
    return [value for value in values if value is not None]


def _total(values: Iterable[Rate]) -> Rate:
    known = _known(values)
    return sum(known) if known else None


def _mean(values: Iterable[Rate]) -> Rate:
    known = _known(values)
    return sum(known) / len(known) if known else None


def _maximum(values: Iterable[Rate]) -> Rate:
    known = _known(values)
    return max(known) if known else None
