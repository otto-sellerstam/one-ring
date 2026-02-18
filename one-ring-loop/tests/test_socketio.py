from __future__ import annotations

from typing import TYPE_CHECKING

from one_ring_core.log import get_logger
from one_ring_loop.loop import create_task, run
from one_ring_loop.socketio import Server, connect, create_server
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro

logger = get_logger(__name__)


def _run_server(socket: Server) -> Coro:
    connection = yield from socket.accept()
    logger.info("A client connected!")

    yield from connection.send(b"A new client connected!")

    logger.info("All clients disconnected")


def entry() -> Coro:
    ip = b"127.0.0.1"
    port = 9999

    # Create server socket.
    server_socket = yield from create_server(ip, port)

    try:
        # Start the server.
        create_task(_run_server(server_socket))

        # Wait a little bit.
        yield from sleep(1)

        # Start a client connection.
        client_socket = yield from connect(ip, port)

        # Receive some stuff!
        try:
            content = yield from client_socket.recv(1024)
        finally:
            yield from client_socket.close()
        logger.info("Client received message", content=content)
    finally:
        yield from server_socket.close()


def test_socketio() -> None:
    run(entry())


test_socketio()
