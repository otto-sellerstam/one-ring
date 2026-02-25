"""Showcases `one_ring_http` to build a simple HTTP server."""

import ssl
from typing import TYPE_CHECKING

from one_ring_http.response import Response
from one_ring_http.router import Router
from one_ring_http.server import HTTPServer
from one_ring_http.static import static_handler
from one_ring_loop import run
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_http.request import Request
    from one_ring_loop.typedefs import Coro


ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain("dev-cert.pem", "dev-key.pem")


router = Router()

router.set_fallback(static_handler("./examples/http_server/static"))


@router.register("GET", "/big")
def big_response(request: Request) -> Response:
    """Sends a large response."""
    print("Received request", request)
    return Response(status_code=200, body=b"A" * 1_000_000)


@router.register("GET", "/")
def hello_world(request: Request) -> Coro[Response]:
    """Hello!"""
    print("Received request", request)
    yield from sleep(1)
    return Response(status_code=200, headers={}, body=b"Hello world!")


@router.register("POST", "/echo")
def echo(request: Request) -> Response:
    """Echoes back body."""
    return Response(status_code=200, headers={}, body=request.body)


server = HTTPServer(router=router, host="127.0.0.1", port=8000, ssl_context=ssl_context)

run(server.serve())
