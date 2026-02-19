from __future__ import annotations

from typing import TYPE_CHECKING

from one_ring_core.log import get_logger
from one_ring_loop.loop import run
from one_ring_loop.socketio import Server, connect, create_server
from one_ring_loop.task import TaskGroup
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro

logger = get_logger(__name__)

server_message = b"A new client connected!"


def _run_server(socket: Server) -> Coro:
    connection = yield from socket.accept()
    logger.info("A client connected!")

    yield from connection.send(server_message)

    logger.info("All clients disconnected")


def entry() -> Coro:
    ip = b"127.0.0.1"
    port = 9999

    # Create server socket.
    server_socket = yield from create_server(ip, port)

    tg = TaskGroup()
    tg.enter()

    try:
        try:
            tg.create_task(_run_server(server_socket))

            # Wait a little bit.
            yield from sleep(1)

            client_socket = yield from connect(ip, port)

            try:
                content = yield from client_socket.recv(1024)
            finally:
                yield from client_socket.close()

            yield from tg.wait()
            assert content == server_message
        finally:
            yield from tg.exit()
    finally:
        yield from server_socket.close()


def test_socketio() -> None:
    run(entry())
