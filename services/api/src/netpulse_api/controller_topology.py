import httpx2
from pydantic import ValidationError

from netpulse_api.topology import ControllerTopology, TopologyUnavailableError

TOPOLOGY_PATH = "/topology"


class ControllerTopologyQuery:
    def __init__(self, http: httpx2.AsyncClient) -> None:
        self._http = http

    async def fetch(self) -> ControllerTopology:
        try:
            response = await self._http.get(TOPOLOGY_PATH)
            response.raise_for_status()
            return ControllerTopology.model_validate_json(response.content)
        except (httpx2.HTTPError, ValidationError) as error:
            raise TopologyUnavailableError(str(error)) from error
