from __future__ import annotations

import socket
from enum import IntEnum

from one_ring_core.log import get_logger

logger = get_logger(__name__)


class AddressFamily(IntEnum):
    """Wrapper for socket address families."""

    AF_INET = socket.AF_INET
    AF_INET6 = socket.AF_INET6
