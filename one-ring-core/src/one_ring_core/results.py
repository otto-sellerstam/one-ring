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
class FileIOResult(IOResult):
    """Base class for all file IO operation results."""


@dataclass(frozen=True)
class NetworkIOResult(IOResult):
    """Base class for all networking IO operation results."""


@dataclass(frozen=True)
class TimerIOResult(IOResult):
    """Base class for all timer IO operation results."""


@dataclass(frozen=True)
class ControlIOResult(IOResult):
    """Base class for all control IO operation results."""


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
class FileCloseResult(IOResult):
    """Result of a file close operation."""
