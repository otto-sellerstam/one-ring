import time
from typing import TYPE_CHECKING

from one_ring_loop.loop import run
from one_ring_loop.sync_primitives import Event, Lock
from one_ring_loop.task import TaskGroup
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def test_event() -> None:
    def coro1(event: Event) -> Coro[None]:
        yield from sleep(1)
        event.set()
        yield from sleep(1)

    def coro2(event: Event) -> Coro[None]:
        yield from event.wait()
        yield from sleep(1)

    def entry() -> Coro[None]:
        tg = TaskGroup()
        tg.enter()

        event = Event()

        try:
            tg.create_task(coro1(event))
            yield from event.wait()
            tg.create_task(coro2(event))
            yield from tg.wait()
        finally:
            yield from tg.exit()

    run(entry())


def test_lock() -> None:
    def coro(lock: Lock) -> Coro[None]:
        yield from lock.acquire()
        yield from sleep(1)
        lock.release()
        yield from sleep(0.1)

    def entry() -> Coro[None]:
        tg = TaskGroup()

        lock = Lock()

        start_time = time.monotonic()
        tg.enter()
        try:
            tg.create_task(coro(lock))
            tg.create_task(coro(lock))
            tg.create_task(coro(lock))
            yield from tg.wait()
            assert time.monotonic() - start_time >= 3
        finally:
            yield from tg.exit()

    run(entry())


if __name__ == "__main__":
    test_lock()
