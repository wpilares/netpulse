import pytest

from netpulse_network.config import NetworkConfig


def test_defaults_target_the_compose_controller() -> None:
    config = NetworkConfig.from_env({})

    assert config == NetworkConfig(
        controller_host="controller",
        controller_port=6653,
        depth=2,
        fanout=2,
        datapath="user",
        link_bandwidth_mbps=10,
        traffic_enabled=True,
        traffic_round_seconds=15,
        traffic_duration_seconds=10,
        traffic_min_mbps=1,
        traffic_max_mbps=8,
        traffic_seed=7,
    )


def test_values_are_read_from_environment() -> None:
    config = NetworkConfig.from_env(
        {
            "NETPULSE_NETWORK_CONTROLLER_HOST": "10.0.0.5",
            "NETPULSE_NETWORK_CONTROLLER_PORT": "6633",
            "NETPULSE_NETWORK_TREE_DEPTH": "3",
            "NETPULSE_NETWORK_TREE_FANOUT": "4",
            "NETPULSE_NETWORK_OVS_DATAPATH": "kernel",
            "NETPULSE_NETWORK_LINK_BANDWIDTH_MBPS": "100",
            "NETPULSE_NETWORK_TRAFFIC_ENABLED": "false",
            "NETPULSE_NETWORK_TRAFFIC_ROUND_SECONDS": "30",
            "NETPULSE_NETWORK_TRAFFIC_DURATION_SECONDS": "20",
            "NETPULSE_NETWORK_TRAFFIC_MIN_MBPS": "5",
            "NETPULSE_NETWORK_TRAFFIC_MAX_MBPS": "50",
            "NETPULSE_NETWORK_TRAFFIC_SEED": "42",
        }
    )

    assert config == NetworkConfig(
        controller_host="10.0.0.5",
        controller_port=6633,
        depth=3,
        fanout=4,
        datapath="kernel",
        link_bandwidth_mbps=100,
        traffic_enabled=False,
        traffic_round_seconds=30,
        traffic_duration_seconds=20,
        traffic_min_mbps=5,
        traffic_max_mbps=50,
        traffic_seed=42,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), ("True", True), ("1", True), ("yes", True), ("false", False), ("0", False)],
)
def test_traffic_enabled_accepts_common_boolean_spellings(raw: str, expected: bool) -> None:
    config = NetworkConfig.from_env({"NETPULSE_NETWORK_TRAFFIC_ENABLED": raw})

    assert config.traffic_enabled is expected


def test_unknown_boolean_is_rejected() -> None:
    with pytest.raises(ValueError, match="TRAFFIC_ENABLED"):
        NetworkConfig.from_env({"NETPULSE_NETWORK_TRAFFIC_ENABLED": "maybe"})


def test_unknown_datapath_is_rejected() -> None:
    with pytest.raises(ValueError, match="datapath"):
        NetworkConfig.from_env({"NETPULSE_NETWORK_OVS_DATAPATH": "dpdk"})


def test_non_numeric_port_is_rejected() -> None:
    with pytest.raises(ValueError, match="CONTROLLER_PORT"):
        NetworkConfig.from_env({"NETPULSE_NETWORK_CONTROLLER_PORT": "openflow"})


@pytest.mark.parametrize(
    ("name", "value", "match"),
    [
        ("LINK_BANDWIDTH_MBPS", "0", "link_bandwidth_mbps"),
        ("TRAFFIC_ROUND_SECONDS", "0", "traffic_round_seconds"),
        ("TRAFFIC_DURATION_SECONDS", "-1", "traffic_duration_seconds"),
        ("TRAFFIC_MIN_MBPS", "0", "traffic_min_mbps"),
        ("TRAFFIC_MAX_MBPS", "0", "traffic_max_mbps"),
        ("TRAFFIC_MIN_MBPS", "9", "traffic_min_mbps"),
        ("TRAFFIC_MAX_MBPS", "11", "traffic_max_mbps"),
        ("TRAFFIC_DURATION_SECONDS", "16", "traffic_duration_seconds"),
    ],
)
def test_traffic_bounds_are_validated(name: str, value: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        NetworkConfig.from_env({f"NETPULSE_NETWORK_{name}": value})
