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


_DATAPATHS: dict[str, Datapath] = {"kernel": "kernel", "user": "user"}


def _datapath(raw: str) -> Datapath:
    if raw not in _DATAPATHS:
        raise ValueError(f"unsupported OVS datapath {raw!r}, expected one of {sorted(_DATAPATHS)}")
    return _DATAPATHS[raw]


@dataclass(frozen=True, slots=True)
class NetworkConfig:
    controller_host: str
    controller_port: int
    depth: int
    fanout: int
    datapath: Datapath

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> Self:
        return cls(
            controller_host=environ.get(PREFIX + "CONTROLLER_HOST", "controller"),
            controller_port=_integer(environ, "CONTROLLER_PORT", 6653),
            depth=_integer(environ, "TREE_DEPTH", 2),
            fanout=_integer(environ, "TREE_FANOUT", 2),
            datapath=_datapath(environ.get(PREFIX + "OVS_DATAPATH", "user")),
        )
