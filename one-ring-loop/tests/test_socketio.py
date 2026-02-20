from __future__ import annotations

from typing import TYPE_CHECKING

from one_ring_loop.log import get_logger
from one_ring_loop.loop import run
from one_ring_loop.socketio import connect, create_server
from one_ring_loop.sync_primitives import Event
from one_ring_loop.task import TaskGroup

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro

logger = get_logger(__name__)

server_message = b"A new client connected!"


def _run_server(ip: bytes, port: int, event: Event) -> Coro:
    server_socket = yield from create_server(ip, port)
    try:
        event.set()
        connection = yield from server_socket.accept()
        logger.info("A client connected!")
        yield from connection.send(server_message)
        logger.info("All clients disconnected")
    finally:
        yield from server_socket.close()


def entry() -> Coro:
    ip = b"127.0.0.1"
    port = 9999
    # Create server socket.
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
        assert content == server_message
    finally:
        yield from tg.exit()


def test_socketio() -> None:
    run(entry())


if __name__ == "__main__":
    test_socketio()
