from __future__ import annotations

from dataclasses import dataclass, field
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET
from typing import TYPE_CHECKING, Any, Self

from liburing import (  # Automatically set to typing.Any by config.
    io_uring,
    io_uring_cqe,
    io_uring_cqe_seen,
    io_uring_get_sqe,
    io_uring_peek_cqe,
    io_uring_prep_accept,
    io_uring_prep_bind,
    io_uring_prep_cancel64,
    io_uring_prep_close,
    io_uring_prep_connect,
    io_uring_prep_listen,
    io_uring_prep_nop,
    io_uring_prep_openat,
    io_uring_prep_read,
    io_uring_prep_recv,
    io_uring_prep_send,
    io_uring_prep_setsockopt,
    io_uring_prep_socket,
    io_uring_prep_timeout,
    io_uring_prep_write,
    io_uring_queue_exit,
    io_uring_queue_init,
    io_uring_sqe_set_data64,
    io_uring_submit,
    io_uring_wait_cqe,
)

from one_ring_core.log import get_logger

if TYPE_CHECKING:
    import array
    from types import TracebackType

    from one_ring_core.file import IOVec, MutableIOVec
    from one_ring_core.socket import SocketAddress
    from one_ring_core.typedefs import WorkerOperationID

logger = get_logger(__name__)


class SubmissionQueueEntry:
    """Wrapper around liburing's SQE."""

    def __init__(self, sqe: Any, user_data: WorkerOperationID) -> None:  # noqa: ANN401
        self._sqe = sqe
        self.user_data: WorkerOperationID = user_data
        io_uring_sqe_set_data64(self._sqe, user_data)

    def prep_cancel(self, target_user_data: WorkerOperationID, flags: int = 0) -> None:
        io_uring_prep_cancel64(self._sqe, target_user_data, flags)

    def prep_openat(self, path: bytes, flags: int, mode: int, dir_fd: int) -> None:
        """Preps SQE for opening file.

        Args:
            path: the path to the file to open
            flags: io_uring specific flags
            mode: to update
            dir_fd: if relative to another directory
        """
        io_uring_prep_openat(self._sqe, path, flags, mode, dir_fd)

    def prep_read(self, fd: int, iov: MutableIOVec, offset: int) -> None:
        """Preps SQE for reading from file.

        Args:
            fd: file descriptor for file to read
            iov: mutable vector buffer for io_uring to fill with content
            offset: reading offset
        """
        io_uring_prep_read(self._sqe, fd, iov.iov_base, iov.iov_len, offset)

    def prep_write(self, fd: int, iov: IOVec, offset: int) -> None:
        """Preps SQE for writing to file.

        Args:
            fd: file descriptor for file to write to
            iov: vector buffer containing content to write
            offset: writing offset
        """
        io_uring_prep_write(self._sqe, fd, iov.iov_base, iov.iov_len, offset)

    def prep_close(self, fd: int) -> None:
        """Preps SQE for closing file.

        Args:
            fd: file descriptor for file to close
        """
        io_uring_prep_close(self._sqe, fd)

    def prep_timeout(self, ts: Any, count: int = 0, flags: int = 0) -> None:  # noqa: ANN401
        """Prepares SQE for timeout (used for async sleep).

        Args:
            ts: io_uring timespec
            count: timeout fires after "count" number of CQEs
            flags: modifier flags
        """
        io_uring_prep_timeout(self._sqe, ts, count, flags)

    def prep_nop(self) -> None:
        """Prepares a nop."""
        io_uring_prep_nop(self._sqe)

    def prep_socket(
        self,
        domain: int = AF_INET,
        sock_type: int = SOCK_STREAM,
        protocol: int = 0,
        flags: int = 0,
    ) -> None:
        """Prepares a socket. Wants to return a file descriptor.

        Args:
            domain: address family (AF_INET=IPv4, AF_INET6=IPv6, AF_UNIX=unix socket)
            sock_type: transport protocol (SOCK_STREAM=TCP, SOCK_DGRAM=UDP)
            protocol: further protocol specifications (0=obvious one)
            flags: extra socket flags
        """
        io_uring_prep_socket(self._sqe, domain, sock_type, protocol, flags)

    def prep_setsocketopt(
        self,
        fd: int,
        val: array.array,
        level: int = SOL_SOCKET,
        optname: int = SO_REUSEADDR,
    ) -> None:
        """Configures socket options.

        Args:
            fd: socket file descriptor
            level: which protocol layer the option belongs to
            optname: which option
            val: option value array
        """
        io_uring_prep_setsockopt(self._sqe, fd, level, optname, val)

    def prep_socket_bind(
        self,
        fd: int,
        addr: SocketAddress,
    ) -> None:
        """Assign address and port to the socket.

        Args:
            fd: socket file descriptor
            addr: the socket address
        """
        io_uring_prep_bind(self._sqe, fd, addr.get_sockaddr())

    def prep_socket_listen(
        self,
        fd: int,
        backlog: int = 128,
    ) -> None:
        """Markes socket as passive.

        Args:
            fd: socket file descriptor
            backlog: maximum number of connections the kernel will queue before accept
        """
        io_uring_prep_listen(self._sqe, fd, backlog)

    def prep_socket_accept(
        self, fd: int, addr: SocketAddress | None = None, flags: int = 0
    ) -> None:
        """Waits for a client to accept.

        Args:
            fd: socket file descriptor
            addr: a the socket address to fill with the client's address info (their IP
                and port)
            flags: extra socket flags
        """
        _addr = addr.get_sockaddr() if addr is not None else None
        io_uring_prep_accept(self._sqe, fd, _addr, flags)

    def prep_socket_recv(self, fd: int, buf: bytearray, flags: int = 0) -> None:
        """Reads data from a connected socket.

        Args:
            fd: socket file descriptor
            buf: a buffer to receive data into
            size: how many bytes to read at most
            flags: extra flags
        """
        io_uring_prep_recv(self._sqe, fd, buf, len(buf), flags)

    def prep_socket_send(self, fd: int, buf: bytes | bytearray, flags: int = 0) -> None:
        """Writes data to a connected socket.

        Args:
            fd: socket file descriptor
            buf: data to send
            size: how many bytes to send
            flags: extra flags
        """
        io_uring_prep_send(self._sqe, fd, buf, len(buf), flags)

    def prep_connect(self, fd: int, addr: SocketAddress) -> None:
        """Prepares to connect to a socket.

        Args:
            fd: the file descriptor of the socket
            addr: the address of the socket
        """
        io_uring_prep_connect(self._sqe, fd, addr.get_sockaddr())


@dataclass
class CompletionEvent:
    """Wrapper around CQEs emitted by the ring."""

    user_data: WorkerOperationID
    res: int
    flags: int


@dataclass
class Ring:
    """Utility wrappeer of ring buffer."""

    depth: int = field(default=32)
    _cqe: Any = field(default=io_uring_cqe(), init=False)
    _ring: Any = field(default=io_uring(), init=False)
    _cqe_ready: bool = field(default=False, init=False)

    def __enter__(self) -> Self:
        """Initialises submission ring buffer."""
        io_uring_queue_init(self.depth, self._ring, 0)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Exits submission ring buffer."""
        io_uring_queue_exit(self._ring)

    def submit(self) -> int:
        """Submits the SQ to the kernel.

        Returns:
            Numbers of SQE events submitted
        """
        # This should check that all new registrations where actually submitted
        return io_uring_submit(self._ring)

    def peek(self) -> CompletionEvent | None:
        """Docstring."""
        if io_uring_peek_cqe(self._ring, self._cqe) == 0:
            self._mark_cqe_ready()
            return self._consume_cqe()
        return None

    def wait(self) -> CompletionEvent:
        """Docstring."""
        io_uring_wait_cqe(self._ring, self._cqe)
        self._mark_cqe_ready()
        return self._consume_cqe()

    def get_sqe(self, user_data: int) -> SubmissionQueueEntry:
        """Returns a SQE from the SQ, with set user_data."""
        if not user_data:
            raise ValueError("user_data cannot be 0")

        sqe = io_uring_get_sqe(self._ring)
        return SubmissionQueueEntry(
            sqe,
            user_data,
        )

    def _mark_cqe_ready(self) -> None:
        """Marks a consumer completion event as ready."""
        self._cqe_ready = True

    def _mark_cqe_seen(self) -> None:
        """Marks a consumer completion event as seen."""
        io_uring_cqe_seen(self._ring, self._cqe)
        self._cqe_ready = False

    def _consume_cqe(self) -> CompletionEvent:
        """Consumes a CQE.

        Returns:
            CompletionEvent
        """
        if not self._cqe_ready:
            raise RuntimeError("No completion event ready")
        try:
            event = CompletionEvent(
                user_data=self._cqe.user_data,
                res=self._cqe.res,
                flags=self._cqe.flags,
            )
        finally:
            self._mark_cqe_seen()
        return event
