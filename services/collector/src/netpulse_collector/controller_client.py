import httpx2

from netpulse_core import PortStatsReport

PORT_STATS_PATH = "/stats/ports"


class ControllerClient:
    def __init__(self, http: httpx2.AsyncClient) -> None:
        self._http = http

    async def fetch_port_stats(self) -> PortStatsReport:
        response = await self._http.get(PORT_STATS_PATH)
        response.raise_for_status()
        return PortStatsReport.model_validate_json(response.content)
