"""Docstring."""

from __future__ import annotations

import array
import errno
import os
import socket
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, override

from one_ring_core.log import get_logger
from one_ring_core.results import (
    CancelResult,
    CloseResult,
    FileOpenResult,
    FileReadResult,
    FileWriteResult,
    SleepResult,
    SocketAcceptResult,
    SocketBindResult,
    SocketConnectResult,
    SocketCreateResult,
    SocketListenResult,
    SocketRecvResult,
    SocketSendResult,
    SocketSetOptResult,
)
from one_ring_core.socket import AddressFamily
from rusty_ring import SockAddr

if TYPE_CHECKING:
    from one_ring_core.results import IOResult
    from one_ring_core.typedefs import WorkerOperationID
    from rusty_ring import CompletionEvent, Ring


logger = get_logger(__name__)


class IOOperation[T: IOResult](metaclass=ABCMeta):
    """Base class for all IO operations."""

    __slots__ = ()

    result_type: type[T]

    @abstractmethod
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Prepares a submission queue entry for the SQ."""

    @abstractmethod
    def extract(self, completion_event: CompletionEvent) -> T:
        """Extract fields from a completion queue event and wrap in correct type."""

    def is_error(self, completion_event: CompletionEvent) -> bool:
        """Determines if the completion event is an error."""
        return completion_event.res < 0


@dataclass(slots=True, kw_only=True)
class Cancel(IOOperation[CancelResult]):
    """Cancels an in-flight operation."""

    result_type = CancelResult

    """The id of the operation to cancel the in-flight operation for"""
    target_identifier: WorkerOperationID

    """Flags for cancellation"""
    flags: int = 0

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Prepares a submission queue entry for the SQ."""
        ring.prep_cancel(user_data, self.target_identifier, self.flags)

    @override
    def extract(self, completion_event: CompletionEvent) -> CancelResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return CancelResult()

    @override
    def is_error(self, completion_event: CompletionEvent) -> bool:
        """Determines if the completion event is an error."""
        return completion_event.res < 0 and completion_event.res not in {
            -errno.ENOENT,  # identifier not found
            -errno.EALREADY,  # identifier already completing
        }


@dataclass(slots=True, kw_only=True)
class FileOpen(IOOperation[FileOpenResult]):
    """Docstring."""

    result_type = FileOpenResult
    path: str
    mode: str

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Prepares a submission queue entry for the SQ."""
        ring.prep_openat(
            user_data, self.path, self._mode_to_flags(self.mode), 0o660, -100
        )

    @override
    def extract(self, completion_event: CompletionEvent) -> FileOpenResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileOpenResult(
            fd=completion_event.res,
        )

    @staticmethod
    def _mode_to_flags(mode: str) -> int:
        """Docstring."""
        if "r" in mode and "w" in mode:
            flags = 2  # read write
        elif "w" in mode:
            flags = 1  # write only
        else:
            flags = 0  # read only

        if "c" in mode:
            flags |= 64  # create if not exists
        if "a" in mode:
            flags |= 1024  # append

        return flags


@dataclass(slots=True, kw_only=True)
class FileRead(IOOperation[FileReadResult]):
    """File descriptor for the regular file."""

    result_type = FileReadResult
    fd: int

    """None will read the whole file"""
    size: int | None = None

    """Offset for file read"""
    offset: int = 0

    """Buffer to be filled with contents from read operation"""
    _buffer: bytearray = field(init=False, repr=False)

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Prepares a submission queue entry for the SQ."""
        _size = self.size
        if _size is None:
            _size = os.fstat(self.fd).st_size  # Blocking syscall.
        self._buffer = bytearray(_size)

        ring.prep_read(user_data, self.fd, self._buffer, _size, self.offset)

    @override
    def extract(self, completion_event: CompletionEvent) -> FileReadResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileReadResult(
            content=bytes(self._buffer),
            size=completion_event.res,
        )


@dataclass(slots=True, kw_only=True)
class FileWrite(IOOperation[FileWriteResult]):
    """File descriptor for the regular file."""

    result_type = FileWriteResult
    fd: int

    """Data to write to file"""
    data: bytes

    """Not sure"""
    offset: int = 0

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Prepares a submission queue entry for the SQ."""
        ring.prep_write(user_data, self.fd, self.data, self.offset)

    @override
    def extract(self, completion_event: CompletionEvent) -> FileWriteResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileWriteResult(
            size=completion_event.res,
        )


@dataclass(slots=True, kw_only=True)
class Close(IOOperation[CloseResult]):
    """File descriptor for the regular file."""

    result_type = CloseResult
    fd: int

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Prepares a submission queue entry for the SQ."""
        ring.prep_close(user_data, self.fd)

    @override
    def extract(self, completion_event: CompletionEvent) -> CloseResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return CloseResult()


@dataclass(slots=True, kw_only=True)
class Sleep(IOOperation[SleepResult]):
    """File descriptor for the regular file."""

    result_type = SleepResult
    time: float
    _timespec: Any = field(init=False, repr=False)

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Prepares a submission queue entry for the SQ."""
        sec = int(self.time)
        nsec = int((self.time - sec) * 1_000_000_000)
        ring.prep_timeout(user_data, sec, nsec)

    @override
    def extract(self, completion_event: CompletionEvent) -> SleepResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return SleepResult()

    @override
    def is_error(self, completion_event: CompletionEvent) -> bool:
        """Override since timeout returns -ETIME on success."""
        return completion_event.res != -errno.ETIME


@dataclass(slots=True, kw_only=True)
class SocketCreate(IOOperation[SocketCreateResult]):
    """Prepares a socket."""

    result_type = SocketCreateResult
    """address family (AF_INET=IPv4, AF_INET6=IPv6, AF_UNIX=unix socket)"""
    domain: int = AddressFamily.AF_INET

    """ransport protocol (SOCK_STREAM=TCP, SOCK_DGRAM=UDP)"""
    sock_type: int = socket.SOCK_STREAM

    """further protocol specifications (0=obvious one chosen by kernel)"""
    protocol: int = 0

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Docstring."""
        ring.prep_socket(user_data, self.domain, self.sock_type, self.protocol)

    @override
    def extract(self, completion_event: CompletionEvent) -> SocketCreateResult:
        """Docstring."""
        return SocketCreateResult(fd=completion_event.res)


@dataclass(slots=True, kw_only=True)
class SocketSetOpt(IOOperation[SocketSetOptResult]):
    """Configures options for a socket."""

    result_type = SocketSetOptResult
    """The file descriptor of the socket"""
    fd: int

    """Docstring"""
    level: int = socket.SOL_SOCKET

    """Docstring"""
    optname: int = socket.SO_REUSEADDR

    """Docstring"""
    val: array.array = field(default_factory=lambda: array.array("i", [1]))

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        ring.prep_socket_setopt(user_data, self.fd)

    @override
    def extract(self, completion_event: CompletionEvent) -> SocketSetOptResult:
        """Docstring."""
        return SocketSetOptResult()


@dataclass(slots=True, kw_only=True)
class SocketBind(IOOperation[SocketBindResult]):
    """Assign address and port to a socket."""

    result_type = SocketBindResult
    """The file descriptor of the socket"""
    fd: int

    """The IP to assign"""
    ip: str

    """The port to assign"""
    port: int

    _sockaddr: SockAddr = field(init=False)

    """Address family"""
    address_family: AddressFamily = AddressFamily.AF_INET

    def __post_init__(self) -> None:
        """Initializes socket address attribute."""
        if self.address_family == AddressFamily.AF_INET:
            self._sockaddr = SockAddr.v4(ip=self.ip, port=self.port)
        else:
            self._sockaddr = SockAddr.v6(ip=self.ip, port=self.port)

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        ring.prep_socket_bind(user_data, self.fd, self._sockaddr)

    @override
    def extract(self, completion_event: CompletionEvent) -> SocketBindResult:
        """Docstring."""
        return SocketBindResult()


@dataclass(slots=True, kw_only=True)
class SocketListen(IOOperation[SocketListenResult]):
    """Marks a socket as passive."""

    result_type = SocketListenResult
    """The file descriptor of the socket"""
    fd: int

    """maximum number of connections the kernel will queue before accept"""
    backlog: int = 128

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        ring.prep_socket_listen(user_data, self.fd, self.backlog)

    @override
    def extract(self, completion_event: CompletionEvent) -> SocketListenResult:
        """Docstring."""
        return SocketListenResult()


@dataclass(slots=True, kw_only=True)
class SocketAccept(IOOperation[SocketAcceptResult]):
    """Accepts a connection on a socket."""

    result_type = SocketAcceptResult
    """The file descriptor of the socket"""
    fd: int

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Docstring."""
        ring.prep_socket_accept(user_data, self.fd)

    @override
    def extract(self, completion_event: CompletionEvent) -> SocketAcceptResult:
        """Docstring."""
        return SocketAcceptResult(fd=completion_event.res)


@dataclass(slots=True, kw_only=True)
class SocketRecv(IOOperation[SocketRecvResult]):
    """Reads from a socket."""

    result_type = SocketRecvResult
    """The socket file descriptor to read from"""
    fd: int

    """The length of the read content"""
    size: int

    """Buffer to be filled with contents from read operation"""
    _buffer: bytearray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initializes buffer."""
        self._buffer = bytearray(self.size)

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Docstring."""
        ring.prep_socket_recv(user_data, self.fd, self._buffer)

    @override
    def extract(self, completion_event: CompletionEvent) -> SocketRecvResult:
        """Docstring."""
        return SocketRecvResult(
            content=bytes(self._buffer[: completion_event.res]),
            size=completion_event.res,
        )


@dataclass(slots=True, kw_only=True)
class SocketSend(IOOperation[SocketSendResult]):
    """Sends data to a socket."""

    result_type = SocketSendResult
    """The file descriptor of the socket to send data to."""
    fd: int

    """The data to send."""
    data: bytes

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Docstring."""
        ring.prep_socket_send(user_data, self.fd, self.data)

    @override
    def extract(self, completion_event: CompletionEvent) -> SocketSendResult:
        """Docstring."""
        return SocketSendResult(size=completion_event.res)


@dataclass(slots=True, kw_only=True)
class SocketConnect(IOOperation[SocketConnectResult]):
    """Connects to a socket."""

    result_type = SocketConnectResult
    """The file descriptor of the socket to send data to."""
    fd: int

    """The IP to connect to"""
    ip: str

    """The port to connect to"""
    port: int

    """The address family"""
    address_family: AddressFamily = AddressFamily.AF_INET

    _sockaddr: SockAddr = field(init=False)

    def __post_init__(self) -> None:
        """Initializes socket address attribute."""
        if self.address_family == AddressFamily.AF_INET:
            self._sockaddr = SockAddr.v4(ip=self.ip, port=self.port)
        else:
            self._sockaddr = SockAddr.v6(ip=self.ip, port=self.port)

    @override
    def prep(self, user_data: WorkerOperationID, ring: Ring) -> None:
        """Docstring."""
        ring.prep_socket_connect(user_data, self.fd, self._sockaddr)

    @override
    def extract(self, completion_event: CompletionEvent) -> SocketConnectResult:
        """Docstring."""
        return SocketConnectResult()
