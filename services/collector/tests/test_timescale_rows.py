from datetime import UTC, datetime

from netpulse_collector.timescale_repository import port_stats_rows
from netpulse_core import PortStats, PortStatsReport, SwitchPortStats

COLLECTED_AT = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
UNSUPPORTED_COUNTER = 2**64 - 1


def _port(port_no: int, **overrides: int) -> PortStats:
    counters = {
        "rx_packets": 10,
        "tx_packets": 12,
        "rx_bytes": 1_500,
        "tx_bytes": 1_800,
        "rx_dropped": 1,
        "tx_dropped": 2,
        "rx_errors": 3,
        "tx_errors": 4,
        "duration_sec": 30,
    }
    counters.update(overrides)
    return PortStats(port_no=port_no, **counters)


def test_rows_flatten_every_port_of_every_switch_in_column_order() -> None:
    report = PortStatsReport(
        switches=(
            SwitchPortStats(dpid=1, collected_at=COLLECTED_AT, ports=(_port(1), _port(2))),
            SwitchPortStats(dpid=2, collected_at=COLLECTED_AT, ports=(_port(1),)),
        )
    )

    rows = port_stats_rows(report)

    assert [(row[1], row[2]) for row in rows] == [(1, 1), (1, 2), (2, 1)]
    assert rows[0] == (COLLECTED_AT, 1, 1, 10, 12, 1_500, 1_800, 1, 2, 3, 4, 30)


def test_rows_are_empty_for_a_report_without_switches() -> None:
    assert port_stats_rows(PortStatsReport(switches=())) == []


def test_counters_beyond_signed_64_bits_are_stored_as_unknown() -> None:
    report = PortStatsReport(
        switches=(
            SwitchPortStats(
                dpid=2**64 - 1,
                collected_at=COLLECTED_AT,
                ports=(_port(4_294_967_294, rx_errors=UNSUPPORTED_COUNTER),),
            ),
        )
    )

    (row,) = port_stats_rows(report)

    assert row[1] == 2**64 - 1
    assert row[2] == 4_294_967_294
    assert row[9] is None
    assert row[10] == 4
