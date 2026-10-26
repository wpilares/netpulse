from datetime import UTC, datetime

from netpulse_controller.stats_store import (
    HostDescription,
    PortCounters,
    PortDescription,
    StatsStore,
    port_speed_bps,
)

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


def _port(port_no: int, dpid: int = 1) -> PortDescription:
    return PortDescription(
        port_no=port_no, name=f"s{dpid}-eth{port_no}", hw_addr=f"00:00:00:00:0{dpid}:0{port_no}"
    )


def test_recorded_ports_register_the_switch_and_are_sorted() -> None:
    store = StatsStore()
    store.record_ports(1, (_port(2), _port(1)))

    assert store.switches() == (1,)
    assert store.ports(1) == (_port(1), _port(2))


def test_single_port_updates_replace_by_port_number() -> None:
    store = StatsStore()
    store.record_ports(1, (_port(1), _port(2)))
    renamed = PortDescription(port_no=2, name="s1-eth2b", hw_addr=_port(2).hw_addr)
    store.record_port(1, renamed)
    store.record_port(1, _port(3))
    store.remove_port(1, 1)

    assert store.ports(1) == (renamed, _port(3))


def test_links_are_sorted_tuples_and_removable() -> None:
    store = StatsStore()
    store.record_link(2, 1, 1, 2)
    store.record_link(1, 2, 2, 1)
    store.record_link(1, 2, 2, 1)
    store.record_link(1, 3, 3, 1)
    store.remove_link(1, 3, 3, 1)
    store.remove_link(9, 9, 9, 9)

    assert store.links() == ((1, 2, 2, 1), (2, 1, 1, 2))


def test_unregistered_switches_lose_ports_and_links() -> None:
    store = StatsStore()
    store.record_ports(1, (_port(1),))
    store.record_ports(2, (_port(1, dpid=2),))
    store.record_link(1, 2, 2, 1)
    store.record_link(2, 1, 1, 2)
    store.record_link(2, 2, 3, 1)
    store.unregister(1)

    assert store.ports(1) == ()
    assert store.ports(2) == (_port(1, dpid=2),)
    assert store.links() == ((2, 2, 3, 1),)


def test_topology_report_lists_switch_ports_and_directed_links() -> None:
    store = StatsStore()
    store.register(2)
    store.record_ports(1, (_port(2), _port(1)))
    store.record_link(2, 1, 1, 2)
    store.record_link(1, 2, 2, 1)

    assert store.topology_report() == {
        "switches": [
            {
                "dpid": 1,
                "ports": [
                    {
                        "port_no": 1,
                        "name": "s1-eth1",
                        "hw_addr": "00:00:00:00:01:01",
                        "curr_speed_bps": None,
                        "hosts": [],
                    },
                    {
                        "port_no": 2,
                        "name": "s1-eth2",
                        "hw_addr": "00:00:00:00:01:02",
                        "curr_speed_bps": None,
                        "hosts": [],
                    },
                ],
            },
            {"dpid": 2, "ports": []},
        ],
        "links": [
            {"src": {"dpid": 1, "port_no": 2}, "dst": {"dpid": 2, "port_no": 1}},
            {"src": {"dpid": 2, "port_no": 1}, "dst": {"dpid": 1, "port_no": 2}},
        ],
    }


def _host(mac: str, *ipv4: str, dpid: int = 1, port_no: int = 1) -> HostDescription:
    return HostDescription(mac=mac, ipv4=ipv4, dpid=dpid, port_no=port_no)


def test_hosts_are_listed_per_port_sorted_by_mac() -> None:
    store = StatsStore()
    store.record_ports(1, (_port(1), _port(2)))
    store.record_host(_host("00:00:00:00:00:02", "10.0.0.2"))
    store.record_host(_host("00:00:00:00:00:01", "10.0.0.1", "10.0.0.11"))
    store.record_host(_host("00:00:00:00:00:03", port_no=2))

    assert store.hosts(1) == (
        _host("00:00:00:00:00:01", "10.0.0.1", "10.0.0.11"),
        _host("00:00:00:00:00:02", "10.0.0.2"),
        _host("00:00:00:00:00:03", port_no=2),
    )
    assert store.topology_report()["switches"] == [
        {
            "dpid": 1,
            "ports": [
                {
                    "port_no": 1,
                    "name": "s1-eth1",
                    "hw_addr": "00:00:00:00:01:01",
                    "curr_speed_bps": None,
                    "hosts": [
                        {"mac": "00:00:00:00:00:01", "ipv4": ["10.0.0.1", "10.0.0.11"]},
                        {"mac": "00:00:00:00:00:02", "ipv4": ["10.0.0.2"]},
                    ],
                },
                {
                    "port_no": 2,
                    "name": "s1-eth2",
                    "hw_addr": "00:00:00:00:01:02",
                    "curr_speed_bps": None,
                    "hosts": [{"mac": "00:00:00:00:00:03", "ipv4": []}],
                },
            ],
        }
    ]


def test_a_host_lives_on_one_port_and_follows_moves() -> None:
    store = StatsStore()
    store.record_ports(1, (_port(1),))
    store.record_ports(2, (_port(1, dpid=2),))
    store.record_host(_host("00:00:00:00:00:01", "10.0.0.1"))
    store.record_host(_host("00:00:00:00:00:01", "10.0.0.1", dpid=2))

    assert store.hosts(1) == ()
    assert store.hosts(2) == (_host("00:00:00:00:00:01", "10.0.0.1", dpid=2),)


def test_hosts_disappear_with_their_port_switch_or_on_removal() -> None:
    store = StatsStore()
    store.record_ports(1, (_port(1), _port(2)))
    store.record_ports(2, (_port(1, dpid=2),))
    store.record_host(_host("00:00:00:00:00:01", "10.0.0.1"))
    store.record_host(_host("00:00:00:00:00:02", "10.0.0.2", port_no=2))
    store.record_host(_host("00:00:00:00:00:03", "10.0.0.3", dpid=2))
    store.record_host(_host("00:00:00:00:00:04", "10.0.0.4", dpid=2))

    store.remove_port(1, 2)
    store.remove_host("00:00:00:00:00:04")
    store.remove_host("ff:ff:ff:ff:ff:ff")

    assert store.hosts(1) == (_host("00:00:00:00:00:01", "10.0.0.1"),)
    assert store.hosts(2) == (_host("00:00:00:00:00:03", "10.0.0.3", dpid=2),)

    store.unregister(2)

    assert store.hosts(2) == ()


def test_port_speed_converts_kilobits_and_treats_zero_as_unknown() -> None:
    assert port_speed_bps(10_000) == 10_000_000
    assert port_speed_bps(0) is None
    assert port_speed_bps(-1) is None


def test_port_speed_is_reported_per_port() -> None:
    store = StatsStore()
    store.record_port(
        1,
        PortDescription(
            port_no=1, name="s1-eth1", hw_addr="00:00:00:00:01:01", curr_speed_bps=10_000_000
        ),
    )

    assert store.topology_report()["switches"] == [
        {
            "dpid": 1,
            "ports": [
                {
                    "port_no": 1,
                    "name": "s1-eth1",
                    "hw_addr": "00:00:00:00:01:01",
                    "curr_speed_bps": 10_000_000,
                    "hosts": [],
                }
            ],
        }
    ]
