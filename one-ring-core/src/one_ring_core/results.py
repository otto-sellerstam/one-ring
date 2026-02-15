from __future__ import annotations

from dataclasses import dataclass

from one_ring_core.types import UserData


@dataclass(frozen=True)
class IOCompletion:
    user_data: UserData
    result: IOResult

@dataclass(frozen=True)
class IOResult:
    """Base class for all IO operation results"""

@dataclass(frozen=True)
class FileIOResult(IOResult):
    """Base class for all file IO operation results"""

@dataclass(frozen=True)
class NetworkIOResult(IOResult):
    """Base class for all networking IO operation results"""

@dataclass(frozen=True)
class TimerIOResult(IOResult):
    """Base class for all timer IO operation results"""

@dataclass(frozen=True)
class ControlIOResult(IOResult):
    """Base class for all control IO operation results"""

@dataclass(frozen=True)
class FileOpenResult(IOResult):
    """Result of a file open operation"""
    fd: int

@dataclass(frozen=True)
class FileReadResult(IOResult):
    """Result of a file read operation"""
    content: str
    size: int

@dataclass(frozen=True)
class FileWriteResult(IOResult):
    """Result of a file write operation"""
    size: int

@dataclass(frozen=True)
class FileCloseResult(IOResult):
    """Result of a file close operation"""