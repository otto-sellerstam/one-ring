"""This example shows a simple echo server."""

from typing import TYPE_CHECKING

from one_ring_loop.loop import create_task, run
from one_ring_loop.socketio import Connection, create_server

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def echo_handler(conn: Connection) -> Coro[None]:
    """Gets data sent from a client and echoes it."""
    try:
        while True:
            data = yield from conn.recv(1024)
            data = b"Server says: " + data
            if not data:
                break
            yield from conn.send(data)
    finally:
        yield from conn.close()


def echo_server() -> Coro[None]:
    """Echo server entrypoint."""
    server = yield from create_server(b"0.0.0.0", 9999)
    try:
        while True:
            conn = yield from server.accept()
            create_task(echo_handler(conn))
    finally:
        yield from server.close()


if __name__ == "__main__":
    run(echo_server())
