import pytest

from netpulse_network.topology import Link, build_tree


def test_single_level_tree_has_one_switch_with_all_hosts() -> None:
    spec = build_tree(depth=1, fanout=3)

    assert spec.switches == ("s1",)
    assert spec.hosts == ("h1", "h2", "h3")
    assert spec.links == (Link("s1", "h1"), Link("s1", "h2"), Link("s1", "h3"))


def test_two_level_tree_connects_core_to_edge_switches() -> None:
    spec = build_tree(depth=2, fanout=2)

    assert spec.switches == ("s1", "s2", "s3")
    assert spec.hosts == ("h1", "h2", "h3", "h4")
    assert spec.links == (
        Link("s1", "s2"),
        Link("s2", "h1"),
        Link("s2", "h2"),
        Link("s1", "s3"),
        Link("s3", "h3"),
        Link("s3", "h4"),
    )


@pytest.mark.parametrize(("depth", "fanout"), [(2, 3), (3, 2), (3, 3)])
def test_tree_sizes_follow_depth_and_fanout(depth: int, fanout: int) -> None:
    spec = build_tree(depth=depth, fanout=fanout)

    expected_switches = sum(fanout**level for level in range(depth))
    assert len(spec.switches) == expected_switches
    assert len(spec.hosts) == fanout**depth
    assert len(spec.links) == len(spec.switches) + len(spec.hosts) - 1


@pytest.mark.parametrize(("depth", "fanout"), [(0, 2), (2, 0), (-1, 2)])
def test_tree_rejects_non_positive_dimensions(depth: int, fanout: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        build_tree(depth=depth, fanout=fanout)


def test_datapath_ids_are_derived_from_switch_names() -> None:
    spec = build_tree(depth=2, fanout=2)

    assert [spec.datapath_id(switch) for switch in spec.switches] == [
        "0000000000000001",
        "0000000000000002",
        "0000000000000003",
    ]
