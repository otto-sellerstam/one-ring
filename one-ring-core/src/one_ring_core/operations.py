"""Docstring."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from liburing import (  # Automatically set to typing.Any by config.
    AT_FDCWD,
    O_APPEND,
    O_CREAT,
    O_RDONLY,
    O_RDWR,
    O_WRONLY,
)

from one_ring_core._ring import IOVec, MutableIOVec
from one_ring_core.results import (
    FileCloseResult,
    FileOpenResult,
    FileReadResult,
    FileWriteResult,
)

if TYPE_CHECKING:
    from one_ring_core._ring import CompletionEvent, SubmissionQueueEntry
    from one_ring_core.results import IOResult
    from one_ring_core.typedefs import WorkerOperationID


from one_ring_core.log import get_logger

logger = get_logger(__name__)


class IOOperation(ABC):
    """Base class for all IO operations."""

    @abstractmethod
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Prepares a submission queue entry for the SQ."""

    @abstractmethod
    def extract(self, completion_event: CompletionEvent) -> IOResult:
        """Extract fields from a completion queue event and wrap in correct type."""


### TODO: These base classes can probably be removed.


class FileIO(IOOperation):
    """Base class for all file IO operations."""


class NetworkIO(IOOperation):
    """Base class for all networking IO operations."""


class TimerIO(IOOperation):
    """Base class for all timer IO operations."""


class ControlIO(IOOperation):
    """Base class for all control IO operations."""


@dataclass
class FileOpen(FileIO):
    """Docstring."""

    path: bytes
    mode: str

    @override
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Prepares a submission queue entry for the SQ."""
        sqe.prep_openat(self.path, self._mode_to_flags(self.mode), 0o660, AT_FDCWD)
        return sqe.user_data

    @override
    def extract(self, completion_event: CompletionEvent) -> IOResult:
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


@dataclass
class FileRead(FileIO):
    """File descriptor for the regular file."""

    fd: int

    """None will read the whole file"""
    size: int | None = None

    """Not sure what this does"""
    offset: int = 0

    _vector_buffer: MutableIOVec = field(init=False)

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
    def extract(self, completion_event: CompletionEvent) -> IOResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileReadResult(
            content=self._vector_buffer.iov_base,
            size=completion_event.res,
        )


@dataclass
class FileWrite(FileIO):
    """File descriptor for the regular file."""

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
    def extract(self, completion_event: CompletionEvent) -> IOResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileWriteResult(
            size=completion_event.res,
        )


@dataclass
class FileClose(FileIO):
    """File descriptor for the regular file."""

    fd: int

    @override
    def prep(self, sqe: SubmissionQueueEntry) -> WorkerOperationID:
        """Prepares a submission queue entry for the SQ."""
        sqe.prep_close(self.fd)
        return sqe.user_data

    @override
    def extract(self, completion_event: CompletionEvent) -> IOResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileCloseResult()
