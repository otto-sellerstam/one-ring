from dataclasses import dataclass
from typing import TYPE_CHECKING

from one_ring_core.operations import (
    Close,
    SocketAccept,
    SocketBind,
    SocketConnect,
    SocketCreate,
    SocketListen,
    SocketRecv,
    SocketSend,
    SocketSetOpt,
)
from one_ring_loop._utils import _execute

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro

# TODO: Clean up
# Better names
# Centralize "close" together with fileio


def _create() -> Coro[int]:
    result = yield from _execute(SocketCreate())
    return result.fd


def _set_options(fd: int) -> Coro[None]:
    yield from _execute(SocketSetOpt(fd))
    return None


def _bind(fd: int, host: bytes, port: int) -> Coro[None]:
    yield from _execute(SocketBind(fd, host, port))
    return None


def _listen(fd: int) -> Coro[None]:
    yield from _execute(SocketListen(fd))
    return None


def _connect(fd: int, host: bytes, port: int) -> Coro[None]:
    yield from _execute(SocketConnect(fd, host, port))
    return None


def create_server(host: bytes, port: int) -> Coro[Server]:
    """Creates a socket (server), sets options, binds it and wraps in SocketListener."""
    fd = yield from _create()
    yield from _set_options(fd)
    yield from _bind(fd, host, port)
    yield from _listen(fd)
    return Server(fd)


def connect(host: bytes, port: int) -> Coro[Connection]:
    """Connects to a listening socket."""
    fd = yield from _create()
    yield from _connect(fd, host, port)

    return Connection(fd)


@dataclass
class Server:
    """Used to accept new connections."""

    """The socket's file descriptor"""
    fd: int

    def accept(self) -> Coro[Connection]:
        """Waits until there's a connection to accept.

        Returns:
            client file descriptor
        """
        result = yield from _execute(SocketAccept(self.fd))
        return Connection(result.fd)

    def close(self) -> Coro[None]:
        """Close socket."""
        yield from _execute(Close(self.fd))
        return None


@dataclass
class Connection:
    """Corresponds a socket connection. Either from server, or client."""

    """Either server file descriptor, or client file descriptor."""
    fd: int

    def recv(self, size: int) -> Coro[bytes]:
        """Reads data from socket."""
        result = yield from _execute(SocketRecv(self.fd, size))
        return result.content

    def send(self, data: bytes) -> Coro[int]:
        """Sends data to socket."""
        result = yield from _execute(SocketSend(self.fd, data))
        return result.size

    def close(self) -> Coro[None]:
        """Close socket."""
        yield from _execute(Close(self.fd))
        return None
