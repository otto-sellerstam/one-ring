"""Showcases `one_ring_http` to build a simple HTTP server."""

import ssl
import time
from typing import TYPE_CHECKING

from one_ring_http.middleware import (
    MiddlewareStack,
    cors_middleware,
    exception_middleware,
    logging_middleware,
)
from one_ring_http.response import Response, StreamingResponse
from one_ring_http.router import Router
from one_ring_http.server import HTTPServer
from one_ring_http.sse import ServerSentEvent
from one_ring_http.static import static_handler
from one_ring_http.status import HTTPStatus
from one_ring_http.websocket import WSConnectionClosedError
from one_ring_loop import run
from one_ring_loop.streams.memory import create_memory_object_stream
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_http.request import Request
    from one_ring_http.websocket import WebSocket
    from one_ring_loop.typedefs import Coro

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain("dev-cert.pem", "dev-key.pem")

router = Router()

router.set_404_fallback(static_handler("./examples/http_server/static"))


@router.get("/big")
def big_response(_: Request) -> Response:
    """Sends a large response."""
    return Response.text("A" * 1_000_000)


@router.get("/{a}")
def dynamic_var(request: Request) -> Coro[Response]:
    """Sends a large response."""
    return Response.text(str(request.path_params))


@router.get("/")
def hello_world(_: Request) -> Coro[Response]:
    """Hello!"""
    yield from sleep(1)
    return Response.text("Hello world!")


@router.get("/sync-sleep")
def sync_sleep(_: Request) -> Coro[Response]:
    """Send concurrent requests to test thread pooling."""
    time.sleep(1)
    return Response.text("Hello world!")


@router.post("/echo")
def echo(request: Request) -> Response:
    """Echoes back body."""
    return Response(status_code=HTTPStatus.OK, body=request.body)


@router.get("/streaming")
def streaming(_: Request) -> StreamingResponse:
    """Streams a simple response to the client."""
    send_stream, receive_stream = create_memory_object_stream[bytes]()

    def producer() -> Coro[None]:
        for word in ["hej!", "jag", "heter", "otto", "sellerstam", ":)"]:
            event = ServerSentEvent(data=word, event=None)
            print("Producer: sending", word)
            yield from send_stream.send(event.encode())
            print("Producer: sleeping")
            yield from sleep(1)

        yield from send_stream.close()

    return StreamingResponse(
        status_code=HTTPStatus.OK,
        body_stream=receive_stream,
        producer=producer(),
        headers={
            "content-type": "text/event-stream",
            "cache-control": "no-cache",
        },
    )


class ConnectionManager:
    """Simple example of a manager for multiple connections."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    def connect(self, websocket: WebSocket) -> None:  # noqa: D102
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:  # noqa: D102
        self.active_connections.remove(websocket)

    def send_personal_message(self, message: str, websocket: WebSocket) -> Coro[None]:  # noqa: D102
        yield from websocket.send_text(message)

    def broadcast(self, message: str) -> Coro[None]:  # noqa: D102
        for connection in self.active_connections:
            yield from connection.send_text(message)


manager = ConnectionManager()


@router.websocket("/ws")
def ws(websocket: WebSocket) -> Coro[None]:
    """Create a websocket! FastAPI style."""
    manager.connect(websocket)
    try:
        while True:
            _, payload = yield from websocket.receive()
            yield from manager.send_personal_message(
                f"You wrote: {payload.decode()}", websocket
            )
            yield from manager.broadcast(f"Client says: {payload.decode()}")
    except WSConnectionClosedError:
        manager.disconnect(websocket)
        yield from manager.broadcast("A client disconnected. Who? Dunno")


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
