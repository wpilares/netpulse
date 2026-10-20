import logging
from datetime import datetime

import psycopg
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from netpulse_collector.repository import PortStatsWriteError, TransientPortStatsWriteError
from netpulse_core import PortStatsReport

logger = logging.getLogger(__name__)

MAX_BIGINT = 2**63 - 1

type ConnectionPool = AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]]
type Counter = int | None
type PortStatsRow = tuple[
    datetime,
    int,
    int,
    Counter,
    Counter,
    Counter,
    Counter,
    Counter,
    Counter,
    Counter,
    Counter,
    Counter,
]

INSERT_PORT_STATS = """
    INSERT INTO port_stats (
        time, dpid, port_no,
        rx_packets, tx_packets, rx_bytes, tx_bytes,
        rx_dropped, tx_dropped, rx_errors, tx_errors,
        duration_sec
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT DO NOTHING
"""


def _counter(value: int) -> Counter:
    return value if value <= MAX_BIGINT else None


def port_stats_rows(report: PortStatsReport) -> list[PortStatsRow]:
    return [
        (
            switch.collected_at,
            switch.dpid,
            port.port_no,
            _counter(port.rx_packets),
            _counter(port.tx_packets),
            _counter(port.rx_bytes),
            _counter(port.tx_bytes),
            _counter(port.rx_dropped),
            _counter(port.tx_dropped),
            _counter(port.rx_errors),
            _counter(port.tx_errors),
            _counter(port.duration_sec),
        )
        for switch in report.switches
        for port in switch.ports
    ]


class TimescalePortStatsRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    async def save(self, report: PortStatsReport) -> None:
        rows = port_stats_rows(report)
        if not rows:
            return
        try:
            async with self._pool.connection() as connection, connection.cursor() as cursor:
                await cursor.executemany(INSERT_PORT_STATS, rows)
        except psycopg.OperationalError as error:
            raise TransientPortStatsWriteError(str(error)) from error
        except psycopg.Error as error:
            raise PortStatsWriteError(str(error)) from error
        logger.info("stored %d port samples from %d switches", len(rows), len(report.switches))
