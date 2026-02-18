from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from types import TracebackType

    from one_ring_core.typedefs import WorkerOperationID

from liburing import (  # Automatically set to typing.Any by config.
    io_uring,
    io_uring_cqe,
    io_uring_cqe_seen,
    io_uring_get_sqe,
    io_uring_peek_cqe,
    io_uring_prep_close,
    io_uring_prep_openat,
    io_uring_prep_read,
    io_uring_prep_timeout,
    io_uring_prep_write,
    io_uring_queue_exit,
    io_uring_queue_init,
    io_uring_sqe_set_data64,
    io_uring_submit,
    io_uring_wait_cqe,
    iovec,
)

from one_ring_core.log import get_logger

logger = get_logger(__name__)


class SubmissionQueueEntry:
    """Wrapper around liburing's SQE."""

    def __init__(self, sqe: Any, user_data: WorkerOperationID) -> None:  # noqa: ANN401
        self._sqe = sqe
        self.user_data: WorkerOperationID = user_data
        io_uring_sqe_set_data64(self._sqe, user_data)

    def prep_openat(self, path: bytes, flags: int, mode: int, dir_fd: int) -> None:
        """Preps SQE for opening file."""
        io_uring_prep_openat(self._sqe, path, flags, mode, dir_fd)

    def prep_read(self, fd: int, iov: MutableIOVec, offset: int) -> None:
        """Preps SQE for reading from file."""
        io_uring_prep_read(self._sqe, fd, iov.iov_base, iov.iov_len, offset)

    def prep_write(self, fd: int, iov: IOVec, offset: int) -> None:
        """Preps SQE for writing to file."""
        io_uring_prep_write(self._sqe, fd, iov.iov_base, iov.iov_len, offset)

    def prep_close(self, fd: int) -> None:
        """Preps SQE for closing file."""
        io_uring_prep_close(self._sqe, fd)

    def prep_timeout(self, ts: Any, count: int = 0, flags: int = 0) -> None:  # noqa: ANN401
        """Prepares SQE for timeout (used for async sleep)."""
        io_uring_prep_timeout(self._sqe, ts, count, flags)


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
        self._iov = iovec(data)  # pyrefly: ignore


class MutableIOVec(BaseIOVec):
    """Docstring."""

    def __init__(self, data: bytearray) -> None:
        self._iov = iovec(data)  # pyrefly: ignore


@dataclass
class CompletionEvent:
    """Docstring."""

    user_data: WorkerOperationID
    res: int
    flags: int


@dataclass
class Ring:
    """Utility wrappeer of ring buffer."""

    depth: int = field(default=32)
    _cqe: Any = field(default=io_uring_cqe(), init=False)
    _ring: Any = field(default=io_uring(), init=False)
    _cqe_ready: bool = field(default=False, init=False)

    def __enter__(self) -> Self:
        """Docstring."""
        io_uring_queue_init(self.depth, self._ring, 0)
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
            self._mark_cqe_ready()
            return self._consume_cqe()
        return None

    def wait(self) -> CompletionEvent:
        """Docstring."""
        io_uring_wait_cqe(self._ring, self._cqe)
        self._mark_cqe_ready()
        return self._consume_cqe()

    def get_sqe(self, user_data: int) -> SubmissionQueueEntry:
        """Returns a SQE from the SQ, with set user_data."""
        if not user_data:
            raise ValueError("user_data cannot be 0")

        sqe = io_uring_get_sqe(self._ring)
        return SubmissionQueueEntry(
            sqe,
            user_data,
        )

    def _mark_cqe_ready(self) -> None:
        """Marks a consumer completion event as ready."""
        self._cqe_ready = True

    def _mark_cqe_seen(self) -> None:
        """Marks a consumer completion event as seen."""
        io_uring_cqe_seen(self._ring, self._cqe)
        self._cqe_ready = False

    def _consume_cqe(self) -> CompletionEvent:
        """Consumes a CQE.

        Returns:
            CompletionEvent
        """
        if not self._cqe_ready:
            raise RuntimeError("No completion event ready")
        try:
            event = CompletionEvent(
                user_data=self._cqe.user_data,
                res=self._cqe.res,
                flags=self._cqe.flags,
            )
        finally:
            self._mark_cqe_seen()
        return event
