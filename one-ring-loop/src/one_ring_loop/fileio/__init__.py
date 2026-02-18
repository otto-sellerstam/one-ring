from dataclasses import dataclass
from typing import TYPE_CHECKING

from one_ring_core.operations import Close, FileOpen, FileRead, FileWrite
from one_ring_core.results import (
    CloseResult,
    FileOpenResult,
    FileReadResult,
    FileWriteResult,
)
from one_ring_loop.typedefs import _execute

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


@dataclass
class File:
    """Utility wrapper for file operations. Represents a single regular file."""

    fd: int

    def read(self) -> Coro[str]:
        """Read file low-level coroutine."""
        result = yield from _execute(FileRead(self.fd), FileReadResult)
        return result.content.decode()

    def write(self, data: bytes | str) -> Coro[int]:
        """Write file low-level coroutine."""
        _data = data.encode() if isinstance(data, str) else data
        result = yield from _execute(FileWrite(self.fd, _data), FileWriteResult)
        return result.size

    def close(self) -> Coro[None]:
        """Close file low-level coroutine."""
        yield from _execute(Close(self.fd), CloseResult)
        return None


def open_file(path: str, mode: str = "r") -> Coro[File]:
    """Open file coroutine."""
    result = yield from _execute(FileOpen(path.encode(), mode), FileOpenResult)
    return File(result.fd)
