"""Integration tests for static file serving."""

from contextlib import suppress
from typing import TYPE_CHECKING

import pytest

from one_ring_http.router import Router
from one_ring_http.server import HTTPServer
from one_ring_http.static import static_handler
from one_ring_loop import TaskGroup, run
from one_ring_loop.cancellation import move_on_after
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.socketio import connect
from one_ring_loop.streams.buffered import BufferedByteStream
from one_ring_loop.streams.tls import TLSStream
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    import ssl
    from pathlib import Path

    from one_ring_loop.typedefs import Coro

from .conftest import RawHTTPResponse, parse_raw_response


def _serve_static(root: str, port: int, server_ctx: ssl.SSLContext) -> Coro[None]:
    """Start a server with static_handler, swallowing Cancelled on shutdown."""
    router = Router()
    router.add("GET", "/*", static_handler(root))
    router.set_fallback(static_handler(root))
    server = HTTPServer(
        router=router, host="127.0.0.1", port=port, ssl_context=server_ctx
    )
    with suppress(Cancelled):
        yield from server.serve()


def _client_get(
    port: int, client_ctx: ssl.SSLContext, path: str
) -> Coro[RawHTTPResponse]:
    """Send a GET request and return parsed response."""
    conn = yield from connect("127.0.0.1", port)
    try:
        tls_conn = yield from TLSStream.wrap(
            conn, ssl_context=client_ctx, server_side=False, hostname="127.0.0.1"
        )
    except BaseException:
        with move_on_after(3, shield=True):
            yield from conn.close()
        raise

    buffered = BufferedByteStream(receive_stream=tls_conn, send_stream=tls_conn)
    try:
        yield from buffered.send(
            f"GET {path} HTTP/1.1\r\nhost: localhost\r\n\r\n".encode()
        )
        return (yield from parse_raw_response(buffered))
    finally:
        with move_on_after(3, shield=True):
            yield from buffered.close()  # pyrefly: ignore[unreachable]


class TestStaticHandler:
    @pytest.mark.io
    def test_serves_index_for_root(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "index.html").write_text("<h1>Hello</h1>")
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_static(str(tmp_path), port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_get(port, client_ctx, "/")
                assert resp.status_code == 200
                assert resp.body == b"<h1>Hello</h1>"
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_serves_specific_file(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "about.html").write_text("<h1>About</h1>")
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_static(str(tmp_path), port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_get(port, client_ctx, "/about.html")
                assert resp.status_code == 200
                assert resp.body == b"<h1>About</h1>"
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_html_extension_fallback(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "about.html").write_text("<h1>About</h1>")
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_static(str(tmp_path), port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_get(port, client_ctx, "/about")
                assert resp.status_code == 200
                assert resp.body == b"<h1>About</h1>"
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_directory_index(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
        tmp_path: Path,
    ) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.html").write_text("<h1>Docs</h1>")
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_static(str(tmp_path), port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_get(port, client_ctx, "/docs/")
                assert resp.status_code == 200
                assert resp.body == b"<h1>Docs</h1>"
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_missing_file_returns_404(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
        tmp_path: Path,
    ) -> None:
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_static(str(tmp_path), port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_get(port, client_ctx, "/nonexistent")
                assert resp.status_code == 404
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_path_traversal_blocked(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "index.html").write_text("root")
        secret = tmp_path / "secret"
        secret.mkdir()
        (secret / "data.txt").write_text("secret data")
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        # Serve only from the "secret" subdirectory, try to escape via ../
        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_static(str(secret), port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_get(port, client_ctx, "/../index.html")
                assert resp.status_code == 404
            finally:
                yield from tg.exit()

        run(entry())

    @pytest.mark.io
    def test_content_type_html(
        self,
        ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext],
        unused_tcp_port: int,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "page.html").write_text("<p>test</p>")
        server_ctx, client_ctx = ssl_contexts
        port = unused_tcp_port

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_serve_static(str(tmp_path), port, server_ctx))
                yield from sleep(0.1)

                resp = yield from _client_get(port, client_ctx, "/page.html")
                assert resp.status_code == 200
                assert resp.headers["content-type"] == "text/html"
            finally:
                yield from tg.exit()

        run(entry())
