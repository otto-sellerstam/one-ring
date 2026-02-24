"""Docstring."""

from __future__ import annotations

import array
import errno
import os
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, override

from liburing import (  # Automatically set to typing.Any by config.
    AT_FDCWD,
    O_APPEND,
    O_CREAT,
    O_RDONLY,
    O_RDWR,
    O_WRONLY,
    SO_REUSEADDR,
    SOL_SOCKET,
    SocketType,
    timespec,
)

from one_ring_core.file import IOVec, MutableIOVec
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
from one_ring_core.socket import AddressFamily, SocketAddress, SocketFamily

if TYPE_CHECKING:
    from one_ring_core._ring import CompletionEvent, SubmissionQueueEntry
    from one_ring_core.results import IOResult
    from one_ring_core.typedefs import WorkerOperationID


logger = get_logger(__name__)


class IOOperation[T: IOResult](metaclass=ABCMeta):
    """Base class for all IO operations."""

    __slots__ = ()

    result_type: type[T]

    @abstractmethod
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
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
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Prepares a submission queue entry for the SQ."""
        sqe.prep_cancel(self.target_identifier, self.flags)
        return sqe.user_data

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
    path: bytes
    mode: str

    @override
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Prepares a submission queue entry for the SQ."""
        sqe.prep_openat(self.path, self._mode_to_flags(self.mode), 0o660, AT_FDCWD)
        return sqe.user_data

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
            flags = O_RDWR
        elif "w" in mode:
            flags = O_WRONLY
        else:
            flags = O_RDONLY

        if "c" in mode:
            flags |= O_CREAT
        if "a" in mode:
            flags |= O_APPEND

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
    _vector_buffer: MutableIOVec = field(init=False, repr=False)

    @override
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Prepares a submission queue entry for the SQ."""
        _size = self.size
        if _size is None:
            _size = os.fstat(self.fd).st_size  # Blocking syscall.
        self._vector_buffer = MutableIOVec(bytearray(_size))

        sqe.prep_read(self.fd, self._vector_buffer, self.offset)
        return sqe.user_data

    @override
    def extract(self, completion_event: CompletionEvent) -> FileReadResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileReadResult(
            content=bytes(self._vector_buffer.iov_base),
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
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Prepares a submission queue entry for the SQ."""
        vector_buffer = IOVec(self.data)
        sqe.prep_write(self.fd, vector_buffer, self.offset)
        return sqe.user_data

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
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Prepares a submission queue entry for the SQ."""
        sqe.prep_close(self.fd)
        return sqe.user_data

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
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Prepares a submission queue entry for the SQ."""
        self._timespec = timespec(self.time)
        sqe.prep_timeout(self._timespec)
        return sqe.user_data

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
    domain: int = SocketFamily.AF_INET

    """ransport protocol (SOCK_STREAM=TCP, SOCK_DGRAM=UDP)"""
    sock_type: int = SocketType.SOCK_STREAM

    """further protocol specifications (0=obvious one chosen by kernel)"""
    protocol: int = 0

    @override
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Docstring."""
        sqe.prep_socket(self.domain, self.sock_type, self.protocol)
        return sqe.user_data

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
    level: int = SOL_SOCKET

    """Docstring"""
    optname: int = SO_REUSEADDR

    """Docstring"""
    val: array.array = field(default_factory=lambda: array.array("i", [1]))

    @override
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        sqe.prep_setsocketopt(self.fd, self.val, self.level, self.optname)
        return sqe.user_data

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
    ip: bytes

    """The port to assign"""
    port: int

    _sockaddr: SocketAddress = field(init=False)

    """Address family"""
    address_family: AddressFamily = AddressFamily.AF_INET

    def __post_init__(self) -> None:
        """Initializes socket address attribute."""
        self._sockaddr = SocketAddress(
            family=self.address_family, ip=self.ip, port=self.port
        )

    @override
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        sqe.prep_socket_bind(self.fd, self._sockaddr)
        return sqe.user_data

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
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        sqe.prep_socket_listen(self.fd, self.backlog)
        return sqe.user_data

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
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Docstring."""
        sqe.prep_socket_accept(self.fd)
        return sqe.user_data

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
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Docstring."""
        sqe.prep_socket_recv(self.fd, self._buffer)
        return sqe.user_data

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
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Docstring."""
        sqe.prep_socket_send(self.fd, self.data)
        return sqe.user_data

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
    ip: bytes

    """The port to connect to"""
    port: int

    """The address family"""
    address_family: AddressFamily = AddressFamily.AF_INET

    _sockaddr: SocketAddress = field(init=False)

    def __post_init__(self) -> None:
        """Initializes socket family attribute."""
        self._sockaddr = SocketAddress(
            family=self.address_family, ip=self.ip, port=self.port
        )

    @override
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Docstring."""
        sqe.prep_connect(self.fd, self._sockaddr)
        return sqe.user_data

    @override
    def extract(self, completion_event: CompletionEvent) -> SocketConnectResult:
        """Docstring."""
        return SocketConnectResult()
