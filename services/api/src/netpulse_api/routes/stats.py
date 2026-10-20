from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from netpulse_api.stats import (
    PortStatsParams,
    PortStatsQuery,
    PortStatsRange,
    PortStatsSeries,
    PortStatsUnavailableError,
)
from netpulse_core import DatapathId, PortNumber


def build_stats_router(query: PortStatsQuery | None) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["stats"])

    @router.get("/switches/{dpid}/ports/{port_no}/stats")
    async def port_stats(
        dpid: Annotated[DatapathId, Path()],
        port_no: Annotated[PortNumber, Path()],
        params: Annotated[PortStatsParams, Query()],
    ) -> PortStatsSeries:
        if query is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "storage is not configured")
        request = PortStatsRange(
            dpid=dpid,
            port_no=port_no,
            start=params.start,
            end=params.end,
            resolution=params.resolution,
            limit=params.limit,
        )
        try:
            points = await query.fetch(request)
        except PortStatsUnavailableError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "storage is unavailable"
            ) from error
        return PortStatsSeries(
            dpid=dpid, port_no=port_no, resolution=params.resolution, points=tuple(points)
        )

    return router
