import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeIs

from one_ring_http.log import get_logger
from one_ring_http.middleware import MiddlewareStack
from one_ring_http.request import Request
from one_ring_http.response import Response, StreamingResponse
from one_ring_http.status import HTTPStatus
from one_ring_http.websocket import WebSocket
from one_ring_loop import TaskGroup
from one_ring_loop.cancellation import fail_after, move_on_after
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.socketio import Connection, create_server
from one_ring_loop.streams.buffered import BufferedByteStream
from one_ring_loop.streams.exceptions import EndOfStreamError
from one_ring_loop.streams.tls import TLSStream
from one_ring_loop.threadpool import run_in_thread

logger = get_logger()

if TYPE_CHECKING:
    import ssl

    from one_ring_http.router import Router
    from one_ring_http.typedef import (
        AsyncHTTPHandler,
        HTTPHandler,
    )
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
        server = yield from create_server(self.host, self.port)
        tg = TaskGroup()
        tg.enter()
        try:
            while True:
                conn = yield from server.accept()
                tg.create_task(self._handle_connection(conn))
        finally:
            yield from tg.exit()

    # TODO: Refactor.
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
                        # Only happens if request parsing failed.
                        response = Response(
                            status_code=HTTPStatus.BAD_REQUEST, body=b"Bad Request"
                        )
                        yield from buffered_stream.send(response.serialize())
                        break

                    if request.headers.get("connection") == "close":
                        response.headers["connection"] = "close"
                        keep_alive = False
                    elif response.headers.get("connection") != "upgrade":
                        response.headers["connection"] = "keep-alive"

                    yield from self._handle_response(buffered_stream, request, response)

                    if response.status_code == HTTPStatus.SWITCHING_PROTOCOLS:
                        ws_handler = self.router.resolve_websocket(request.path)
                        websocket = WebSocket(stream=buffered_stream)
                        yield from ws_handler(websocket)
                        break
            finally:
                with move_on_after(3, shield=True):
                    yield from buffered_stream.close()
        except Exception:
            logger.exception("An unexpected error occured. No response was sent")

    def _handle_request(
        self, stream: BufferedByteStream
    ) -> Coro[tuple[Request | None, Response | StreamingResponse | None]]:
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

        handler, path_params = self.router.resolve(request.method, request.path)
        handler = self._ensure_async_handler(handler)
        handler = self._apply_middleware(handler)
        request.path_params = path_params
        response = yield from handler(request)

        return request, response

    def _handle_response(
        self,
        stream: BufferedByteStream,
        request: Request,
        response: Response | StreamingResponse,
    ) -> Coro[None]:
        if isinstance(response, StreamingResponse):
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(response.producer)
                while True:
                    try:
                        chunk = yield from response.serialize()
                    except EndOfStreamError:
                        break
                    yield from stream.send(chunk)
            finally:
                yield from tg.exit()

        else:
            exclude_body = request.method == "HEAD"
            yield from stream.send(response.serialize(exclude_body))

    def _apply_middleware(self, handler: AsyncHTTPHandler) -> AsyncHTTPHandler:
        """Gets handler from router and applies all middleware.

        TODO: don't apply middleware on each request...
        """
        for middleware in self.middleware:
            handler = middleware(handler)

        return handler

    def _ensure_async_handler(self, handler: HTTPHandler) -> AsyncHTTPHandler:
        """Ensures a handler is async by wrapping it in thread pool if not."""
        if self._is_async_handler(handler):
            return handler

        sync_handler = handler  # For propery type narrowing in closure.

        def threaded_handler(request: Request) -> Coro[Response]:
            response = yield from run_in_thread(sync_handler, request)
            return response

        return threaded_handler

    def _is_async_handler(self, handler: HTTPHandler) -> TypeIs[AsyncHTTPHandler]:
        """TypeIs wrapper for proper type narrowing of HTTP handler types."""
        return inspect.isgeneratorfunction(handler)
