from datetime import UTC, datetime, timedelta

import pytest

from netpulse_core.kpi import (
    NetworkSummary,
    PortCounters,
    PortKpis,
    PortSample,
    compute_port_kpis,
    port_samples,
    summarize_kpis,
)
from netpulse_core.telemetry import PortStats, SwitchPortStats

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
CAPACITY_BPS = 10_000_000


def _sample(
    *,
    dpid: int = 1,
    port_no: int = 1,
    collected_at: datetime = T0,
    **counters: int | None,
) -> PortSample:
    return _build_sample(dpid, port_no, collected_at, counters)


def _next_sample(**counters: int | None) -> PortSample:
    defaults: dict[str, int | None] = {
        "rx_packets": 30,
        "tx_packets": 15,
        "rx_bytes": 9_000,
        "tx_bytes": 4_500,
        "rx_dropped": 1,
        "tx_dropped": 2,
        "rx_errors": 6,
        "tx_errors": 3,
        "duration_sec": 20,
    }
    defaults.update(counters)
    return _build_sample(1, 1, T0 + timedelta(seconds=12), defaults)


def _build_sample(
    dpid: int, port_no: int, collected_at: datetime, counters: dict[str, int | None]
) -> PortSample:
    payload: dict[str, int | None] = {
        "port_no": port_no,
        "rx_packets": 10,
        "tx_packets": 5,
        "rx_bytes": 1_000,
        "tx_bytes": 500,
        "rx_dropped": 0,
        "tx_dropped": 0,
        "rx_errors": 0,
        "tx_errors": 0,
        "duration_sec": 10,
    }
    payload.update(counters)
    return PortSample(
        dpid=dpid, collected_at=collected_at, stats=PortCounters.model_validate(payload)
    )


def _kpis(
    *,
    dpid: int = 1,
    port_no: int = 1,
    rx_bps: float | None = None,
    tx_bps: float | None = None,
    drop_rate: float | None = None,
    error_rate: float | None = None,
    utilization: float | None = None,
    counter_reset: bool = False,
) -> PortKpis:
    return PortKpis(
        dpid=dpid,
        port_no=port_no,
        computed_at=T0,
        interval_seconds=10.0,
        rx_bps=rx_bps,
        tx_bps=tx_bps,
        rx_pps=None,
        tx_pps=None,
        drop_rate=drop_rate,
        error_rate=error_rate,
        utilization=utilization,
        counter_reset=counter_reset,
    )


def test_normal_deltas_yield_rates_over_duration_interval() -> None:
    current = _next_sample()

    kpis = compute_port_kpis(_sample(), current, link_capacity_bps=CAPACITY_BPS)

    assert kpis.dpid == 1
    assert kpis.port_no == 1
    assert kpis.computed_at == current.collected_at
    assert kpis.interval_seconds == 10.0
    assert kpis.rx_bps == 6_400.0
    assert kpis.tx_bps == 3_200.0
    assert kpis.rx_pps == 2.0
    assert kpis.tx_pps == 1.0
    assert kpis.drop_rate == pytest.approx(0.1)
    assert kpis.error_rate == pytest.approx(0.3)
    assert kpis.utilization == pytest.approx(6_400 / CAPACITY_BPS)
    assert kpis.counter_reset is False


def test_interval_falls_back_to_timestamps_without_duration() -> None:
    previous = _sample(duration_sec=None)
    current = _next_sample(duration_sec=None)

    kpis = compute_port_kpis(previous, current, link_capacity_bps=None)

    assert kpis.interval_seconds == 12.0
    assert kpis.rx_bps == pytest.approx(8_000 * 8 / 12)
    assert kpis.counter_reset is False


def test_interval_prefers_duration_over_timestamps() -> None:
    kpis = compute_port_kpis(_sample(), _next_sample(), link_capacity_bps=None)

    assert kpis.interval_seconds == 10.0


def test_duration_decrease_marks_counter_reset() -> None:
    kpis = compute_port_kpis(
        _sample(), _next_sample(duration_sec=3), link_capacity_bps=CAPACITY_BPS
    )

    assert kpis.counter_reset is True
    assert kpis.interval_seconds == -7.0
    assert _all_rates(kpis) == [None] * 7


def test_counter_decrease_marks_counter_reset() -> None:
    kpis = compute_port_kpis(_sample(), _next_sample(rx_bytes=100), link_capacity_bps=CAPACITY_BPS)

    assert kpis.counter_reset is True
    assert kpis.interval_seconds == 10.0
    assert _all_rates(kpis) == [None] * 7


def test_zero_interval_marks_counter_reset() -> None:
    kpis = compute_port_kpis(_sample(), _next_sample(duration_sec=10), link_capacity_bps=None)

    assert kpis.counter_reset is True
    assert _all_rates(kpis) == [None] * 7


def test_unknown_counters_only_blank_dependent_rates() -> None:
    current = _next_sample(rx_bytes=None, rx_dropped=None)

    kpis = compute_port_kpis(_sample(), current, link_capacity_bps=CAPACITY_BPS)

    assert kpis.rx_bps is None
    assert kpis.utilization is None
    assert kpis.drop_rate is None
    assert kpis.tx_bps == 3_200.0
    assert kpis.rx_pps == 2.0
    assert kpis.tx_pps == 1.0
    assert kpis.error_rate == pytest.approx(0.3)
    assert kpis.counter_reset is False


def test_unknown_previous_counter_blanks_rate() -> None:
    kpis = compute_port_kpis(
        _sample(tx_packets=None), _next_sample(), link_capacity_bps=CAPACITY_BPS
    )

    assert kpis.tx_pps is None
    assert kpis.drop_rate is None
    assert kpis.error_rate is None
    assert kpis.rx_pps == 2.0


def test_zero_packet_delta_leaves_ratios_unknown() -> None:
    current = _next_sample(rx_packets=10, tx_packets=5, rx_dropped=0, tx_dropped=0)

    kpis = compute_port_kpis(_sample(), current, link_capacity_bps=CAPACITY_BPS)

    assert kpis.rx_pps == 0.0
    assert kpis.tx_pps == 0.0
    assert kpis.drop_rate is None
    assert kpis.error_rate is None
    assert kpis.rx_bps == 6_400.0


def test_utilization_uses_busiest_direction() -> None:
    current = _next_sample(tx_bytes=20_500)

    kpis = compute_port_kpis(_sample(), current, link_capacity_bps=CAPACITY_BPS)

    assert kpis.tx_bps == 16_000.0
    assert kpis.utilization == pytest.approx(16_000 / CAPACITY_BPS)


def test_utilization_is_not_clamped() -> None:
    kpis = compute_port_kpis(_sample(), _next_sample(), link_capacity_bps=1_000)

    assert kpis.utilization == pytest.approx(6.4)


@pytest.mark.parametrize("capacity", [None, 0])
def test_utilization_without_capacity_is_unknown(capacity: int | None) -> None:
    kpis = compute_port_kpis(_sample(), _next_sample(), link_capacity_bps=capacity)

    assert kpis.rx_bps == 6_400.0
    assert kpis.utilization is None


def test_mismatched_port_raises() -> None:
    with pytest.raises(ValueError, match="port"):
        compute_port_kpis(_sample(), _sample(port_no=2), link_capacity_bps=None)


def test_mismatched_switch_raises() -> None:
    with pytest.raises(ValueError, match="dpid"):
        compute_port_kpis(_sample(), _sample(dpid=2), link_capacity_bps=None)


def test_port_samples_are_built_from_switch_port_stats() -> None:
    port = PortStats(
        port_no=3,
        rx_packets=1,
        tx_packets=2,
        rx_bytes=3,
        tx_bytes=4,
        rx_dropped=5,
        tx_dropped=6,
        rx_errors=7,
        tx_errors=8,
        duration_sec=9,
    )
    report = SwitchPortStats(
        dpid=7, collected_at=T0, ports=(port, port.model_copy(update={"port_no": 4}))
    )

    samples = port_samples(report)

    assert [sample.stats.port_no for sample in samples] == [3, 4]
    assert all(sample.dpid == 7 and sample.collected_at == T0 for sample in samples)
    assert samples[0].stats == PortCounters.model_validate(port.model_dump())


def test_summary_aggregates_known_values_only() -> None:
    kpis = [
        _kpis(rx_bps=100.0, tx_bps=50.0, drop_rate=0.1, error_rate=0.2, utilization=0.5),
        _kpis(dpid=2, port_no=2, tx_bps=25.0, error_rate=0.4, counter_reset=True),
        _kpis(dpid=2, port_no=3, rx_bps=20.0, drop_rate=0.3, utilization=0.9),
    ]

    summary = summarize_kpis(kpis)

    assert summary.ports == 3
    assert summary.switches == 2
    assert summary.rx_bps == 120.0
    assert summary.tx_bps == 75.0
    assert summary.drop_rate == pytest.approx(0.2)
    assert summary.error_rate == pytest.approx(0.3)
    assert summary.max_utilization == 0.9
    assert summary.counter_resets == 1


def test_summary_of_nothing_is_unknown() -> None:
    assert summarize_kpis([]) == NetworkSummary(
        ports=0,
        switches=0,
        rx_bps=None,
        tx_bps=None,
        drop_rate=None,
        error_rate=None,
        max_utilization=None,
        counter_resets=0,
    )


def _all_rates(kpis: PortKpis) -> list[float | None]:
    return [
        kpis.rx_bps,
        kpis.tx_bps,
        kpis.rx_pps,
        kpis.tx_pps,
        kpis.drop_rate,
        kpis.error_rate,
        kpis.utilization,
    ]
