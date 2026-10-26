from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Self

Datapath = Literal["kernel", "user"]

PREFIX = "NETPULSE_NETWORK_"


def _integer(environ: Mapping[str, str], name: str, default: int) -> int:
    raw = environ.get(PREFIX + name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{PREFIX}{name} must be an integer, got {raw!r}") from error


_BOOLEANS: dict[str, bool] = {
    "true": True,
    "1": True,
    "yes": True,
    "on": True,
    "false": False,
    "0": False,
    "no": False,
    "off": False,
}


def _boolean(environ: Mapping[str, str], name: str, default: bool) -> bool:
    raw = environ.get(PREFIX + name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized not in _BOOLEANS:
        raise ValueError(f"{PREFIX}{name} must be a boolean, got {raw!r}")
    return _BOOLEANS[normalized]


_DATAPATHS: dict[str, Datapath] = {"kernel": "kernel", "user": "user"}


def _datapath(raw: str) -> Datapath:
    if raw not in _DATAPATHS:
        raise ValueError(f"unsupported OVS datapath {raw!r}, expected one of {sorted(_DATAPATHS)}")
    return _DATAPATHS[raw]


def _require_positive(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be positive, got {value}")


@dataclass(frozen=True, slots=True)
class NetworkConfig:
    controller_host: str
    controller_port: int
    depth: int
    fanout: int
    datapath: Datapath
    link_bandwidth_mbps: int = 10
    traffic_enabled: bool = True
    traffic_round_seconds: int = 15
    traffic_duration_seconds: int = 10
    traffic_min_mbps: int = 1
    traffic_max_mbps: int = 8
    traffic_seed: int = 7

    def __post_init__(self) -> None:
        _require_positive("link_bandwidth_mbps", self.link_bandwidth_mbps)
        _require_positive("traffic_round_seconds", self.traffic_round_seconds)
        _require_positive("traffic_duration_seconds", self.traffic_duration_seconds)
        _require_positive("traffic_min_mbps", self.traffic_min_mbps)
        _require_positive("traffic_max_mbps", self.traffic_max_mbps)
        if self.traffic_min_mbps > self.traffic_max_mbps:
            raise ValueError(
                f"traffic_min_mbps {self.traffic_min_mbps} exceeds "
                f"traffic_max_mbps {self.traffic_max_mbps}"
            )
        if self.traffic_max_mbps > self.link_bandwidth_mbps:
            raise ValueError(
                f"traffic_max_mbps {self.traffic_max_mbps} exceeds "
                f"link_bandwidth_mbps {self.link_bandwidth_mbps}"
            )
        if self.traffic_duration_seconds > self.traffic_round_seconds:
            raise ValueError(
                f"traffic_duration_seconds {self.traffic_duration_seconds} exceeds "
                f"traffic_round_seconds {self.traffic_round_seconds}"
            )

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> Self:
        return cls(
            controller_host=environ.get(PREFIX + "CONTROLLER_HOST", "controller"),
            controller_port=_integer(environ, "CONTROLLER_PORT", 6653),
            depth=_integer(environ, "TREE_DEPTH", 2),
            fanout=_integer(environ, "TREE_FANOUT", 2),
            datapath=_datapath(environ.get(PREFIX + "OVS_DATAPATH", "user")),
            link_bandwidth_mbps=_integer(environ, "LINK_BANDWIDTH_MBPS", 10),
            traffic_enabled=_boolean(environ, "TRAFFIC_ENABLED", True),
            traffic_round_seconds=_integer(environ, "TRAFFIC_ROUND_SECONDS", 15),
            traffic_duration_seconds=_integer(environ, "TRAFFIC_DURATION_SECONDS", 10),
            traffic_min_mbps=_integer(environ, "TRAFFIC_MIN_MBPS", 1),
            traffic_max_mbps=_integer(environ, "TRAFFIC_MAX_MBPS", 8),
            traffic_seed=_integer(environ, "TRAFFIC_SEED", 7),
        )
