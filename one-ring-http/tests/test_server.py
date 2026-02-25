"""Integration tests for HTTPServer with full TLS roundtrip."""

from contextlib import suppress
from typing import TYPE_CHECKING

import pytest

from one_ring_http.response import HTTPStatus, Response
from one_ring_http.router import Router
from one_ring_http.server import HTTPServer
from one_ring_loop import TaskGroup, run
from one_ring_loop.cancellation import move_on_after
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.socketio import connect
from one_ring_loop.streams.buffered import BufferedByteStream
from one_ring_loop.streams.tls import TLSStream
from one_ring_loop.timerio import sleep

from .conftest import parse_raw_response

if TYPE_CHECKING:
    import ssl

    from one_ring_http.request import Request
    from one_ring_loop.typedefs import Coro

from .conftest import RawHTTPResponse


def _serve_until_cancelled(
    router: Router, port: int, server_ctx: ssl.SSLContext
) -> Coro[None]:
    """Start the server, swallowing Cancelled on shutdown."""
    server = HTTPServer(
        router=router, host="127.0.0.1", port=port, ssl_context=server_ctx
    )
    with suppress(Cancelled):
        yield from server.serve()


def _client_exchange(
    port: int, client_ctx: ssl.SSLContext, raw_request: bytes
) -> Coro[RawHTTPResponse]:
    """Connect to server, send request, return parsed response."""
    conn = yield from connect(b"127.0.0.1", port)
    try:
        tls_conn = yield from TLSStream.wrap(
            conn, ssl_context=client_ctx, server_side=False, hostname=b"127.0.0.1"
        )
    except BaseException:
        with move_on_after(3, shield=True):
            yield from conn.close()
        raise

    buffered = BufferedByteStream(receive_stream=tls_conn, send_stream=tls_conn)
    try:
        yield from buffered.send(raw_request)
        resp = yield from parse_raw_response(buffered)
    finally:
        with move_on_after(3, shield=True):
            yield from buffered.close()
    return resp


class TestHTTPServer:
    @pytest.mark.io
    def test_get_returns_200(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
    ) -> None:
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        router = Router()
        router.add(
            "GET", "/hello", lambda req: Response(status_code=HTTPStatus.OK, body=b"Hi")
        )

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_until_cancelled(router, port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_exchange(
                    port, client_ctx, b"GET /hello HTTP/1.1\r\nhost: localhost\r\n\r\n"
                )
                assert resp.status_code == 200
                assert resp.body == b"Hi"
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_async_generator_handler(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
    ) -> None:
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        def async_handler(req: Request) -> Coro[Response]:
            yield from sleep(0)
            return Response(status_code=HTTPStatus.OK, body=b"async")

        router = Router()
        router.add("GET", "/async", async_handler)

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_until_cancelled(router, port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_exchange(
                    port, client_ctx, b"GET /async HTTP/1.1\r\nhost: localhost\r\n\r\n"
                )
                assert resp.status_code == 200
                assert resp.body == b"async"
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_post_with_body(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
    ) -> None:
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        captured: dict[str, bytes] = {}

        def echo_handler(req: Request) -> Response:
            captured["body"] = req.body
            return Response(status_code=HTTPStatus.OK, body=req.body)

        router = Router()
        router.add("POST", "/echo", echo_handler)

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_until_cancelled(router, port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_exchange(
                    port,
                    client_ctx,
                    b"POST /echo HTTP/1.1\r\n"
                    b"host: localhost\r\n"
                    b"content-length: 11\r\n"
                    b"\r\n"
                    b"hello world",
                )
                assert resp.status_code == 200
                assert resp.body == b"hello world"
                assert captured["body"] == b"hello world"
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_unregistered_route_returns_404(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
    ) -> None:
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        router = Router()

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_until_cancelled(router, port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_exchange(
                    port,
                    client_ctx,
                    b"GET /missing HTTP/1.1\r\nhost: localhost\r\n\r\n",
                )
                assert resp.status_code == 404
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_custom_fallback(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
    ) -> None:
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        router = Router()
        router.set_fallback(
            lambda req: Response(status_code=HTTPStatus.TEAPOT, body=b"teapot")
        )

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_until_cancelled(router, port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_exchange(
                    port,
                    client_ctx,
                    b"GET /anything HTTP/1.1\r\nhost: localhost\r\n\r\n",
                )
                assert resp.status_code == 418
                assert resp.body == b"teapot"
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_multiple_sequential_connections(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
    ) -> None:
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        counter = {"n": 0}

        def counting_handler(req: Request) -> Response:
            counter["n"] += 1
            return Response(status_code=HTTPStatus.OK, body=str(counter["n"]).encode())

        router = Router()
        router.add("GET", "/count", counting_handler)

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_until_cancelled(router, port, server_ctx))
                yield from sleep(0.1)

                for expected in (b"1", b"2", b"3"):
                    resp = yield from _client_exchange(
                        port,
                        client_ctx,
                        b"GET /count HTTP/1.1\r\nhost: localhost\r\n\r\n",
                    )
                    assert resp.status_code == 200
                    assert resp.body == expected
            finally:
                yield from tg.exit()

        run(entry())
