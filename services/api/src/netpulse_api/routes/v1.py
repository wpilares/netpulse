from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict


class ServiceInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str


def build_v1_router(version: str) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["v1"])

    @router.get("/info")
    async def info() -> ServiceInfo:
        return ServiceInfo(name="netpulse", version=version)

    return router
