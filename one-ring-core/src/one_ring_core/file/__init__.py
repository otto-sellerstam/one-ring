from __future__ import annotations

from liburing import (  # Automatically set to typing.Any by config.
    iovec,
)

from one_ring_core.log import get_logger

logger = get_logger(__name__)


class BaseIOVec:
    """Wrapper around liburing's iovec."""

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
    """IOVec for immutable data."""

    def __init__(self, data: bytes) -> None:
        self._iov = iovec(data)  # pyrefly: ignore


class MutableIOVec(BaseIOVec):
    """IOVec for mutable data."""

    def __init__(self, data: bytearray) -> None:
        self._iov = iovec(data)  # pyrefly: ignore
