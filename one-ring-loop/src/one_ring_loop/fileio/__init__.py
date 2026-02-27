from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from one_ring_core.operations import Close, FileOpen, FileRead, FileWrite
from one_ring_loop._utils import _execute

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


@dataclass(slots=True, kw_only=True)
class File:
    """Utility wrapper for file operations. Represents a single regular file."""

    fd: int

    def read(self) -> Coro[str]:
        """Read file low-level coroutine."""
        result = yield from _execute(FileRead(fd=self.fd))
        return result.content.decode()

    def write(self, data: bytes | str) -> Coro[int]:
        """Write file low-level coroutine."""
        _data = data.encode() if isinstance(data, str) else data
        result = yield from _execute(FileWrite(fd=self.fd, data=_data))
        return result.size

    def close(self) -> Coro[None]:
        """Close file low-level coroutine."""
        yield from _execute(Close(fd=self.fd))
        return None


def open_file(path: str | Path, mode: str = "r") -> Coro[File]:
    """Open file coroutine."""
    _path = str(path) if isinstance(path, Path) else path

    result = yield from _execute(FileOpen(path=_path, mode=mode))
    return File(fd=result.fd)
