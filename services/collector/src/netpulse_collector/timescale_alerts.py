import logging
from collections.abc import Sequence
from typing import Final

import psycopg

from netpulse_collector.alerts import AlertWriteError
from netpulse_collector.timescale_repository import ConnectionPool
from netpulse_core import AlertEvent

logger = logging.getLogger(__name__)

type Statement = tuple[str, tuple[object, ...]]

INSERT_ALERT: Final = """
    INSERT INTO alerts (
        dpid, port_no, metric, severity, status,
        opened_at, last_seen_at, resolved_at,
        value, expected, zscore, updated_at
    )
    VALUES (%s, %s, %s, %s, 'open', %s, %s, NULL, %s, %s, %s, now())
"""

REFRESH_OPEN_ALERT: Final = """
    UPDATE alerts
    SET severity = %s, last_seen_at = %s, value = %s, expected = %s, zscore = %s,
        updated_at = now()
    WHERE dpid = %s::numeric AND port_no = %s AND metric = %s AND status = 'open'
"""

RESOLVE_OPEN_ALERT: Final = """
    UPDATE alerts
    SET status = 'resolved', resolved_at = %s, updated_at = now()
    WHERE dpid = %s::numeric AND port_no = %s AND metric = %s AND status = 'open'
"""


def alert_statement(event: AlertEvent) -> Statement | None:
    state = event.state
    dpid, port_no, metric = state.key
    match event.kind:
        case "opened":
            return INSERT_ALERT, (
                dpid,
                port_no,
                metric,
                state.severity,
                state.opened_at,
                state.last_seen_at,
                state.value,
                state.expected,
                state.zscore,
            )
        case "refreshed" | "escalated":
            return REFRESH_OPEN_ALERT, (
                state.severity,
                state.last_seen_at,
                state.value,
                state.expected,
                state.zscore,
                dpid,
                port_no,
                metric,
            )
        case "resolved":
            return RESOLVE_OPEN_ALERT, (state.resolved_at, dpid, port_no, metric)
        case "suppressed":
            return None


class TimescaleAlertRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    async def apply(self, events: Sequence[AlertEvent]) -> None:
        statements = [
            statement for event in events if (statement := alert_statement(event)) is not None
        ]
        if not statements:
            return
        try:
            async with self._pool.connection() as connection, connection.cursor() as cursor:
                for query, parameters in statements:
                    await cursor.execute(query, parameters)
        except psycopg.Error as error:
            raise AlertWriteError(str(error)) from error
        logger.info("stored %d alert events", len(statements))
