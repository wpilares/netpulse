from fastapi import APIRouter, Response, status

from netpulse_api.health import DatabaseProbe, HealthReport, check_health


def build_health_router(probe: DatabaseProbe | None, version: str) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health(response: Response) -> HealthReport:
        report = await check_health(probe, version)
        if report.status != "ok":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return report

    return router
