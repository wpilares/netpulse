import pytest

from netpulse_network.faults import (
    Fault,
    FaultKind,
    Schedule,
    choose_probe_host,
    describe_fault,
    plan_faults,
    probe_cleanup_commands,
    probe_commands,
)
from netpulse_network.topology import Link, TopologySpec, build_tree

SPEC = build_tree(depth=2, fanout=2)
HOST_LINKS = {link for link in SPEC.links if link.target in SPEC.hosts}
SWITCH_LINKS = set(SPEC.links) - HOST_LINKS


def _plan(
    *,
    count: int = len(SPEC.links),
    seed: int = 11,
    kinds: tuple[FaultKind, ...] = ("loss", "host_down"),
    loss_percent: int = 20,
    duration_seconds: int = 30,
) -> tuple[Fault, ...]:
    return plan_faults(
        SPEC.links,
        hosts=SPEC.hosts,
        count=count,
        kinds=kinds,
        duration_seconds=duration_seconds,
        loss_percent=loss_percent,
        seed=seed,
    )


def test_plan_is_deterministic_for_a_seed() -> None:
    assert _plan(seed=11) == _plan(seed=11)
    assert _plan(seed=11) != _plan(seed=12)


def test_plan_returns_the_requested_number_of_faults() -> None:
    assert len(_plan(count=9)) == 9


def test_kinds_alternate_on_host_links_and_switch_links_only_lose_packets() -> None:
    faults = _plan()

    host_faults = faults[: len(HOST_LINKS)]
    switch_faults = faults[len(HOST_LINKS) :]

    assert [fault.kind for fault in host_faults] == ["loss", "host_down"] * (len(HOST_LINKS) // 2)
    assert {fault.kind for fault in switch_faults} == {"loss"}


@pytest.mark.parametrize("seed", [1, 11, 42])
def test_host_down_is_only_scheduled_on_host_links(seed: int) -> None:
    for fault in _plan(count=len(SPEC.links) * 3, seed=seed):
        if fault.kind == "host_down":
            assert fault.link in HOST_LINKS
            assert fault.host in SPEC.hosts
            assert fault.host in (fault.link.source, fault.link.target)
        else:
            assert fault.host is None


def test_host_down_alone_cycles_only_host_links() -> None:
    faults = _plan(count=len(HOST_LINKS) * 2, kinds=("host_down",))

    assert {fault.kind for fault in faults} == {"host_down"}
    assert {fault.link for fault in faults} == HOST_LINKS
    assert len(faults) == len(HOST_LINKS) * 2


def test_host_down_without_host_links_is_rejected() -> None:
    with pytest.raises(ValueError, match="host"):
        plan_faults(
            sorted(SWITCH_LINKS, key=str),
            hosts=SPEC.hosts,
            count=1,
            kinds=("host_down",),
            duration_seconds=30,
            loss_percent=20,
            seed=11,
        )


def test_host_links_are_hit_before_switch_links() -> None:
    faults = _plan()

    assert {fault.link for fault in faults[: len(HOST_LINKS)]} == HOST_LINKS
    assert {fault.link for fault in faults[len(HOST_LINKS) :]} == SWITCH_LINKS


def test_every_link_is_hit_once_per_cycle() -> None:
    faults = _plan(count=len(SPEC.links) * 2)

    first_cycle = [fault.link for fault in faults[: len(SPEC.links)]]
    second_cycle = [fault.link for fault in faults[len(SPEC.links) :]]

    assert sorted(first_cycle, key=str) == sorted(SPEC.links, key=str)
    assert sorted(second_cycle, key=str) == sorted(SPEC.links, key=str)


def test_a_single_kind_is_repeated() -> None:
    assert {fault.kind for fault in _plan(kinds=("loss",))} == {"loss"}


def test_faults_carry_duration_and_loss() -> None:
    for fault in _plan(loss_percent=35, duration_seconds=12):
        assert fault.loss_percent == 35
        assert fault.duration_seconds == 12


def test_non_positive_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="count"):
        _plan(count=0)


@pytest.mark.parametrize("loss_percent", [0, 101])
def test_loss_outside_one_to_one_hundred_percent_is_rejected(loss_percent: int) -> None:
    with pytest.raises(ValueError, match="loss_percent"):
        _plan(loss_percent=loss_percent)


def test_non_positive_duration_is_rejected() -> None:
    with pytest.raises(ValueError, match="duration_seconds"):
        _plan(duration_seconds=0)


def test_empty_kinds_are_rejected() -> None:
    with pytest.raises(ValueError, match="kinds"):
        _plan(kinds=())


def test_plan_without_links_is_rejected() -> None:
    with pytest.raises(ValueError, match="links"):
        plan_faults((), hosts=SPEC.hosts, count=1, duration_seconds=30, loss_percent=20, seed=11)


def test_loss_fault_description_names_the_link_and_rate() -> None:
    fault = Fault(kind="loss", link=Link("s2", "h1"), duration_seconds=30, loss_percent=20)

    assert describe_fault(fault) == "loss 20% on s2 <-> h1 for 30s"


def test_host_down_description_names_the_host_and_its_switch() -> None:
    fault = Fault(
        kind="host_down", link=Link("s3", "h3"), duration_seconds=30, loss_percent=20, host="h3"
    )

    assert describe_fault(fault) == "host down h3 behind s3 for 30s"


def test_host_down_fault_requires_its_host() -> None:
    with pytest.raises(ValueError, match="host"):
        Fault(kind="host_down", link=Link("s3", "h3"), duration_seconds=30, loss_percent=20)


def test_loss_fault_carries_no_host() -> None:
    with pytest.raises(ValueError, match="host"):
        Fault(kind="loss", link=Link("s3", "h3"), duration_seconds=30, loss_percent=20, host="h3")


def _host_down(host: str, switch: str) -> Fault:
    return Fault(
        kind="host_down", link=Link(switch, host), duration_seconds=30, loss_percent=20, host=host
    )


def test_probe_host_is_a_sibling_behind_the_same_switch() -> None:
    assert choose_probe_host(_host_down("h1", "s2"), SPEC) == "h2"
    assert choose_probe_host(_host_down("h2", "s2"), SPEC) == "h1"


def test_probe_host_falls_back_to_any_other_host() -> None:
    spec = TopologySpec(
        switches=("s1", "s2"),
        hosts=("h1", "h2"),
        links=(Link("s1", "s2"), Link("s1", "h1"), Link("s2", "h2")),
    )

    assert choose_probe_host(_host_down("h1", "s1"), spec) == "h2"


def test_probe_host_needs_another_host() -> None:
    spec = TopologySpec(switches=("s1",), hosts=("h1",), links=(Link("s1", "h1"),))

    with pytest.raises(ValueError, match="host"):
        choose_probe_host(_host_down("h1", "s1"), spec)


def test_probe_pins_the_neighbour_then_floods_it_for_the_fault_duration() -> None:
    commands = probe_commands(
        target_ip="10.0.0.4",
        target_mac="00:00:00:00:00:04",
        interface="h1-eth0",
        duration_seconds=30,
    )

    assert commands == (
        (
            "ip",
            "neigh",
            "replace",
            "10.0.0.4",
            "lladdr",
            "00:00:00:00:00:04",
            "dev",
            "h1-eth0",
            "nud",
            "permanent",
        ),
        ("ping", "-f", "-q", "-w", "30", "-s", "1000", "10.0.0.4"),
    )


def test_probe_cleanup_forgets_the_pinned_neighbour() -> None:
    assert probe_cleanup_commands(target_ip="10.0.0.4", interface="h1-eth0") == (
        "ip",
        "neigh",
        "del",
        "10.0.0.4",
        "dev",
        "h1-eth0",
    )


def test_schedule_starts_with_immediate_traffic_and_a_delayed_fault() -> None:
    schedule = Schedule.start(100.0, traffic=True, first_fault_in=90)

    assert schedule == Schedule(traffic_at=100.0, fault_at=190.0, fault_until=None)
    assert schedule.next_event() == ("traffic", 100.0)


def test_schedule_without_traffic_or_faults_has_no_events() -> None:
    assert Schedule.start(0.0, traffic=False, first_fault_in=None).next_event() is None


def test_schedule_with_only_faults_waits_for_the_first_fault() -> None:
    assert Schedule.start(0.0, traffic=False, first_fault_in=90).next_event() == (
        "fault_start",
        90.0,
    )


def test_traffic_launch_reschedules_the_next_round() -> None:
    schedule = Schedule.start(0.0, traffic=True, first_fault_in=None).traffic_launched(0.0, 15)

    assert schedule == Schedule(traffic_at=15.0, fault_at=None, fault_until=None)


def test_earliest_event_wins() -> None:
    assert Schedule(traffic_at=95.0, fault_at=90.0).next_event() == ("fault_start", 90.0)
    assert Schedule(traffic_at=125.0, fault_until=120.0).next_event() == ("fault_end", 120.0)
    assert Schedule(traffic_at=90.0, fault_until=120.0).next_event() == ("traffic", 90.0)


def test_traffic_wins_ties() -> None:
    assert Schedule(traffic_at=90.0, fault_at=90.0).next_event() == ("traffic", 90.0)
    assert Schedule(traffic_at=120.0, fault_until=120.0).next_event() == ("traffic", 120.0)


def test_applying_a_fault_schedules_its_end_and_suspends_new_faults() -> None:
    schedule = Schedule(traffic_at=95.0, fault_at=90.0).fault_applied(90.0, 30)

    assert schedule == Schedule(traffic_at=95.0, fault_at=None, fault_until=120.0)


def test_clearing_a_fault_schedules_the_next_one_after_the_period() -> None:
    schedule = Schedule(traffic_at=125.0, fault_until=120.0).fault_cleared(120.0, 90)

    assert schedule == Schedule(traffic_at=125.0, fault_at=210.0, fault_until=None)
