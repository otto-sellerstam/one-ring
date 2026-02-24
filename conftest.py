"""Root conftest — pre-import workspace packages.

Without this, pytest's directory traversal registers package directories
(e.g. core/) as namespace packages before test collection, which shadows the
real packages installed from <pkg>/src/.  Importing them here (while
pythonpath is already in effect) caches the correct module in sys.modules.
"""

import one_ring_asyncio  # noqa: F401
import one_ring_core  # noqa: F401
import one_ring_http  # noqa: F401
import one_ring_loop  # noqa: F401
