from datetime import UTC, datetime

from netpulse_controller.stats_store import PortCounters, StatsStore

COLLECTED_AT = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _counters(port_no: int) -> PortCounters:
    return PortCounters(
        port_no=port_no,
        rx_packets=10,
        tx_packets=12,
        rx_bytes=1500,
        tx_bytes=1800,
        rx_dropped=0,
        tx_dropped=0,
        rx_errors=0,
        tx_errors=0,
        duration_sec=30,
    )


def test_registered_switches_are_listed_in_order() -> None:
    store = StatsStore()
    store.register(2)
    store.register(1)

    assert store.switches() == (1, 2)


def test_unregistered_switches_disappear_with_their_stats() -> None:
    store = StatsStore()
    store.register(1)
    store.record(1, (_counters(1),), COLLECTED_AT)
    store.unregister(1)

    assert store.switches() == ()
    assert store.port_stats_report() == {"switches": []}


def test_recorded_stats_are_reported_in_collector_format() -> None:
    store = StatsStore()
    store.register(1)
    store.register(2)
    store.record(1, (_counters(2), _counters(1)), COLLECTED_AT)

    report = store.port_stats_report()

    assert report == {
        "switches": [
            {
                "dpid": 1,
                "collected_at": "2026-10-20T12:00:00+00:00",
                "ports": [
                    {**_counters(1).as_dict()},
                    {**_counters(2).as_dict()},
                ],
            }
        ]
    }


def test_stats_from_unknown_switches_are_ignored() -> None:
    store = StatsStore()
    store.record(7, (_counters(1),), COLLECTED_AT)

    assert store.port_stats_report() == {"switches": []}
