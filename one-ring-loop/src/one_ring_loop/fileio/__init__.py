from dataclasses import dataclass
from typing import TYPE_CHECKING

from one_ring_core.operations import FileClose, FileOpen, FileRead, FileWrite
from one_ring_core.results import (
    FileCloseResult,
    FileOpenResult,
    FileReadResult,
    FileWriteResult,
)

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


@dataclass
class File:
    """Utility wrapper for file operations. Represents a single regular file."""

    fd: int

    def read(self) -> Coro[str]:
        """Read file low-level coroutine."""
        read_completion = yield FileRead(self.fd)
        if read_completion is not None and isinstance(
            result := read_completion.unwrap(), FileReadResult
        ):
            return result.content.decode()

        raise ValueError("read_file received wrong result type")

    def write(self, data: bytes | str) -> Coro[int]:
        """Read file low-level coroutine."""
        _data = data.encode() if isinstance(data, str) else data

        read_completion = yield FileWrite(self.fd, _data)
        if read_completion is not None and isinstance(
            result := read_completion.unwrap(), FileWriteResult
        ):
            return result.size

        raise ValueError("write_file received wrong result type")

    def close(self) -> Coro[bool]:
        """Read file low-level coroutine."""
        close_completion = yield FileClose(self.fd)
        if close_completion is not None and isinstance(
            result := close_completion.unwrap(), FileCloseResult
        ):
            return result.success

        raise ValueError("close_file received wrong result type")


def open_file(path: str, mode: str = "r") -> Coro[File]:
    """Test file open coroutine."""
    open_completion = yield FileOpen(path.encode(), mode)
    if open_completion is not None and isinstance(
        result := open_completion.unwrap(), FileOpenResult
    ):
        return File(result.fd)

    raise ValueError("open_file received wrong result type")
