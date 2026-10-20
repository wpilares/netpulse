from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Self

PREFIX = "NETPULSE_CONTROLLER_"


def _read[T](environ: Mapping[str, str], name: str, parse: Callable[[str], T], default: T) -> T:
    raw = environ.get(PREFIX + name)
    if raw is None:
        return default
    try:
        return parse(raw)
    except ValueError as error:
        raise ValueError(f"{PREFIX}{name} is invalid: {raw!r}") from error


@dataclass(frozen=True, slots=True)
class ControllerSettings:
    openflow_port: int
    rest_host: str
    rest_port: int
    stats_interval_seconds: float

    def __post_init__(self) -> None:
        if self.stats_interval_seconds <= 0:
            raise ValueError(f"{PREFIX}STATS_INTERVAL_SECONDS must be positive")

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> Self:
        return cls(
            openflow_port=_read(environ, "OPENFLOW_PORT", int, 6653),
            rest_host=environ.get(PREFIX + "REST_HOST", "127.0.0.1"),
            rest_port=_read(environ, "REST_PORT", int, 8080),
            stats_interval_seconds=_read(environ, "STATS_INTERVAL_SECONDS", float, 5.0),
        )
