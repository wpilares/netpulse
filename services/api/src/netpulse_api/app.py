from importlib.metadata import version

from fastapi import FastAPI

from netpulse_api.health import DatabaseProbe
from netpulse_api.routes.health import build_health_router
from netpulse_api.routes.telemetry_ws import build_telemetry_router
from netpulse_api.routes.v1 import build_v1_router

SERVICE_VERSION = version("netpulse-api")


def create_app(*, database_probe: DatabaseProbe | None) -> FastAPI:
    app = FastAPI(title="NetPulse API", version=SERVICE_VERSION)
    app.include_router(build_health_router(database_probe, SERVICE_VERSION))
    app.include_router(build_v1_router(SERVICE_VERSION))
    app.include_router(build_telemetry_router(SERVICE_VERSION))
    return app
