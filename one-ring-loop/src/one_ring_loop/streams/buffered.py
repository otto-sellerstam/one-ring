from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from one_ring_loop.streams.exceptions import (
    ClosedResourceError,
    DelimiterNotFoundError,
    EndOfStreamError,
)

if TYPE_CHECKING:
    from one_ring_loop.streams.protocols import ReceiveStream, SendStream
    from one_ring_loop.typedefs import Coro


@dataclass(slots=True, kw_only=True)
class BufferedByteReceiveStream:
    """Wraps any bytes-based receive stream to exposed buffered reads."""

    """Wrapped receive stream"""
    receive_stream: ReceiveStream[bytes]

    """Internal buffer"""
    _buffer: bytearray = field(default_factory=bytearray, init=False, repr=False)

    """Marker for closed resouce"""
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> Coro[None]:
        """Closes the resouce."""
        yield from self.receive_stream.close()
        self._closed = True

    def receive(self, max_bytes: int = 65536) -> Coro[bytes]:
        """Reads data from the resource."""
        if self._closed:
            raise ClosedResourceError("Cannot received from closed resouce")

        if len(self._buffer) >= max_bytes:
            data = bytes(self._buffer[:max_bytes])
            self._buffer = self._buffer[max_bytes:]
            return data

        received_data = yield from self.receive_stream.receive()
        combined_data = self._buffer + received_data
        self._buffer = combined_data[max_bytes:]
        return bytes(combined_data[:max_bytes])

    def receive_exactly(self, nbytes: int) -> Coro[bytes]:
        """Reads exactly the given amount of bytes from the resouce."""
        try:
            while len(self._buffer) < nbytes:
                content = yield from self.receive_stream.receive()
                self._buffer.extend(content)
        except EndOfStreamError as e:
            raise EndOfStreamError("Stream closed before receiving enough data") from e

        data = bytes(self._buffer[:nbytes])
        self._buffer = self._buffer[nbytes:]
        return data

    def receive_until(self, *, delimiter: bytes, max_bytes: int) -> Coro[bytes]:
        """Reads from the resouce until delimiter is found, or max bytes are read."""
        try:
            while len(self._buffer) < max_bytes and delimiter not in self._buffer:
                content = yield from self.receive_stream.receive()
                self._buffer.extend(content)
        except EndOfStreamError as e:
            raise EndOfStreamError("Stream closed before delimiter found") from e

        if len(split := self._buffer.split(delimiter, 1)) > 1:
            self._buffer = split[1]
            return bytes(split[0])

        msg = f"Delimiter '{delimiter}' was not found within {max_bytes} bytes"
        raise DelimiterNotFoundError(msg)

    @property
    def buffer(self) -> bytes:
        """Returns the contents of the internal buffer."""
        return bytes(self._buffer)


@dataclass(slots=True, kw_only=True)
class BufferedByteStream(BufferedByteReceiveStream):
    """Full-duplex variant of buffered receive stream."""

    """Thinly wrapped send stream"""
    send_stream: SendStream[bytes]

    @override
    def close(self) -> Coro[None]:
        yield from super().close()
        yield from self.send_stream.close()

    def send(self, data: bytes) -> Coro[None]:
        """Sends data via send stream."""
        yield from self.send_stream.send(data)
