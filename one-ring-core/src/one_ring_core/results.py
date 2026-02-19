from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from one_ring_core.typedefs import WorkerOperationID


@dataclass(frozen=True)
class IOCompletion[T: IOResult]:
    """Docstring."""

    user_data: WorkerOperationID
    result: T | OSError

    def unwrap(self) -> T:
        """Rust style unwrapping of results."""
        if isinstance(self.result, OSError):
            raise self.result

        return self.result


@dataclass(frozen=True)
class IOResult:
    """Base class for all IO operation results."""


@dataclass(frozen=True)
class CancelResult(IOResult):
    """Result of cancelling an in flight IO operation."""


@dataclass(frozen=True)
class FileOpenResult(IOResult):
    """Result of a file open operation."""

    fd: int


@dataclass(frozen=True)
class FileReadResult(IOResult):
    """Result of a file read operation."""

    content: bytes
    size: int


@dataclass(frozen=True)
class FileWriteResult(IOResult):
    """Result of a file write operation."""

    size: int


@dataclass(frozen=True)
class CloseResult(IOResult):
    """Result of a file close operation."""


@dataclass(frozen=True)
class SleepResult(IOResult):
    """Result of sleeping."""


@dataclass(frozen=True)
class SocketCreateResult(IOResult):
    """Docstring."""

    fd: int


@dataclass(frozen=True)
class SocketSetOptResult(IOResult):
    """Docstring."""


@dataclass(frozen=True)
class SocketBindResult(IOResult):
    """Docstring."""


@dataclass(frozen=True)
class SocketListenResult(IOResult):
    """Docstring."""


@dataclass(frozen=True)
class SocketAcceptResult(IOResult):
    """Docstring."""

    """File descriptor for new client connection."""
    fd: int


@dataclass(frozen=True)
class SocketRecvResult(IOResult):
    """Docstring."""

    content: bytes
    size: int


@dataclass(frozen=True)
class SocketSendResult(IOResult):
    """Docstring."""

    size: int


@dataclass(frozen=True)
class SocketConnectResult(IOResult):
    """Docstring."""
