"""This will be a docstring."""

from __future__ import annotations

import os
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self, override

if TYPE_CHECKING:
    from types import TracebackType

from liburing import (  # Automatically set to typing.Any by config.
    AT_FDCWD,
    O_APPEND,
    O_CREAT,
    O_RDONLY,
    O_RDWR,
    O_WRONLY,
    io_uring,
    io_uring_cqe,
    io_uring_cqe_seen,
    io_uring_get_sqe,
    io_uring_peek_cqe,
    io_uring_prep_close,
    io_uring_prep_openat,
    io_uring_prep_read,
    io_uring_prep_write,
    io_uring_queue_exit,
    io_uring_queue_init,
    io_uring_sqe_set_data64,
    io_uring_submit,
    io_uring_wait_cqe,
    iovec,
)


class SubmissionQueueEntry:
    """Docstring."""

    def __init__(self, sqe, user_data: UserData) -> None:
        self._sqe = sqe
        self.user_data: UserData = user_data
        io_uring_sqe_set_data64(self._sqe, user_data)

    def prep_openat(self, path: bytes, flags: int, mode: int, dir_fd: int) -> None:
        """Docstring."""
        io_uring_prep_openat(self._sqe, path, flags, mode, dir_fd)

    def prep_read(self, fd: int, iov: MutableIOVec, offset: int) -> None:
        """Docstring."""
        io_uring_prep_read(self._sqe, fd, iov.iov_base, iov.iov_len, offset)

    def prep_write(self, fd: int, iov: IOVec, offset: int) -> None:
        """Docstring."""
        io_uring_prep_write(self._sqe, fd, iov.iov_base, iov.iov_len, offset)

    def prep_close(self, fd: int) -> None:
        """Docstring."""
        io_uring_prep_close(self._sqe, fd)


class BaseIOVec:
    """Docstring."""

    _iov: iovec

    @property
    def iov_base(self) -> bytes:
        """Docstring."""
        return self._iov.iov_base

    @property
    def iov_len(self) -> int:
        """Docstring."""
        return self._iov.iov_len


class IOVec(BaseIOVec):
    """Docstring."""

    def __init__(self, data: bytes) -> None:
        self._iov = iovec(data)


class MutableIOVec(BaseIOVec):
    """Docstring."""

    def __init__(self, data: bytearray) -> None:
        self._iov = iovec(data)  # pyrefly: ignore


### Operation request types


@dataclass
class IOOperation:
    """Base class for all IO operations."""

    def prep(self, sqe: SubmissionQueueEntry) -> UserData:
        """Prepares a submission queue entry for the SQ."""
        raise NotImplementedError("Operations should implement prepare method")

    def extract(self, cqe) -> IOResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        raise NotImplementedError("Operations should implement prepare method")


@dataclass
class FileIO(IOOperation):
    """Base class for all file IO operations."""


@dataclass
class NetworkIO(IOOperation):
    """Base class for all networking IO operations."""


@dataclass
class TimerIO(IOOperation):
    """Base class for all timer IO operations."""


@dataclass
class ControlIO(IOOperation):
    """Base class for all control IO operations."""


@dataclass
class FileOpen(FileIO):
    """Docstring."""

    path: bytes
    mode: str

    @override
    def prep(self, sqe: SubmissionQueueEntry) -> UserData:
        """Prepares a submission queue entry for the SQ."""
        sqe.prep_openat(self.path, self._mode_to_flags(self.mode), 0o660, AT_FDCWD)
        return sqe.user_data

    @override
    def extract(self, cqe) -> IOResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileOpenResult(
            fd=cqe.res,
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

        if "c" in mode or "w" in mode:
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
    def prep(self, sqe: SubmissionQueueEntry) -> UserData:
        """Prepares a submission queue entry for the SQ."""
        _size = self.size
        if _size is None:
            _size = os.fstat(self.fd).st_size  # Blocking syscall.
        self._vector_buffer = MutableIOVec(bytearray(_size))

        sqe.prep_read(self.fd, self._vector_buffer, self.offset)
        return sqe.user_data

    @override
    def extract(self, cqe) -> IOResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileReadResult(
            content=self._vector_buffer.iov_base.decode(),
            size=cqe.res,
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
    def prep(self, sqe: SubmissionQueueEntry) -> UserData:
        """Prepares a submission queue entry for the SQ."""
        vector_buffer = IOVec(self.data)
        sqe.prep_write(self.fd, vector_buffer, self.offset)
        return sqe.user_data

    @override
    def extract(self, cqe) -> IOResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileWriteResult(
            size=cqe.res,
        )


@dataclass
class FileClose(FileIO):
    """File descriptor for the regular file."""

    fd: int

    @override
    def prep(self, sqe: SubmissionQueueEntry) -> UserData:
        """Prepares a submission queue entry for the SQ."""
        sqe.prep_close(self.fd)
        return sqe.user_data

    @override
    def extract(self, cqe) -> IOResult:
        """Extract fields from a completion queue event and wrap in correct type."""
        return FileCloseResult()


### Operation result types.


@dataclass
class IOCompletion:
    """Docstring."""

    user_data: UserData
    result: IOResult


@dataclass
class IOResult:
    """Base class for all IO operation results."""


@dataclass
class FileIOResult(IOResult):
    """Base class for all file IO operation results."""


@dataclass
class NetworkIOResult(IOResult):
    """Base class for all networking IO operation results."""


@dataclass
class TimerIOResult(IOResult):
    """Base class for all timer IO operation results."""


@dataclass
class ControlIOResult(IOResult):
    """Base class for all control IO operation results."""


@dataclass
class FileOpenResult(IOResult):
    """Result of a file open operation."""

    fd: int


@dataclass
class FileReadResult(IOResult):
    """Result of a file read operation."""

    content: str
    size: int


@dataclass
class FileWriteResult(IOResult):
    """Result of a file write operation."""

    size: int


@dataclass
class FileCloseResult(IOResult):
    """Result of a file close operation."""


type UserData = int


@dataclass
class CompletionEvent:
    """Docstring."""

    user_data: UserData
    res: int
    flags: int


class Ring:
    def __init__(self, depth: int = 32) -> None:
        self._ring = io_uring()
        self._cqe = io_uring_cqe()
        self._depth = depth

    def __enter__(self) -> Self:
        """Docstring."""
        io_uring_queue_init(self._depth, self._ring, 0)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Docstring."""
        io_uring_queue_exit(self._ring)

    def submit(self) -> int:
        """Submits the SQ to the kernel."""
        # This should check that all new registrations where actually submitted
        return io_uring_submit(self._ring)

    def peek(self) -> CompletionEvent | None:
        """Docstring."""
        if io_uring_peek_cqe(self._ring, self._cqe) == 0:
            return self._consume_cqe()
        return None

    def wait(self) -> CompletionEvent:
        """Docstring."""
        io_uring_wait_cqe(self._ring, self._cqe)
        return self._consume_cqe()

    def _consume_cqe(self) -> CompletionEvent:
        event = CompletionEvent(
            user_data=self._cqe.user_data,
            res=self._cqe.res,
            flags=self._cqe.flags,
        )
        io_uring_cqe_seen(self._ring, self._cqe)
        return event

    def get_sqe(self, user_data: int) -> SubmissionQueueEntry:
        """Returns a SQE from the SQ, with set user_data."""
        if not user_data:
            raise ValueError("user_data cannot be 0")

        sqe = io_uring_get_sqe(self._ring)
        return SubmissionQueueEntry(
            sqe,
            user_data,
        )


class IOWorker:
    """Docstring."""

    def __init__(self) -> None:
        self._ring = Ring()

        # Maps user_data (internal) to respective operation.
        self._active_submissions: dict[UserData, IOOperation] = {}

        # Buffers for reading data.
        self._iovecs: dict[UserData, MutableIOVec] = {}

    def register(self, operation: IOOperation) -> UserData:
        """Registers operation in the SQ."""
        user_data = operation.prep(self._get_sqe())

        self._add_submission(user_data, operation)
        return user_data

    def _get_user_data(self) -> UserData:
        """Gets the smallest positive number which is unused.

        TODO: Optimize.
        """
        user_data = 1
        while user_data <= len(self._active_submissions):
            if user_data not in self._active_submissions:
                break

            user_data += 1

        return user_data

    def _add_submission(self, user_data: UserData, operation: IOOperation) -> None:
        self._active_submissions[user_data] = operation

    def _pop_submission(self, user_data: UserData) -> IOOperation:
        """Pops a submission from the internal tracking of active submissions.

        Args:
            user_data: the submission to pop.

        Returns:
            The popped submission.
        """
        return self._active_submissions.pop(user_data)

    def submit(self) -> None:
        """Submits the SQ to the kernel."""
        # This should check that all new registrations where actually submitted
        number_submitted = self._ring.submit()
        print(f"Submitted {number_submitted} SQEs")

    def wait(self) -> IOCompletion:
        """Blocking check if a completion event is available.

        Returns:
            IOCompletion
        """
        io_uring_wait_cqe(self._ring, self._cqe)
        return self._extract_cqe()

    def peek(self) -> IOCompletion | None:
        """Nonblocking check if a completion event is available.

        Returns:
            IOCompletion if available, otherwise None.
        """
        if self._ring.peek() == 0:
            return self._extract_cqe()

        return None

    def __enter__(self) -> Self:
        """Docstring."""
        self._stack = ExitStack()
        self._stack.__enter__()
        self._ring = self._stack.enter_context(Ring(depth=32))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Docstring."""
        self._stack.__exit__(exc_type, exc_val, exc_tb)

    def _extract_cqe(self) -> IOCompletion:
        """Fetches data from completion event and transforms to relevant type."""
        user_data = self._cqe.user_data
        # Now we need to handle the CQE based on the operation type of the submission.
        operation = self._pop_submission(user_data)
        try:
            result = operation.extract(self._cqe)
        finally:
            io_uring_cqe_seen(self._ring, self._cqe)

        return IOCompletion(
            user_data=user_data,
            result=result,
        )

    def _get_sqe(self) -> SubmissionQueueEntry:
        user_data = self._get_user_data()
        return self._ring.get_sqe(user_data)


def main() -> None:
    """Docstring."""
    with IOWorker() as worker:
        worker.register(FileOpen(b"./testing/hello.txt", "rwa"))
        worker.register(FileOpen(b"./testing/world.txt", "rwa"))
        worker.register(FileOpen(b"./testing/exclamation.txt", "rwa"))
        worker.submit()
        i = 0
        while i < 3:
            completion = worker.peek()
            if completion is not None and isinstance(completion.result, FileOpenResult):
                print(f"Found {completion}")
                worker.register(FileWrite(completion.result.fd, f"Otto {i}".encode()))
                i += 1

        worker.submit()

        i = 0
        while i < 3:
            result = worker.peek()
            if result is not None:
                print(result)
                i += 1


if __name__ == "__main__":
    main()
