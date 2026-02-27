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
from one_ring_loop.streams.exceptions import EndOfStreamError

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro

# TODO: Clean up
# Better names
# Centralize "close" together with fileio


def _create() -> Coro[int]:
    result = yield from _execute(SocketCreate())
    return result.fd


def _set_options(fd: int) -> Coro[None]:
    yield from _execute(SocketSetOpt(fd=fd))
    return None


def _bind(fd: int, host: str, port: int) -> Coro[None]:
    yield from _execute(SocketBind(fd=fd, ip=host, port=port))
    return None


def _listen(fd: int) -> Coro[None]:
    yield from _execute(SocketListen(fd=fd))
    return None


def _connect(fd: int, host: str, port: int) -> Coro[None]:
    yield from _execute(SocketConnect(fd=fd, ip=host, port=port))
    return None


def create_server(host: str, port: int) -> Coro[Server]:
    """Creates a socket (server), sets options, binds it and wraps in SocketListener."""
    fd = yield from _create()
    yield from _set_options(fd)
    yield from _bind(fd, host, port)
    yield from _listen(fd)
    return Server(fd=fd)


def connect(host: str, port: int) -> Coro[Connection]:
    """Connects to a listening socket."""
    fd = yield from _create()
    yield from _connect(fd, host, port)

    return Connection(fd=fd)


@dataclass(slots=True, kw_only=True)
class Server:
    """Used to accept new connections."""

    """The socket's file descriptor"""
    fd: int

    def accept(self) -> Coro[Connection]:
        """Waits until there's a connection to accept.

        Returns:
            client file descriptor
        """
        result = yield from _execute(SocketAccept(fd=self.fd))
        return Connection(fd=result.fd)

    def close(self) -> Coro[None]:
        """Close socket."""
        yield from _execute(Close(fd=self.fd))
        return None


@dataclass(slots=True, kw_only=True)
class Connection:
    """Corresponds a socket connection. Either from server, or client."""

    """Either server file descriptor, or client file descriptor."""
    fd: int

    def receive(self, max_bytes: int = 65536) -> Coro[bytes]:
        """Reads data from socket."""
        result = yield from _execute(SocketRecv(fd=self.fd, size=max_bytes))
        if not result.content:
            raise EndOfStreamError
        return result.content

    def send(self, data: bytes, /) -> Coro[None]:
        """Sends data to socket."""
        yield from _execute(SocketSend(fd=self.fd, data=data))

    def close(self) -> Coro[None]:
        """Close socket."""
        yield from _execute(Close(fd=self.fd))
        return None
