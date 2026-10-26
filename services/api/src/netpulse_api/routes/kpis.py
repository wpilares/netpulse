from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from netpulse_api.capacity import ConfiguredCapacity, LinkCapacityResolver
from netpulse_api.kpis import (
    KpiHistoryQuery,
    KpiRange,
    KpiRangeParams,
    KpiUnavailableError,
    LatestSamplesQuery,
    NetworkKpiSummary,
    PortKpiSeries,
    SwitchKpis,
    latest_port_kpis,
    network_kpi_summary,
    switch_kpis,
)
from netpulse_core import DatapathId, PortKpis, PortNumber


def build_kpis_router(
    history: KpiHistoryQuery | None,
    latest: LatestSamplesQuery | None,
    *,
    link_capacity_bps: int | None,
    capacity: LinkCapacityResolver | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["kpis"])
    resolver = ConfiguredCapacity(link_capacity_bps) if capacity is None else capacity

    async def latest_kpis(dpid: DatapathId | None) -> list[PortKpis]:
        if latest is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "storage is not configured")
        try:
            pairs = await latest.fetch(dpid)
        except KpiUnavailableError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "storage is unavailable"
            ) from error
        await resolver.refresh()
        return latest_port_kpis(pairs, capacity=resolver)

    @router.get("/switches/{dpid}/ports/{port_no}/kpis")
    async def port_kpi_history(
        dpid: Annotated[DatapathId, Path()],
        port_no: Annotated[PortNumber, Path()],
        params: Annotated[KpiRangeParams, Query()],
    ) -> PortKpiSeries:
        if history is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "storage is not configured")
        request = KpiRange(
            dpid=dpid, port_no=port_no, start=params.start, end=params.end, limit=params.limit
        )
        try:
            points = await history.fetch(request)
        except KpiUnavailableError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "storage is unavailable"
            ) from error
        return PortKpiSeries(dpid=dpid, port_no=port_no, points=tuple(points))

    @router.get("/switches/{dpid}/kpis")
    async def switch_latest_kpis(dpid: Annotated[DatapathId, Path()]) -> SwitchKpis:
        kpis = await latest_kpis(dpid)
        return switch_kpis(dpid, kpis, generated_at=datetime.now(UTC))

    @router.get("/kpis/summary")
    async def network_summary() -> NetworkKpiSummary:
        kpis = await latest_kpis(None)
        return network_kpi_summary(kpis, generated_at=datetime.now(UTC))

    return router
