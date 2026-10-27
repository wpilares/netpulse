import logging
from collections.abc import Sequence
from datetime import timedelta
from typing import Final

import psycopg

from netpulse_collector.alerts import AlertReadError, AlertWriteError
from netpulse_collector.timescale_repository import ConnectionPool
from netpulse_core import AlertEvent, AlertState

logger = logging.getLogger(__name__)

type Statement = tuple[str, tuple[object, ...]]
type OpenAlertRow = tuple[object, ...]

UPSERT_OPEN_ALERT: Final = """
    INSERT INTO alerts (
        dpid, port_no, metric, severity, status,
        opened_at, last_seen_at, resolved_at,
        value, expected, zscore, updated_at
    )
    VALUES (%s, %s, %s, %s, 'open', %s, %s, NULL, %s, %s, %s, now())
    ON CONFLICT (dpid, port_no, metric) WHERE status = 'open'
    DO UPDATE SET severity = EXCLUDED.severity, last_seen_at = EXCLUDED.last_seen_at,
        value = EXCLUDED.value, expected = EXCLUDED.expected, zscore = EXCLUDED.zscore,
        updated_at = now(), seq = nextval('alerts_seq')
"""

REFRESH_OPEN_ALERT: Final = """
    UPDATE alerts
    SET severity = %s, last_seen_at = %s, value = %s, expected = %s, zscore = %s,
        updated_at = now(), seq = nextval('alerts_seq')
    WHERE dpid = %s::numeric AND port_no = %s AND metric = %s AND status = 'open'
"""

RESOLVE_OPEN_ALERT: Final = """
    UPDATE alerts
    SET status = 'resolved', resolved_at = %s, updated_at = now(), seq = nextval('alerts_seq')
    WHERE dpid = %s::numeric AND port_no = %s AND metric = %s AND status = 'open'
"""

PURGE_RESOLVED_ALERTS: Final = """
    DELETE FROM alerts
    WHERE status = 'resolved' AND resolved_at < now() - %(older_than)s
"""

SELECT_OPEN_ALERTS: Final = """
    SELECT dpid, port_no, metric, severity, opened_at, last_seen_at, value, expected, zscore
    FROM alerts
    WHERE status = 'open'
    ORDER BY dpid, port_no, metric
"""


def alert_statement(event: AlertEvent) -> Statement | None:
    state = event.state
    dpid, port_no, metric = state.key
    match event.kind:
        case "opened":
            return UPSERT_OPEN_ALERT, (
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


def open_alert_state(row: OpenAlertRow) -> AlertState:
    dpid, port_no, metric, severity, opened_at, last_seen_at, value, expected, zscore = row
    return AlertState.model_validate(
        {
            "key": (dpid, port_no, metric),
            "severity": severity,
            "opened_at": opened_at,
            "last_seen_at": last_seen_at,
            "value": value,
            "expected": expected,
            "zscore": zscore,
            "status": "open",
            "resolved_at": None,
        }
    )


class TimescaleAlertRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    async def load_open(self) -> tuple[AlertState, ...]:
        try:
            async with self._pool.connection() as connection, connection.cursor() as cursor:
                await cursor.execute(SELECT_OPEN_ALERTS)
                rows = await cursor.fetchall()
        except psycopg.Error as error:
            raise AlertReadError(type(error).__name__) from error
        return tuple(open_alert_state(row) for row in rows)

    async def apply(self, events: Sequence[AlertEvent]) -> None:
        planned = [
            (event, statement)
            for event in events
            if (statement := alert_statement(event)) is not None
        ]
        if not planned:
            return
        try:
            async with self._pool.connection() as connection, connection.cursor() as cursor:
                for event, (query, parameters) in planned:
                    await cursor.execute(query, parameters)
                    if event.kind != "opened" and cursor.rowcount == 0:
                        _warn_unmatched(event)
        except psycopg.Error as error:
            raise AlertWriteError(str(error)) from error
        logger.info("stored %d alert events", len(planned))

    async def purge_resolved(self, older_than: timedelta) -> int:
        try:
            async with self._pool.connection() as connection, connection.cursor() as cursor:
                await cursor.execute(PURGE_RESOLVED_ALERTS, {"older_than": older_than})
                return cursor.rowcount
        except psycopg.Error as error:
            raise AlertWriteError(str(error)) from error


def _warn_unmatched(event: AlertEvent) -> None:
    dpid, port_no, metric = event.state.key
    logger.warning(
        "%s alert event matched no open alert: dpid=%s port=%s metric=%s",
        event.kind,
        dpid,
        port_no,
        metric,
    )
