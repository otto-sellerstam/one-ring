from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from liburing import (  # Automatically set to typing.Any by config.
    SocketFamily,
    sockaddr,
)

from one_ring_core.log import get_logger

logger = get_logger(__name__)


class AddressFamily(Enum):
    """Wrapper for socket address families."""

    AF_UNIX = SocketFamily.AF_UNIX
    AF_INET = SocketFamily.AF_INET
    AF_INET6 = SocketFamily.AF_INET6


@dataclass(slots=True, kw_only=True)
class SocketAddress:
    """Wrapper around liburing's sockaddr."""

    """The address family of the socket"""
    family: AddressFamily

    """IP of the address"""
    ip: bytes

    """Port of the address"""
    port: int

    _sockaddr: sockaddr = field(init=False)

    def __post_init__(self) -> None:
        """Constructs sockaddr object and attaches to self."""
        self._sockaddr = sockaddr(self.family.value, self.ip, self.port)

    def get_sockaddr(self) -> sockaddr:
        """Returns a sockaddr object."""
        return self._sockaddr
