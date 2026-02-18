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
from one_ring_core.results import (
    CloseResult,
    SocketAcceptResult,
    SocketBindResult,
    SocketConnectResult,
    SocketCreateResult,
    SocketListenResult,
    SocketRecvResult,
    SocketSendResult,
    SocketSetOptResult,
)

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro

# TODO: Clean up
# Better names
# Centralize "close" together file fileio


def _create() -> Coro[int]:
    create_completion = yield SocketCreate()
    if create_completion is not None and isinstance(
        result := create_completion.unwrap(), SocketCreateResult
    ):
        return result.fd

    raise ValueError("_create received wrong type")


def _set_options(fd: int) -> Coro[None]:
    set_opt_completion = yield SocketSetOpt(fd)
    if set_opt_completion is not None and isinstance(
        set_opt_completion.unwrap(), SocketSetOptResult
    ):
        return None

    raise ValueError("_set_options received wrong type")


def _bind(fd: int, host: bytes, port: int) -> Coro[None]:
    bind_completion = yield SocketBind(fd, host, port)
    if bind_completion is not None and isinstance(
        bind_completion.unwrap(), SocketBindResult
    ):
        return None

    raise ValueError("_bind received wrong type")


def _listen(fd: int) -> Coro[None]:
    listen_completion = yield SocketListen(fd)
    if listen_completion is not None and isinstance(
        listen_completion.unwrap(), SocketListenResult
    ):
        return None

    raise ValueError("_listen received wrong type")


def _connect(fd: int, host: bytes, port: int) -> Coro[None]:
    bind_completion = yield SocketConnect(fd, host, port)
    if bind_completion is not None and isinstance(
        bind_completion.unwrap(), SocketConnectResult
    ):
        return None

    raise ValueError("_connect received wrong type")


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
    """User by server to accept new connections."""

    """The socket's file descriptor"""
    fd: int

    def accept(self) -> Coro[Connection]:
        """Waits until there's a connection to accept.

        Returns:
            client file descriptor
        """
        accept_completion = yield SocketAccept(self.fd)
        if accept_completion is not None and isinstance(
            result := accept_completion.unwrap(), SocketAcceptResult
        ):
            return Connection(result.fd)

        raise ValueError("accept received wrong type")

    def close(self) -> Coro[None]:
        """Close socket."""
        close_completion = yield Close(self.fd)
        if close_completion is not None and isinstance(
            close_completion.unwrap(), CloseResult
        ):
            return None

        raise ValueError("close_file received wrong result type")


@dataclass
class Connection:
    """Corresponds a socket connection. Either from server, or client."""

    """Either server file descriptor, or client file descriptor."""
    fd: int

    def recv(self, size: int) -> Coro[bytes]:
        """Reads data from socket."""
        recv_completion = yield SocketRecv(self.fd, size)
        if recv_completion is not None and isinstance(
            result := recv_completion.unwrap(), SocketRecvResult
        ):
            return result.content

        raise ValueError("recv received wrong type")

    def send(self, data: bytes) -> Coro[int]:
        """Reads data from socket."""
        send_completion = yield SocketSend(self.fd, data)
        if send_completion is not None and isinstance(
            result := send_completion.unwrap(), SocketSendResult
        ):
            return result.size

        raise ValueError("send received wrong type")

    def close(self) -> Coro[None]:
        """Close socket."""
        close_completion = yield Close(self.fd)
        if close_completion is not None and isinstance(
            close_completion.unwrap(), CloseResult
        ):
            return None

        raise ValueError("close_file received wrong result type")
