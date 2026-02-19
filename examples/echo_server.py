"""This example shows a simple echo server."""

from typing import TYPE_CHECKING

from one_ring_loop import TaskGroup, run
from one_ring_loop.socketio import Connection, create_server

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def echo_handler(conn: Connection) -> Coro[None]:
    """Gets data sent from a client and echoes it."""
    try:
        while True:
            data = yield from conn.recv(1024)
            if not data:
                break
            yield from conn.send(b"Server echoes: " + data)
    finally:
        yield from conn.close()


def echo_server() -> Coro[None]:
    """Echo server entrypoint."""
    server = yield from create_server(b"0.0.0.0", 9999)
    tg = TaskGroup()
    tg.enter()
    try:
        try:
            while True:
                conn = yield from server.accept()
                tg.create_task(echo_handler(conn))
        finally:
            yield from server.close()
    finally:
        yield from tg.exit()


if __name__ == "__main__":
    run(echo_server())
