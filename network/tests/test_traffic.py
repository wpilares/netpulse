from collections import Counter

import pytest

from netpulse_network.traffic import (
    TrafficFlow,
    TrafficRound,
    iperf_client_command,
    iperf_server_command,
    plan_rounds,
    tournament_rounds,
)

HOSTS = ("h1", "h2", "h3", "h4")


def _plan(
    hosts: tuple[str, ...] = HOSTS, *, rounds: int = 3, seed: int = 7
) -> tuple[TrafficRound, ...]:
    return plan_rounds(
        hosts,
        rounds=rounds,
        min_mbps=1,
        max_mbps=8,
        duration_seconds=10,
        seed=seed,
    )


def test_plan_is_deterministic_for_a_seed() -> None:
    assert _plan(seed=7) == _plan(seed=7)
    assert _plan(seed=7) != _plan(seed=8)


def test_plan_returns_the_requested_number_of_rounds() -> None:
    assert len(_plan(rounds=5)) == 5


def test_every_host_appears_at_most_once_per_round() -> None:
    for traffic_round in _plan(rounds=6):
        participants = [host for flow in traffic_round.flows for host in (flow.client, flow.server)]
        assert len(participants) == len(set(participants))
        assert all(flow.client != flow.server for flow in traffic_round.flows)


def test_even_host_count_keeps_every_host_busy_each_round() -> None:
    for traffic_round in _plan(rounds=6):
        participants = {host for flow in traffic_round.flows for host in (flow.client, flow.server)}
        assert participants == set(HOSTS)


def test_every_pair_of_hosts_talks_over_a_full_tournament() -> None:
    rounds = _plan(rounds=tournament_rounds(len(HOSTS)))

    pairs = {frozenset((flow.client, flow.server)) for r in rounds for flow in r.flows}

    expected = {frozenset((a, b)) for a in HOSTS for b in HOSTS if a < b}
    assert pairs == expected


def test_every_host_is_a_client_and_a_server_over_time() -> None:
    rounds = _plan(rounds=tournament_rounds(len(HOSTS)) * 2)

    clients = Counter(flow.client for r in rounds for flow in r.flows)
    servers = Counter(flow.server for r in rounds for flow in r.flows)

    assert set(clients) == set(HOSTS)
    assert set(servers) == set(HOSTS)


def test_odd_host_count_rests_one_host_per_round() -> None:
    hosts = ("h1", "h2", "h3")
    rounds = _plan(hosts, rounds=tournament_rounds(len(hosts)))

    resting = [set(hosts) - {h for f in r.flows for h in (f.client, f.server)} for r in rounds]

    assert all(len(rest) == 1 for rest in resting)
    assert set().union(*resting) == set(hosts)


def test_fewer_than_two_hosts_produces_idle_rounds() -> None:
    assert _plan(("h1",), rounds=2) == (TrafficRound(flows=()), TrafficRound(flows=()))


def test_bandwidth_stays_within_bounds_and_moves() -> None:
    rounds = plan_rounds(HOSTS, rounds=20, min_mbps=2, max_mbps=6, duration_seconds=10, seed=7)

    bandwidths = [flow.bandwidth_mbps for r in rounds for flow in r.flows]

    assert all(2 <= bandwidth <= 6 for bandwidth in bandwidths)
    assert len(set(bandwidths)) > 1


def test_flows_carry_the_configured_duration() -> None:
    assert all(flow.duration_seconds == 10 for r in _plan() for flow in r.flows)


@pytest.mark.parametrize(
    ("host_count", "expected"), [(0, 0), (1, 0), (2, 1), (3, 3), (4, 3), (5, 5)]
)
def test_tournament_length_covers_every_pair(host_count: int, expected: int) -> None:
    assert tournament_rounds(host_count) == expected


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"rounds": 0}, "rounds"),
        ({"min_mbps": 0}, "min_mbps"),
        ({"min_mbps": 9}, "max_mbps"),
        ({"duration_seconds": 0}, "duration"),
    ],
)
def test_invalid_plan_arguments_are_rejected(kwargs: dict[str, int], match: str) -> None:
    arguments = {"rounds": 3, "min_mbps": 1, "max_mbps": 8, "duration_seconds": 10, "seed": 7}
    arguments.update(kwargs)

    with pytest.raises(ValueError, match=match):
        plan_rounds(HOSTS, **arguments)


def test_server_command_runs_iperf3_as_a_daemon() -> None:
    assert iperf_server_command() == ("iperf3", "-s", "-D")


def test_client_command_sends_udp_at_the_flow_rate() -> None:
    flow = TrafficFlow(client="h1", server="h2", duration_seconds=10, bandwidth_mbps=5)

    assert iperf_client_command("10.0.0.2", flow) == (
        "iperf3",
        "-c",
        "10.0.0.2",
        "-u",
        "-b",
        "5M",
        "-t",
        "10",
    )
