from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from netpulse_api.topology import Topology, TopologyQuery, TopologyUnavailableError, build_topology


def build_topology_router(query: TopologyQuery | None) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["topology"])

    @router.get("/topology")
    async def topology() -> Topology:
        if query is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "controller is not configured")
        try:
            controller = await query.fetch()
        except TopologyUnavailableError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "controller is unavailable"
            ) from error
        return build_topology(controller, generated_at=datetime.now(UTC))

    return router
