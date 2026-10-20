from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from netpulse_core.telemetry import PortStats, PortStatsReport


def _port_payload(**overrides: int) -> dict[str, int]:
    payload = {
        "port_no": 1,
        "rx_packets": 10,
        "tx_packets": 12,
        "rx_bytes": 1_500,
        "tx_bytes": 1_800,
        "rx_dropped": 0,
        "tx_dropped": 0,
        "rx_errors": 0,
        "tx_errors": 0,
        "duration_sec": 30,
    }
    payload.update(overrides)
    return payload


def test_report_parses_controller_payload() -> None:
    payload = {
        "switches": [
            {
                "dpid": 1,
                "collected_at": "2026-10-20T12:00:00Z",
                "ports": [_port_payload(), _port_payload(port_no=2)],
            }
        ]
    }

    report = PortStatsReport.model_validate(payload)

    switch = report.switches[0]
    assert switch.dpid == 1
    assert switch.collected_at == datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    assert [port.port_no for port in switch.ports] == [1, 2]


def test_report_with_no_switches_is_empty() -> None:
    assert PortStatsReport.model_validate({"switches": []}).switches == ()


@pytest.mark.parametrize("field", ["rx_packets", "tx_bytes", "rx_errors"])
def test_port_stats_rejects_negative_counters(field: str) -> None:
    with pytest.raises(ValidationError):
        PortStats.model_validate(_port_payload(**{field: -1}))


def test_port_stats_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PortStats.model_validate({**_port_payload(), "unexpected": 1})


def test_switch_stats_rejects_naive_timestamps() -> None:
    payload = {"dpid": 1, "collected_at": "2026-10-20T12:00:00", "ports": []}

    with pytest.raises(ValidationError):
        PortStatsReport.model_validate({"switches": [payload]})


def test_switch_stats_rejects_datapath_ids_beyond_64_bits() -> None:
    payload = {"dpid": 2**64, "collected_at": "2026-10-20T12:00:00Z", "ports": []}

    with pytest.raises(ValidationError):
        PortStatsReport.model_validate({"switches": [payload]})


@pytest.mark.parametrize("field", ["port_no", "rx_packets"])
def test_port_stats_are_immutable(field: str) -> None:
    stats = PortStats.model_validate(_port_payload())

    with pytest.raises(ValidationError):
        setattr(stats, field, 99)
