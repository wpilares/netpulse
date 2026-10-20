import logging
from typing import Final, LiteralString

import psycopg
from psycopg.rows import TupleRow, dict_row
from psycopg_pool import AsyncConnectionPool

from netpulse_api.stats import (
    PortStatsPoint,
    PortStatsRange,
    PortStatsUnavailableError,
    Resolution,
)

logger = logging.getLogger(__name__)

type ConnectionPool = AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]]

QUERIES: Final[dict[Resolution, LiteralString]] = {
    "raw": """
        SELECT time, rx_packets, tx_packets, rx_bytes, tx_bytes,
               rx_dropped, tx_dropped, rx_errors, tx_errors,
               duration_sec, 1 AS samples
        FROM port_stats
        WHERE dpid = %(dpid)s::numeric AND port_no = %(port_no)s
          AND time >= %(start)s AND time < %(end)s
        ORDER BY time
        LIMIT %(limit)s
    """,
    "1m": """
        SELECT bucket AS time, rx_packets, tx_packets, rx_bytes, tx_bytes,
               rx_dropped, tx_dropped, rx_errors, tx_errors,
               duration_sec, samples
        FROM port_stats_1m
        WHERE dpid = %(dpid)s::numeric AND port_no = %(port_no)s
          AND bucket >= %(start)s AND bucket < %(end)s
        ORDER BY bucket
        LIMIT %(limit)s
    """,
}


class TimescalePortStatsQuery:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    async def fetch(self, request: PortStatsRange) -> list[PortStatsPoint]:
        parameters = request.model_dump(include={"dpid", "port_no", "start", "end", "limit"})
        try:
            async with (
                self._pool.connection() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                await cursor.execute(QUERIES[request.resolution], parameters)
                rows = await cursor.fetchall()
        except psycopg.Error as error:
            logger.warning("port stats query failed", exc_info=True)
            raise PortStatsUnavailableError(str(error)) from error
        return [PortStatsPoint.model_validate(row) for row in rows]
