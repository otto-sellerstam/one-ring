from typing import TYPE_CHECKING

import pytest

from one_ring_loop import TaskGroup, run
from one_ring_loop.log import get_logger
from one_ring_loop.socketio import connect, create_server
from one_ring_loop.streams.tls import TLSStream
from one_ring_loop.sync_primitives import Event
from one_ring_loop.task import CancelScope

if TYPE_CHECKING:
    import ssl

    from one_ring_loop.typedefs import Coro


logger = get_logger(__name__)


class TestTLSStream:
    @pytest.mark.io
    def test_tls_stream(  # noqa: PLR0915
        self, ssl_contexts: tuple[ssl.SSLContext, ssl.SSLContext], unused_tcp_port: int
    ) -> None:
        def run_server() -> Coro[None]:
            server = yield from create_server(ip, port)
            try:
                event.set()
                server_conn = yield from server.accept()
                try:
                    logger.info("Setting up TLS stream", side="server")
                    sever_tls_conn = yield from TLSStream.wrap(
                        transport_stream=server_conn,
                        ssl_context=server_ctx,
                        server_side=True,
                    )
                except BaseException:
                    with CancelScope(shielded=True):
                        yield from server_conn.close()
                    raise

                try:
                    logger.info("Sending message", side="server")
                    yield from sever_tls_conn.send(b"Hello!")
                finally:
                    with CancelScope(shielded=True):
                        yield from sever_tls_conn.close()
            finally:
                with CancelScope(shielded=True):
                    yield from server.close()

        ip = "127.0.0.1"
        port = unused_tcp_port
        server_ctx, client_ctx = ssl_contexts
        event = Event()

        def enter() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(run_server())

                yield from event.wait()
                client_conn = yield from connect(ip, port)
                try:
                    logger.info("Setting up TLS stream", side="client")
                    client_tls_conn = yield from TLSStream.wrap(
                        transport_stream=client_conn,
                        ssl_context=client_ctx,
                        server_side=False,
                        hostname=ip,
                    )
                except BaseException:
                    with CancelScope(shielded=True):
                        yield from client_conn.close()
                    raise

                try:
                    logger.info("Receiving message", side="client")
                    response = yield from client_tls_conn.receive(6)
                    assert response == b"Hello!"
                finally:
                    with CancelScope(shielded=True):
                        yield from client_tls_conn.close()

                yield from tg.wait()
            finally:
                yield from tg.exit()

        run(enter())
