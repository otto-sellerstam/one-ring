"""Root conftest — pre-import workspace packages and shared fixtures.

Without this, pytest's directory traversal registers package directories
(e.g. core/) as namespace packages before test collection, which shadows the
real packages installed from <pkg>/src/.  Importing them here (while
pythonpath is already in effect) caches the correct module in sys.modules.
"""

import socket
import ssl
import subprocess
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

import one_ring_asyncio  # noqa: F401
import one_ring_core  # noqa: F401
import one_ring_http  # noqa: F401
import one_ring_loop  # noqa: F401
from one_ring_loop.loop import run

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from one_ring_loop.typedefs import Coro


@pytest.fixture
def tmp_file_path(tmp_path: Path) -> Path:
    """Provide a temporary file path for file I/O tests.

    Uses pytest's built-in "tmp_path" fixture.
    """
    return tmp_path / "test_file.txt"


@dataclass(slots=True, kw_only=True)
class TimingContext:
    """Captures elapsed time and provides tolerance-aware assertions."""

    _start: float = field(default=0, repr=False)
    _end: float = field(default=0, repr=False)

    def start(self) -> None:
        """Record the start time."""
        self._start = time.monotonic()

    def stop(self) -> None:
        """Record the end time."""
        self._end = time.monotonic()

    @property
    def elapsed(self) -> float:
        """Return elapsed seconds since start."""
        if self._end == 0.0:
            return time.monotonic() - self._start
        return self._end - self._start

    def assert_elapsed_between(
        self, lower: float, upper: float, *, msg: str = ""
    ) -> None:
        """Assert elapsed time is within [lower, upper] seconds."""
        elapsed = self.elapsed
        context = f" ({msg})" if msg else ""
        assert lower <= elapsed <= upper, (  # noqa: S101
            f"Expected elapsed time in [{lower}, {upper}]s, got {elapsed:.3f}s{context}"
        )


@pytest.fixture
def run_coro() -> Callable[[Coro], object]:
    """Run a generator coroutine on the event loop."""

    def _run(coro: Coro) -> object:
        return run(coro)

    return _run


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


@pytest.fixture
def ssl_contexts(tmp_path: Path) -> tuple[ssl.SSLContext, ssl.SSLContext]:
    """Generates temporay server and client ssl contexts."""
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"

    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            key_path,
            "-out",
            cert_path,
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )

    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert_path, key_path)

    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_ctx.load_verify_locations(cert_path)

    return server_ctx, client_ctx
