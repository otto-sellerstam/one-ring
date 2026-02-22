from typing import TYPE_CHECKING

import pytest

from one_ring_loop.log import get_logger
from one_ring_loop.streams import (
    BrokenResourceError,
    ClosedResourceError,
    EndOfStreamError,
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
    create_memory_object_stream,
)
from one_ring_loop.task import TaskGroup

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


logger = get_logger(__name__)


class TestMemoryObjectSendStream:
    def test_send_receive(self, run_coro) -> None:
        def producer(send_stream: MemoryObjectSendStream[int]) -> Coro[None]:
            for i in range(1):
                yield from send_stream.send(i)
            yield from send_stream.close()

        def consumer(receive_stream: MemoryObjectReceiveStream[int]) -> Coro[None]:
            while True:
                yield from receive_stream.receive()

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()

            send_stream, receive_stream = create_memory_object_stream[int]()

            try:
                tg.create_task(consumer(receive_stream))
                tg.create_task(producer(send_stream))
                yield from tg.wait()
            finally:
                yield from tg.exit()

        with pytest.raises(BaseExceptionGroup) as exc_info:
            run_coro(entry())

        assert isinstance(exc_info.value.exceptions[0], EndOfStreamError)

    def test_clone_send_receive(self, run_coro) -> None:
        def producer(send_stream: MemoryObjectSendStream[int]) -> Coro[None]:
            for i in range(5):
                yield from send_stream.send(i)
            yield from send_stream.close()

        def consumer(receive_stream: MemoryObjectReceiveStream[int]) -> Coro[None]:
            while True:
                yield from receive_stream.receive()

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()

            send_stream, receive_stream = create_memory_object_stream[int]()

            try:
                tg.create_task(producer(send_stream))
                tg.create_task(producer(send_stream.clone()))
                tg.create_task(consumer(receive_stream))
                tg.create_task(consumer(receive_stream.clone()))
                yield from tg.wait()
            finally:
                yield from tg.exit()

        with pytest.raises(BaseExceptionGroup) as exc_info:
            run_coro(entry())

        assert isinstance(exc_info.value.exceptions[0], EndOfStreamError)

    def test_send_stream_raises_broken_resource_error(self, run_coro) -> None:
        def producer(send_stream: MemoryObjectSendStream[int]) -> Coro[None]:
            for i in range(5):
                yield from send_stream.send(i)
            yield from send_stream.close()

        def consumer(receive_stream: MemoryObjectReceiveStream[int]) -> Coro[None]:
            yield from receive_stream.receive()
            yield from receive_stream.close()

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()

            send_stream, receive_stream = create_memory_object_stream[int]()

            try:
                tg.create_task(producer(send_stream))
                tg.create_task(producer(send_stream.clone()))
                tg.create_task(consumer(receive_stream))
                tg.create_task(consumer(receive_stream.clone()))
                yield from tg.wait()
            finally:
                yield from tg.exit()

        with pytest.raises(BaseExceptionGroup) as exc_info:
            run_coro(entry())

        assert isinstance(exc_info.value.exceptions[0], BrokenResourceError)

    def test_send_stream_raises_closed_error(self, run_coro) -> None:
        def producer(send_stream: MemoryObjectSendStream[int]) -> Coro[None]:
            yield from send_stream.close()
            for i in range(5):
                yield from send_stream.send(i)

        def consumer(receive_stream: MemoryObjectReceiveStream[int]) -> Coro[None]:
            yield from receive_stream.receive()

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()

            send_stream, receive_stream = create_memory_object_stream[int]()

            try:
                tg.create_task(producer(send_stream))
                tg.create_task(producer(send_stream.clone()))
                tg.create_task(consumer(receive_stream))
                tg.create_task(consumer(receive_stream.clone()))
                yield from tg.wait()
            finally:
                yield from tg.exit()

        with pytest.raises(BaseExceptionGroup) as exc_info:
            run_coro(entry())

        assert isinstance(exc_info.value.exceptions[0], ClosedResourceError)

    def test_send_receive_raises_closed_error(self, run_coro) -> None:
        def producer(send_stream: MemoryObjectSendStream[int]) -> Coro[None]:
            for i in range(5):
                yield from send_stream.send(i)

        def consumer(receive_stream: MemoryObjectReceiveStream[int]) -> Coro[None]:
            yield from receive_stream.close()
            yield from receive_stream.receive()

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()

            send_stream, receive_stream = create_memory_object_stream[int]()

            try:
                tg.create_task(producer(send_stream))
                tg.create_task(producer(send_stream.clone()))
                tg.create_task(consumer(receive_stream))
                tg.create_task(consumer(receive_stream.clone()))
                yield from tg.wait()
            finally:
                yield from tg.exit()

        with pytest.raises(BaseExceptionGroup) as exc_info:
            run_coro(entry())

        assert isinstance(exc_info.value.exceptions[0], ClosedResourceError)
