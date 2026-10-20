import pytest

from netpulse_controller.settings import ControllerSettings


def test_defaults_listen_on_standard_ports() -> None:
    assert ControllerSettings.from_env({}) == ControllerSettings(
        openflow_port=6653,
        rest_host="127.0.0.1",
        rest_port=8080,
        stats_interval_seconds=5.0,
    )


def test_values_are_read_from_environment() -> None:
    settings = ControllerSettings.from_env(
        {
            "NETPULSE_CONTROLLER_OPENFLOW_PORT": "6633",
            "NETPULSE_CONTROLLER_REST_HOST": "10.0.0.2",
            "NETPULSE_CONTROLLER_REST_PORT": "9090",
            "NETPULSE_CONTROLLER_STATS_INTERVAL_SECONDS": "1.5",
        }
    )

    assert settings == ControllerSettings(
        openflow_port=6633,
        rest_host="10.0.0.2",
        rest_port=9090,
        stats_interval_seconds=1.5,
    )


@pytest.mark.parametrize("interval", ["0", "-2", "soon"])
def test_stats_interval_must_be_a_positive_number(interval: str) -> None:
    with pytest.raises(ValueError, match="STATS_INTERVAL_SECONDS"):
        ControllerSettings.from_env({"NETPULSE_CONTROLLER_STATS_INTERVAL_SECONDS": interval})
