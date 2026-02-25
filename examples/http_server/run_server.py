"""Showcases `one_ring_http` to build a simple HTTP server."""

import ssl
from typing import TYPE_CHECKING

from one_ring_http.middleware import (
    MiddlewareStack,
    cors_middleware,
    exception_middleware,
    logging_middleware,
)
from one_ring_http.response import HTTPStatus, Response
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


@router.get("/big")
def big_response(_: Request) -> Response:
    """Sends a large response."""
    return Response(status_code=HTTPStatus.OK, body=b"A" * 1_000_000)


@router.get("/")
def hello_world(_: Request) -> Coro[Response]:
    """Hello!"""
    yield from sleep(1)
    return Response(status_code=HTTPStatus.OK, body=b"Hello world!")


@router.post("/echo")
def echo(request: Request) -> Response:
    """Echoes back body."""
    return Response(status_code=HTTPStatus.OK, body=request.body)


middleware = MiddlewareStack()

middleware.register(exception_middleware)
middleware.register(logging_middleware)
middleware.register(cors_middleware())


server = HTTPServer(
    router=router,
    host="127.0.0.1",
    port=8000,
    ssl_context=ssl_context,
    middleware=middleware,
)

run(server.serve())
