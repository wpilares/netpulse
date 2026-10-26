import logging
from collections.abc import Iterable, Mapping
from itertools import groupby, pairwise
from typing import Final, LiteralString

import psycopg
from psycopg.rows import TupleRow, dict_row
from psycopg_pool import AsyncConnectionPool

from netpulse_api.kpis import KpiRange, KpiUnavailableError, SamplePair
from netpulse_core import DatapathId, PortKpis, PortSample, compute_port_kpis

logger = logging.getLogger(__name__)

type ConnectionPool = AsyncConnectionPool[psycopg.AsyncConnection[TupleRow]]

SAMPLE_COLUMNS: Final = frozenset({"dpid", "collected_at"})

HISTORY_QUERY: Final[LiteralString] = """
    SELECT dpid, port_no, bucket AS collected_at,
           rx_packets, tx_packets, rx_bytes, tx_bytes,
           rx_dropped, tx_dropped, rx_errors, tx_errors, duration_sec
    FROM port_stats_1m
    WHERE dpid = %(dpid)s::numeric AND port_no = %(port_no)s
      AND bucket >= %(start)s AND bucket < %(end)s
    ORDER BY bucket
    LIMIT %(limit)s
"""

LATEST_QUERIES: Final[dict[bool, LiteralString]] = {
    False: """
        SELECT dpid, port_no, time AS collected_at,
               rx_packets, tx_packets, rx_bytes, tx_bytes,
               rx_dropped, tx_dropped, rx_errors, tx_errors, duration_sec
        FROM (
            SELECT *, row_number() OVER (PARTITION BY dpid, port_no ORDER BY time DESC) AS recency
            FROM port_stats
        ) AS ranked
        WHERE recency <= 2
        ORDER BY dpid, port_no, time
    """,
    True: """
        SELECT dpid, port_no, time AS collected_at,
               rx_packets, tx_packets, rx_bytes, tx_bytes,
               rx_dropped, tx_dropped, rx_errors, tx_errors, duration_sec
        FROM (
            SELECT *, row_number() OVER (PARTITION BY dpid, port_no ORDER BY time DESC) AS recency
            FROM port_stats
            WHERE dpid = %(dpid)s::numeric
        ) AS ranked
        WHERE recency <= 2
        ORDER BY dpid, port_no, time
    """,
}


def sample_from_row(row: Mapping[str, object]) -> PortSample:
    counters = {column: value for column, value in row.items() if column not in SAMPLE_COLUMNS}
    return PortSample.model_validate(
        {"dpid": row["dpid"], "collected_at": row["collected_at"], "stats": counters}
    )


def pair_latest_samples(samples: Iterable[PortSample]) -> list[SamplePair]:
    by_port = groupby(samples, key=lambda sample: (sample.dpid, sample.stats.port_no))
    pairs: list[SamplePair] = []
    for _, port_samples in by_port:
        ordered = sorted(port_samples, key=lambda sample: sample.collected_at)
        if len(ordered) == 2:
            pairs.append((ordered[0], ordered[1]))
    return pairs


async def _fetch_samples(
    pool: ConnectionPool, query: LiteralString, parameters: Mapping[str, object]
) -> list[PortSample]:
    try:
        async with (
            pool.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(query, parameters)
            rows = await cursor.fetchall()
    except psycopg.Error as error:
        logger.warning("kpi query failed", exc_info=True)
        raise KpiUnavailableError(str(error)) from error
    return [sample_from_row(row) for row in rows]


class TimescaleKpiHistoryQuery:
    def __init__(self, pool: ConnectionPool, *, link_capacity_bps: int | None) -> None:
        self._pool = pool
        self._link_capacity_bps = link_capacity_bps

    async def fetch(self, request: KpiRange) -> list[PortKpis]:
        parameters = request.model_dump(include={"dpid", "port_no", "start", "end"})
        parameters["limit"] = request.limit + 1
        samples = await _fetch_samples(self._pool, HISTORY_QUERY, parameters)
        return [
            compute_port_kpis(previous, current, link_capacity_bps=self._link_capacity_bps)
            for previous, current in pairwise(samples)
        ]


class TimescaleLatestSamplesQuery:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    async def fetch(self, dpid: DatapathId | None) -> list[SamplePair]:
        samples = await _fetch_samples(self._pool, LATEST_QUERIES[dpid is not None], {"dpid": dpid})
        return pair_latest_samples(samples)
