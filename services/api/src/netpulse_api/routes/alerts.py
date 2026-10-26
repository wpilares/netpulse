from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from netpulse_api.alerts import (
    Alert,
    AlertCommand,
    AlertList,
    AlertListParams,
    AlertsQuery,
    AlertsUnavailableError,
)


def build_alerts_router(query: AlertsQuery | None, command: AlertCommand | None) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["alerts"])

    @router.get("/alerts")
    async def list_alerts(params: Annotated[AlertListParams, Query()]) -> AlertList:
        if query is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "storage is not configured")
        try:
            alerts = await query.fetch(params.status, limit=params.limit)
        except AlertsUnavailableError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "storage is unavailable"
            ) from error
        return AlertList(generated_at=datetime.now(UTC), alerts=tuple(alerts))

    @router.post("/alerts/{alert_id}/ack")
    async def acknowledge_alert(alert_id: Annotated[int, Path()]) -> Alert:
        if command is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "storage is not configured")
        try:
            alert = await command.acknowledge(alert_id, at=datetime.now(UTC))
        except AlertsUnavailableError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "storage is unavailable"
            ) from error
        if alert is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")
        return alert

    return router
