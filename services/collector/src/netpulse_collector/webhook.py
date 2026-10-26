import logging
from collections.abc import Sequence

import httpx2

from netpulse_core import AlertEvent, AlertState

logger = logging.getLogger(__name__)


def alert_payload(state: AlertState) -> dict[str, object]:
    dpid, port_no, metric = state.key
    return {
        "dpid": dpid,
        "port_no": port_no,
        "metric": metric,
        **state.model_dump(mode="json", exclude={"key"}),
    }


def events_payload(events: Sequence[AlertEvent]) -> dict[str, object]:
    return {
        "events": [{"kind": event.kind, "alert": alert_payload(event.state)} for event in events]
    }


class WebhookAlertNotifier:
    def __init__(self, http: httpx2.AsyncClient, url: str) -> None:
        self._http = http
        self._url = url

    async def notify(self, events: Sequence[AlertEvent]) -> None:
        if not events:
            return
        try:
            response = await self._http.post(self._url, json=events_payload(events))
            response.raise_for_status()
        except httpx2.HTTPError as error:
            logger.error(
                "alert webhook delivery of %d events failed: %s", len(events), describe_error(error)
            )
            return
        logger.info("delivered %d alert events to webhook", len(events))


def describe_error(error: httpx2.HTTPError) -> str:
    name = type(error).__name__
    if isinstance(error, httpx2.HTTPStatusError):
        return f"{name} status={error.response.status_code}"
    return name
