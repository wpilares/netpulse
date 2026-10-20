import json
import logging
from collections.abc import Callable, Iterable
from http import HTTPStatus
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server
from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

from netpulse_controller.stats_store import Json, StatsStore

logger = logging.getLogger(__name__)


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class LoggingRequestHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        logger.debug(format, *args)


def _respond(start_response: StartResponse, status: HTTPStatus, payload: Json) -> list[bytes]:
    body = json.dumps(payload).encode()
    start_response(
        f"{status.value} {status.phrase}",
        [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
    )
    return [body]


def create_rest_app(store: StatsStore) -> WSGIApplication:
    routes: dict[str, Callable[[], Json]] = {
        "/health": lambda: {"status": "ok"},
        "/switches": lambda: {"switches": list(store.switches())},
        "/stats/ports": store.port_stats_report,
    }

    def application(environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        handler = routes.get(environ.get("PATH_INFO", ""))
        if handler is None:
            return _respond(start_response, HTTPStatus.NOT_FOUND, {"error": "not found"})
        if environ.get("REQUEST_METHOD") != "GET":
            return _respond(
                start_response, HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"}
            )
        return _respond(start_response, HTTPStatus.OK, handler())

    return application


def create_rest_server(store: StatsStore, host: str, port: int) -> WSGIServer:
    return make_server(
        host,
        port,
        create_rest_app(store),
        server_class=ThreadingWSGIServer,
        handler_class=LoggingRequestHandler,
    )
