from typing import TYPE_CHECKING

import pytest

from one_ring_loop.log import get_logger
from one_ring_loop.streams.buffered import (
    BufferedByteStream,
)
from one_ring_loop.streams.exceptions import ClosedResourceError, DelimiterNotFoundError
from one_ring_loop.streams.memory import (
    create_memory_object_stream,
)

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


logger = get_logger(__name__)


class TestBufferedByteStream:
    def test_receive_exactly(self, run_coro) -> None:
        def entry() -> Coro[None]:
            send_stream, receive_stream = create_memory_object_stream[bytes](5)
            buffered = BufferedByteStream(
                send_stream=send_stream, receive_stream=receive_stream
            )
            try:
                for part in b"hel", b"lo, ", b"wo", b"rld!":
                    yield from buffered.send(part)

                result = yield from buffered.receive_exactly(8)
                assert result == b"hello, w"
            finally:
                yield from buffered.close()

        run_coro(entry())

    def test_receive_until(self, run_coro) -> None:
        def entry() -> Coro[None]:
            send_stream, receive_stream = create_memory_object_stream[bytes](5)
            buffered = BufferedByteStream(
                send_stream=send_stream, receive_stream=receive_stream
            )
            try:
                for part in b"hel", b"lo, ", b"wo", b"rld!":
                    yield from buffered.send(part)

                result = yield from buffered.receive_until(delimiter=b"w", max_bytes=10)
                assert result == b"hello, "
            finally:
                yield from buffered.close()

        run_coro(entry())

    def test_receive_until_no_delimiter_raises(self, run_coro) -> None:
        def entry() -> Coro[None]:
            send_stream, receive_stream = create_memory_object_stream[bytes](5)
            buffered = BufferedByteStream(
                send_stream=send_stream, receive_stream=receive_stream
            )
            try:
                for part in b"hel", b"lo, ", b"wo", b"rld!":
                    yield from buffered.send(part)

                result = yield from buffered.receive_until(delimiter=b"x", max_bytes=10)
                assert result == b"hello, "
            finally:
                yield from buffered.close()

        with pytest.raises(DelimiterNotFoundError):
            run_coro(entry())

    def test_closed_stream_raises(self, run_coro) -> None:
        def entry() -> Coro[None]:
            send_stream, receive_stream = create_memory_object_stream[bytes](5)
            buffered = BufferedByteStream(
                send_stream=send_stream, receive_stream=receive_stream
            )
            try:
                for part in b"hel", b"lo, ", b"wo", b"rld!":
                    yield from buffered.send(part)

                yield from buffered.close()

                result = yield from buffered.receive_until(delimiter=b"w", max_bytes=10)
                assert result == b"hello, "
            finally:
                yield from buffered.close()

        with pytest.raises(ClosedResourceError):
            run_coro(entry())
