from typing import TYPE_CHECKING

import pytest

from one_ring_loop.log import get_logger
from one_ring_loop.socketio import connect, create_server
from one_ring_loop.sync_primitives import Event
from one_ring_loop.task import TaskGroup

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro

logger = get_logger(__name__)

SERVER_MESSAGE = b"A new client connected!"


class TestSocketIO:
    @pytest.mark.io
    def test_server_sends_to_client(self, run_coro, unused_tcp_port: int) -> None:
        def _run_server(ip: bytes, port: int, event: Event) -> Coro:
            server_socket = yield from create_server(ip, port)
            try:
                event.set()
                connection = yield from server_socket.accept()
                logger.info("A client connected!")
                yield from connection.send(SERVER_MESSAGE)
                logger.info("All clients disconnected")
            finally:
                yield from server_socket.close()

        def entry() -> Coro:
            ip = b"127.0.0.1"
            port = unused_tcp_port
            event = Event()
            tg = TaskGroup()
            tg.enter()
            try:
                tg.create_task(_run_server(ip, port, event))
                yield from event.wait()
                client_socket = yield from connect(ip, port)
                try:
                    content = yield from client_socket.recv(1024)
                finally:
                    yield from client_socket.close()
                yield from tg.wait()
                assert content == SERVER_MESSAGE, (
                    f"Expected {SERVER_MESSAGE!r}, got {content!r}"
                )
            finally:
                yield from tg.exit()

        run_coro(entry())
