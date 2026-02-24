from collections.abc import Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from one_ring_http.log import get_logger
from one_ring_http.request import Request
from one_ring_loop import TaskGroup
from one_ring_loop.cancellation import move_on_after
from one_ring_loop.socketio import Connection, create_server
from one_ring_loop.streams.buffered import BufferedByteStream
from one_ring_loop.streams.tls import TLSStream

logger = get_logger()

if TYPE_CHECKING:
    import ssl

    from one_ring_http.router import Router
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
                request = yield from Request.parse(buffered_stream)
                handler = self.router.resolve(request.method, request.path)
                result = handler(request)
                if isinstance(result, Generator):
                    response = yield from result
                else:
                    response = result
                yield from buffered_stream.send(response.serialize())
            finally:
                with move_on_after(3, shield=True):
                    yield from buffered_stream.close()
        except Exception:
            logger.exception("Connection error")
