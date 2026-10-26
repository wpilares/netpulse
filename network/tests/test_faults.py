import pytest

from netpulse_network.faults import Fault, FaultKind, Schedule, describe_fault, plan_faults
from netpulse_network.topology import Link, build_tree

SPEC = build_tree(depth=2, fanout=2)
HOST_LINKS = {link for link in SPEC.links if link.target in SPEC.hosts}
SWITCH_LINKS = set(SPEC.links) - HOST_LINKS


def _plan(
    *,
    count: int = len(SPEC.links),
    seed: int = 11,
    kinds: tuple[FaultKind, ...] = ("loss", "link_down"),
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


def test_kinds_alternate_strictly() -> None:
    assert [fault.kind for fault in _plan(count=6)] == ["loss", "link_down"] * 3


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


def test_link_down_description_names_the_link() -> None:
    fault = Fault(kind="link_down", link=Link("s1", "s2"), duration_seconds=30, loss_percent=20)

    assert describe_fault(fault) == "link down s1 <-> s2 for 30s"


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
