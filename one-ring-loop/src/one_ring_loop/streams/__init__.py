from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

from one_ring_loop.log import get_logger
from one_ring_loop.sync_primitives import Condition

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro

logger = get_logger()


class ClosedResourceError(Exception):
    """Thrown when the relevant stream has been closed."""


class BrokenResourceError(Exception):
    """Thrown when opposite end of stream has been closed."""


class EndOfStreamError(Exception):
    """Thrown when receive stream buffer is empty and send stream is closed."""


@dataclass
class MemoryObjectStreamBase[T]:
    """Base class for memory object receive and send streams."""

    """Shared buffer for sending into"""
    buffer: deque[T]

    """Condition if ready to send. Notified from receiver"""
    send_condition: Condition

    """Condition if ready to receive. Notified from sender"""
    receive_condition: Condition

    """Shared mutable stream refcount state"""
    stream_refcount: StreamRefcount

    """If the stream instance has been closed."""
    _closed: bool = field(default=False, init=False)


@dataclass
class MemoryObjectSendStream[T](MemoryObjectStreamBase[T]):
    """Sends items to a MemoryObjectReceiveStream."""

    def close(self) -> Coro[None]:
        """Closes the resource.

        Notifies all receives when all send streams have closed.
        """
        self._closed = True
        self.stream_refcount["send_streams"] -= 1
        if self.stream_refcount["send_streams"] <= 0:
            yield from self.receive_condition.acquire()
            try:
                self.receive_condition.notify_all()
            finally:
                self.receive_condition.release()

    def clone(self) -> MemoryObjectSendStream[T]:
        """Creates a clone of this send stream."""
        self.stream_refcount["send_streams"] += 1

        return MemoryObjectSendStream[T](
            buffer=self.buffer,
            send_condition=self.send_condition,
            receive_condition=self.receive_condition,
            stream_refcount=self.stream_refcount,
        )

    def send(self, item: T) -> Coro[None]:
        """Sends an item to the stream."""
        if self._closed:
            raise ClosedResourceError("Send stream already closed")
        elif self.stream_refcount["receive_streams"] <= 0:
            raise BrokenResourceError("All receive streams are closed")

        yield from self.send_condition.acquire()
        try:
            while not self._predicate():
                yield from self.send_condition.wait()
            self.buffer.append(item)
        finally:
            self.send_condition.release()

        yield from self.receive_condition.acquire()
        try:
            self.receive_condition.notify(1)
        finally:
            self.receive_condition.release()

    def _predicate(self) -> bool:
        if self.stream_refcount["receive_streams"] <= 0:
            raise BrokenResourceError

        if self.buffer.maxlen is None:
            return True

        return len(self.buffer) < self.buffer.maxlen


@dataclass
class MemoryObjectReceiveStream[T](MemoryObjectStreamBase[T]):
    """Receives items from a MemoryObjectSendStream."""

    def close(self) -> Coro[None]:
        """Closes the resource."""
        self._closed = True
        self.stream_refcount["receive_streams"] -= 1
        if self.stream_refcount["receive_streams"] <= 0:
            yield from self.send_condition.acquire()
            try:
                self.send_condition.notify_all()
            finally:
                self.send_condition.release()

    def clone(self) -> MemoryObjectReceiveStream[T]:
        """Creates a clone of this send stream."""
        self.stream_refcount["receive_streams"] += 1

        return MemoryObjectReceiveStream[T](
            buffer=self.buffer,
            send_condition=self.send_condition,
            receive_condition=self.receive_condition,
            stream_refcount=self.stream_refcount,
        )

    def receive(self) -> Coro[T]:
        """Receives an item from the stream."""
        if self._closed:
            raise ClosedResourceError("Receive stream already closed")

        yield from self.receive_condition.acquire()
        try:
            while not self._predicate():
                yield from self.receive_condition.wait()
            item = self.buffer.popleft()
        finally:
            self.receive_condition.release()

        yield from self.send_condition.acquire()
        try:
            self.send_condition.notify(1)
        finally:
            self.send_condition.release()

        return item

    def _predicate(self) -> bool:
        is_empty = len(self.buffer) == 0
        if is_empty and self.stream_refcount["send_streams"] <= 0:
            raise EndOfStreamError
        return not is_empty


class StreamRefcount(TypedDict):
    """Type for mutable stream ref count state."""

    receive_streams: int
    send_streams: int


class create_memory_object_stream[T]:  # noqa: N801
    """Dummy wrapper to allow for proper generic typing."""

    def __new__(
        cls, max_buffer_size: int | None = 1
    ) -> tuple[MemoryObjectSendStream[T], MemoryObjectReceiveStream[T]]:
        """Creates and returns a send and receive stream."""
        buffer: deque[T] = deque(maxlen=max_buffer_size)
        receive_condition = Condition()
        send_condition = Condition()

        stream_refcount: StreamRefcount = {
            "receive_streams": 1,
            "send_streams": 1,
        }

        return (
            MemoryObjectSendStream(
                buffer=buffer,
                send_condition=send_condition,
                receive_condition=receive_condition,
                stream_refcount=stream_refcount,
            ),
            MemoryObjectReceiveStream(
                buffer=buffer,
                send_condition=send_condition,
                receive_condition=receive_condition,
                stream_refcount=stream_refcount,
            ),
        )
