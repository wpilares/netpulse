from importlib.metadata import version

from fastapi import FastAPI
from starlette.types import Lifespan

from netpulse_api.alerts import AlertCommand, AlertsQuery
from netpulse_api.health import DatabaseProbe
from netpulse_api.kpis import KpiHistoryQuery, LatestSamplesQuery
from netpulse_api.live import LiveKpiBroadcaster
from netpulse_api.routes.alerts import build_alerts_router
from netpulse_api.routes.health import build_health_router
from netpulse_api.routes.kpis import build_kpis_router
from netpulse_api.routes.stats import build_stats_router
from netpulse_api.routes.telemetry_ws import build_telemetry_router
from netpulse_api.routes.topology import build_topology_router
from netpulse_api.routes.v1 import build_v1_router
from netpulse_api.stats import PortStatsQuery
from netpulse_api.topology import TopologyQuery

SERVICE_VERSION = version("netpulse-api")


def create_app(
    *,
    database_probe: DatabaseProbe | None,
    port_stats_query: PortStatsQuery | None = None,
    kpi_history: KpiHistoryQuery | None = None,
    latest_samples: LatestSamplesQuery | None = None,
    link_capacity_bps: int | None = None,
    live_broadcaster: LiveKpiBroadcaster | None = None,
    topology_query: TopologyQuery | None = None,
    alerts_query: AlertsQuery | None = None,
    alert_command: AlertCommand | None = None,
    lifespan: Lifespan[FastAPI] | None = None,
) -> FastAPI:
    app = FastAPI(title="NetPulse API", version=SERVICE_VERSION, lifespan=lifespan)
    app.include_router(build_health_router(database_probe, SERVICE_VERSION))
    app.include_router(build_v1_router(SERVICE_VERSION))
    app.include_router(build_stats_router(port_stats_query))
    app.include_router(
        build_kpis_router(kpi_history, latest_samples, link_capacity_bps=link_capacity_bps)
    )
    app.include_router(build_telemetry_router(SERVICE_VERSION, broadcaster=live_broadcaster))
    app.include_router(build_topology_router(topology_query))
    app.include_router(build_alerts_router(alerts_query, alert_command))
    return app
