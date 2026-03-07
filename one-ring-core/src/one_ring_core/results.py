from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from one_ring_core.typedefs import WorkerOperationID


@dataclass(slots=True, kw_only=True, frozen=True)
class IOCompletion[T: IOResult]:
    """Wrapper around IO completion result."""

    """user_data identifier of completed operation"""
    user_data: WorkerOperationID

    """Result of operation. OSError if failed"""
    result: T | OSError

    def unwrap(self) -> T:
        """Rust style unwrapping of results."""
        if isinstance(self.result, OSError):
            raise self.result

        return self.result


@dataclass(slots=True, kw_only=True, frozen=True)
class IOResult:
    """Base class for all IO operation results."""


@dataclass(slots=True, kw_only=True, frozen=True)
class CancelResult(IOResult):
    """Result of cancelling an in flight IO operation."""


@dataclass(slots=True, kw_only=True, frozen=True)
class FileOpenResult(IOResult):
    """Result of a file open operation."""

    """File descriptor of opened file"""
    fd: int


@dataclass(slots=True, kw_only=True, frozen=True)
class StatxResult(IOResult):
    """Result of a statx file metadata operation."""

    """Size of file contents as bytes"""
    size: int

    """Last modification time in whole seconds"""
    mtime_sec: int

    """Inode number of the file"""
    ino: int

    """Encodes file type and permissions"""
    mode: int


@dataclass(slots=True, kw_only=True, frozen=True)
class ReadResult(IOResult):
    """Result of a read operation."""

    """Data read"""
    content: bytes

    """Number of bytes in data read"""
    size: int


@dataclass(slots=True, kw_only=True, frozen=True)
class WriteResult(IOResult):
    """Result of a file write operation."""

    """Number of bytes written"""
    size: int


@dataclass(slots=True, kw_only=True, frozen=True)
class CloseResult(IOResult):
    """Result of a file close operation."""


@dataclass(slots=True, kw_only=True, frozen=True)
class SleepResult(IOResult):
    """Result of sleeping."""


@dataclass(slots=True, kw_only=True, frozen=True)
class SocketCreateResult(IOResult):
    """Result for socket creation operation."""

    """File descriptor of created socket"""
    fd: int


@dataclass(slots=True, kw_only=True, frozen=True)
class SocketSetOptResult(IOResult):
    """Result for setting socket options operation."""


@dataclass(slots=True, kw_only=True, frozen=True)
class SocketBindResult(IOResult):
    """Result for binding socket operation."""


@dataclass(slots=True, kw_only=True, frozen=True)
class SocketListenResult(IOResult):
    """Result for setting socket as passive."""


@dataclass(slots=True, kw_only=True, frozen=True)
class SocketAcceptResult(IOResult):
    """Result for accepting connection on socket."""

    """File descriptor for new client connection."""
    fd: int


@dataclass(slots=True, kw_only=True, frozen=True)
class SocketRecvResult(IOResult):
    """Result for reading from socket."""

    """Data received in bytes"""
    content: bytes

    """Size of data received"""
    size: int


@dataclass(slots=True, kw_only=True, frozen=True)
class SocketSendResult(IOResult):
    """Result for sending data via socket."""

    """Size of data sent"""
    size: int


@dataclass(slots=True, kw_only=True, frozen=True)
class SocketConnectResult(IOResult):
    """Sentinal result for connecting to socket operation."""
