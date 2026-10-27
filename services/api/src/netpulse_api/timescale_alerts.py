import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Final

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from netpulse_api.alerts import MAX_ALERT_LIMIT, Alert, AlertStatusFilter, AlertsUnavailableError
from netpulse_api.timescale_stats import ConnectionPool

logger = logging.getLogger(__name__)

ALERT_COLUMNS: Final = sql.SQL(
    "id, seq, dpid, port_no, metric, severity, status, opened_at, last_seen_at, resolved_at, "
    "acknowledged_at, value, expected, zscore, updated_at"
)

LIST_QUERY: Final = sql.SQL("""
    SELECT {columns}
    FROM alerts
    {where}
    ORDER BY opened_at DESC, id DESC
    LIMIT %(limit)s
""")
STATUS_CONDITION: Final = sql.SQL("WHERE status = %(status)s")

AFTER_SEQ_QUERY: Final = sql.SQL("""
    SELECT {columns}
    FROM alerts
    WHERE seq > %(seq)s
    ORDER BY seq
    LIMIT %(limit)s
""")

ACKNOWLEDGE_QUERY: Final = sql.SQL("""
    UPDATE alerts
    SET acknowledged_at = coalesce(acknowledged_at, %(at)s),
        updated_at = CASE WHEN acknowledged_at IS NULL THEN now() ELSE updated_at END,
        seq = CASE WHEN acknowledged_at IS NULL THEN nextval('alerts_seq') ELSE seq END
    WHERE id = %(alert_id)s
    RETURNING {columns}
""")


def list_query(status: AlertStatusFilter) -> sql.Composed:
    where = sql.SQL("") if status == "all" else STATUS_CONDITION
    return LIST_QUERY.format(columns=ALERT_COLUMNS, where=where)


class TimescaleAlertStore:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    async def fetch(self, status: AlertStatusFilter, *, limit: int) -> list[Alert]:
        return await self._fetch(list_query(status), {"status": status, "limit": limit})

    async def fetch_after(self, seq: int, *, limit: int = MAX_ALERT_LIMIT) -> list[Alert]:
        query = AFTER_SEQ_QUERY.format(columns=ALERT_COLUMNS)
        return await self._fetch(query, {"seq": seq, "limit": limit})

    async def acknowledge(self, alert_id: int, *, at: datetime) -> Alert | None:
        query = ACKNOWLEDGE_QUERY.format(columns=ALERT_COLUMNS)
        rows = await self._fetch(query, {"alert_id": alert_id, "at": at})
        return rows[0] if rows else None

    async def _fetch(self, query: sql.Composed, parameters: Mapping[str, object]) -> list[Alert]:
        try:
            async with (
                self._pool.connection() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                await cursor.execute(query, parameters)
                rows = await cursor.fetchall()
        except psycopg.Error as error:
            logger.warning("alert query failed", exc_info=True)
            raise AlertsUnavailableError(str(error)) from error
        return [Alert.model_validate(row) for row in rows]
