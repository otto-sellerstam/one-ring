from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


class Resource(Protocol):
    """Defines an async resouce."""

    def close(self) -> Coro[None]:
        """Closes the resouce."""


class ReceiveStream[T](Resource, Protocol):
    """Common interface usable with buffered byte receive stream."""

    def receive(self) -> Coro[T]:
        """Receives data from stream."""


class SendStream[T](Resource, Protocol):
    """Common interface for sending usable with buffered byte stream."""

    def send(self, data: T, /) -> Coro[None]:
        """Sends data to stream."""


class TransportStream[T](SendStream[T], ReceiveStream[T], Protocol):
    """Bidirectional stream."""
