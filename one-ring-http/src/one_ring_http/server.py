from collections.abc import Generator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_http.log import get_logger
from one_ring_http.middleware import MiddlewareStack
from one_ring_http.request import Request
from one_ring_http.response import HTTPStatus, Response
from one_ring_loop import TaskGroup
from one_ring_loop.cancellation import fail_after, move_on_after
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.socketio import Connection, create_server
from one_ring_loop.streams.buffered import BufferedByteStream
from one_ring_loop.streams.exceptions import EndOfStreamError
from one_ring_loop.streams.tls import TLSStream

logger = get_logger()

if TYPE_CHECKING:
    import ssl

    from one_ring_http.router import Router
    from one_ring_http.typedef import HTTPHandler, HTTPMethod
    from one_ring_loop.typedefs import Coro


@dataclass(frozen=True, slots=True, kw_only=True)
class HTTPServer:
    """A simple HTTP server built on one-ring-loop."""

    """Routes method and path to a handler"""
    router: Router

    """The host for the server to run on"""
    host: str

    """The port for the server to run on"""
    port: int

    """The SSL context for TLS wrapping"""
    ssl_context: ssl.SSLContext

    """Stack of middleware"""
    middleware: MiddlewareStack = field(default_factory=MiddlewareStack)

    def serve(self) -> Coro[None]:
        """Starts the server."""
        server = yield from create_server(self.host.encode(), self.port)
        tg = TaskGroup()
        tg.enter()
        try:
            while True:
                conn = yield from server.accept()
                tg.create_task(self._handle_connection(conn))
        finally:
            yield from tg.exit()

    def _handle_connection(self, conn: Connection) -> Coro[None]:
        """Handles an incoming connection."""
        try:
            try:
                tls_con = yield from TLSStream.wrap(
                    conn, ssl_context=self.ssl_context, standard_compatible=False
                )
            except Exception:
                with move_on_after(3, shield=True):
                    yield from conn.close()
                raise

            buffered_stream = BufferedByteStream(
                receive_stream=tls_con, send_stream=tls_con
            )

            try:
                keep_alive = True
                while keep_alive:
                    request, response = yield from self._handle_request(buffered_stream)

                    if response is None:
                        break

                    if request is None:
                        yield from buffered_stream.send(response.serialize())
                        break

                    if request.headers.get("connection") == "close":
                        response.headers["connection"] = "close"
                        keep_alive = False
                    else:
                        response.headers["connection"] = "keep-alive"

                    yield from buffered_stream.send(response.serialize())
            finally:
                with move_on_after(3, shield=True):
                    yield from buffered_stream.close()
        except Exception:
            logger.exception("An unexpected error occured. No response was sent")

    def _handle_request(
        self, stream: BufferedByteStream
    ) -> Coro[tuple[Request | None, Response | None]]:
        try:
            with fail_after(5):
                request = yield from Request.parse(stream)
        except Cancelled:
            return None, None
        except EndOfStreamError:
            return None, None
        except Exception:
            logger.exception("Failed to parse request")
            return None, Response(
                status_code=HTTPStatus.BAD_REQUEST, body=b"Bad Request"
            )

        handler = self._get_handler(request.method, request.path)
        result = handler(request)
        if isinstance(result, Generator):
            response = yield from result
        else:
            response = result

        return request, response

    def _get_handler(self, method: HTTPMethod, path: str) -> HTTPHandler:
        """Gets handler from router and applies all middleware.

        TODO: don't apply middleware on each request...
        """
        handler = self.router.resolve(method, path)
        for middleware in self.middleware:
            handler = middleware(handler)

        return handler
