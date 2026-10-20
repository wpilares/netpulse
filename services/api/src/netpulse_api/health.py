import logging
from typing import Literal, Protocol

import psycopg
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

DatabaseState = Literal["up", "down", "disabled"]


class DatabaseProbe(Protocol):
    async def is_reachable(self) -> bool: ...


class PostgresProbe:
    def __init__(self, dsn: str, *, timeout_seconds: float) -> None:
        self._dsn = dsn
        self._timeout_seconds = timeout_seconds

    async def is_reachable(self) -> bool:
        try:
            async with await psycopg.AsyncConnection.connect(
                self._dsn, connect_timeout=max(1, round(self._timeout_seconds))
            ) as connection:
                await connection.execute("SELECT 1")
        except psycopg.Error:
            logger.warning("database health check failed", exc_info=True)
            return False
        return True


class HealthReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "degraded"]
    database: DatabaseState
    version: str


async def check_health(probe: DatabaseProbe | None, version: str) -> HealthReport:
    if probe is None:
        return HealthReport(status="ok", database="disabled", version=version)
    if await probe.is_reachable():
        return HealthReport(status="ok", database="up", version=version)
    return HealthReport(status="degraded", database="down", version=version)
