from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from one_ring_core.operations import Close, FileOpen, Read, Statx, Write
from one_ring_loop._utils import _execute

if TYPE_CHECKING:
    from one_ring_core.results import StatxResult
    from one_ring_loop.typedefs import Coro


@dataclass(slots=True, kw_only=True)
class File:
    """Utility wrapper for file operations. Represents a single regular file."""

    fd: int

    def read(self, size: int | None = None) -> Coro[bytes]:
        """Read file low-level coroutine.

        Args:
            size: number of bytes to fetch. Fetches the whole file if None.
        """
        _size = size
        if _size is None:
            # Async fetching of size from metadata using statx.
            metadata = yield from _execute(Statx.from_fd(fd=self.fd))
            _size = metadata.size

        result = yield from _execute(Read(fd=self.fd, size=_size))
        return result.content

    def read_text(self, size: int | None = None) -> Coro[str]:
        """Reads file content and decodes to string."""
        content = yield from self.read(size)
        return content.decode()

    def write(self, data: bytes | str) -> Coro[int]:
        """Write file low-level coroutine.

        Args:
            data: the data to write to the file.
        """
        _data = data.encode() if isinstance(data, str) else data
        result = yield from _execute(Write(fd=self.fd, data=_data))
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


def statx(path: str | Path) -> Coro[StatxResult]:
    """Gets file metadata via statx."""
    _path = str(path) if isinstance(path, Path) else path

    result = yield from _execute(Statx.from_path(_path))
    return result
