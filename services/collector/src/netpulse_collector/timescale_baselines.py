import logging
from collections.abc import Iterable, Mapping
from typing import Final

import psycopg
from pydantic import TypeAdapter

from netpulse_collector.alerts import AlertReadError, AlertWriteError
from netpulse_collector.timescale_repository import ConnectionPool
from netpulse_core import Baseline, BaselineKey

logger = logging.getLogger(__name__)

type BaselineRow = tuple[object, ...]

UPSERT_BASELINE: Final = """
    INSERT INTO alert_baselines (dpid, port_no, metric, mean, variance, samples, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, now())
    ON CONFLICT (dpid, port_no, metric)
    DO UPDATE SET mean = EXCLUDED.mean, variance = EXCLUDED.variance,
        samples = EXCLUDED.samples, updated_at = now()
"""

DELETE_BASELINE: Final = """
    DELETE FROM alert_baselines
    WHERE dpid = %s::numeric AND port_no = %s AND metric = %s
"""

SELECT_BASELINES: Final = """
    SELECT dpid, port_no, metric, mean, variance, samples
    FROM alert_baselines
    ORDER BY dpid, port_no, metric
"""

BASELINE_KEY: Final = TypeAdapter[BaselineKey](BaselineKey)


def baseline_parameters(key: BaselineKey, baseline: Baseline) -> tuple[object, ...]:
    dpid, port_no, metric = key
    return (dpid, port_no, metric, baseline.mean, baseline.variance, baseline.samples)


def stored_baseline(row: BaselineRow) -> tuple[BaselineKey, Baseline]:
    dpid, port_no, metric, mean, variance, samples = row
    key = BASELINE_KEY.validate_python((dpid, port_no, metric))
    return key, Baseline.model_validate({"mean": mean, "variance": variance, "samples": samples})


class TimescaleBaselineRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    async def load(self) -> dict[BaselineKey, Baseline]:
        try:
            async with self._pool.connection() as connection, connection.cursor() as cursor:
                await cursor.execute(SELECT_BASELINES)
                rows = await cursor.fetchall()
        except psycopg.Error as error:
            raise AlertReadError(type(error).__name__) from error
        return dict(stored_baseline(row) for row in rows)

    async def save(self, baselines: Mapping[BaselineKey, Baseline]) -> None:
        rows = [baseline_parameters(key, baseline) for key, baseline in baselines.items()]
        if not rows:
            return
        try:
            async with self._pool.connection() as connection, connection.cursor() as cursor:
                await cursor.executemany(UPSERT_BASELINE, rows)
        except psycopg.Error as error:
            raise AlertWriteError(str(error)) from error
        logger.debug("stored %d baselines", len(rows))

    async def delete(self, keys: Iterable[BaselineKey]) -> None:
        rows = [tuple(key) for key in keys]
        if not rows:
            return
        try:
            async with self._pool.connection() as connection, connection.cursor() as cursor:
                await cursor.executemany(DELETE_BASELINE, rows)
        except psycopg.Error as error:
            raise AlertWriteError(str(error)) from error
        logger.info("deleted %d baselines of pruned ports", len(rows))
