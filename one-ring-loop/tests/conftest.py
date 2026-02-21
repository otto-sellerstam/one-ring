"""Shared test fixtures for one-ring-loop."""

import socket
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from one_ring_loop.loop import run

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from one_ring_loop.typedefs import Coro


@dataclass
class TimingContext:
    """Captures elapsed time and provides tolerance-aware assertions."""

    _start: float = field(default=0, repr=False)
    _end: float = field(default=0, repr=False)

    def start(self) -> None:
        self._start = time.monotonic()

    def stop(self) -> None:
        self._end = time.monotonic()

    @property
    def elapsed(self) -> float:
        if self._end == 0.0:
            return time.monotonic() - self._start
        return self._end - self._start

    def assert_elapsed_between(
        self, lower: float, upper: float, *, msg: str = ""
    ) -> None:
        """Assert elapsed time is within [lower, upper] seconds."""
        elapsed = self.elapsed
        context = f" ({msg})" if msg else ""
        assert lower <= elapsed <= upper, (
            f"Expected elapsed time in [{lower}, {upper}]s, got {elapsed:.3f}s{context}"
        )


@pytest.fixture
def run_coro() -> Callable[[Coro], object]:
    """Run a generator coroutine on the event loop."""

    def _run(coro: Coro) -> object:
        return run(coro)

    return _run


@pytest.fixture
def tmp_file_path(tmp_path: Path) -> Path:
    """Provide a temporary file path for file I/O tests.

    Uses pytest's built-in "tmp_path" fixture.
    """
    return tmp_path / "test_file.txt"


@pytest.fixture
def unused_tcp_port() -> int:
    """Find an unused TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture
def timing() -> TimingContext:
    """Provide a timing context for measuring elapsed time in tests."""
    return TimingContext()
