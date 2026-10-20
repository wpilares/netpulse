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
    )


def test_values_are_read_from_environment() -> None:
    config = NetworkConfig.from_env(
        {
            "NETPULSE_NETWORK_CONTROLLER_HOST": "10.0.0.5",
            "NETPULSE_NETWORK_CONTROLLER_PORT": "6633",
            "NETPULSE_NETWORK_TREE_DEPTH": "3",
            "NETPULSE_NETWORK_TREE_FANOUT": "4",
            "NETPULSE_NETWORK_OVS_DATAPATH": "kernel",
        }
    )

    assert config == NetworkConfig(
        controller_host="10.0.0.5",
        controller_port=6633,
        depth=3,
        fanout=4,
        datapath="kernel",
    )


def test_unknown_datapath_is_rejected() -> None:
    with pytest.raises(ValueError, match="datapath"):
        NetworkConfig.from_env({"NETPULSE_NETWORK_OVS_DATAPATH": "dpdk"})


def test_non_numeric_port_is_rejected() -> None:
    with pytest.raises(ValueError, match="CONTROLLER_PORT"):
        NetworkConfig.from_env({"NETPULSE_NETWORK_CONTROLLER_PORT": "openflow"})
