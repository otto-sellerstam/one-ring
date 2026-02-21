from typing import TYPE_CHECKING

from one_ring_loop.sync_primitives import Event, Lock, Semaphore
from one_ring_loop.task import TaskGroup
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


class TestEvent:
    def test_wait_blocks_until_set(self, run_coro) -> None:
        def coro1(event: Event) -> Coro[None]:
            yield from sleep(0.1)
            event.set()
            yield from sleep(0.1)

        def coro2(event: Event) -> Coro[None]:
            yield from event.wait()
            yield from sleep(0.1)

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

        run_coro(entry())


class TestLock:
    def test_serializes_concurrent_tasks(self, run_coro, timing) -> None:
        def coro(lock: Lock) -> Coro[None]:
            yield from lock.acquire()
            yield from sleep(0.1)
            lock.release()

        def entry() -> Coro[None]:
            tg = TaskGroup()

            lock = Lock()

            timing.start()
            tg.enter()
            try:
                tg.create_task(coro(lock))
                tg.create_task(coro(lock))
                tg.create_task(coro(lock))
                yield from tg.wait()
            finally:
                yield from tg.exit()

        run_coro(entry())

        timing.assert_elapsed_between(
            0.3, 0.4, msg="3 tasks each holding lock for 0.1s"
        )


class TestSemaphore:
    def test_serializes_concurrent_tasks(self, run_coro, timing) -> None:
        def coro(semaphore: Semaphore, time: float) -> Coro[None]:
            yield from semaphore.acquire()
            yield from sleep(time)
            semaphore.release()
            yield from sleep(0)

        def entry() -> Coro[None]:
            tg = TaskGroup()

            semaphore = Semaphore(2)

            timing.start()
            tg.enter()
            try:
                tg.create_task(coro(semaphore, 0.1))
                tg.create_task(coro(semaphore, 0.2))
                tg.create_task(coro(semaphore, 0.1))
                yield from tg.wait()
            finally:
                yield from tg.exit()

        run_coro(entry())

        timing.assert_elapsed_between(
            0.2,
            0.25,
            msg=(
                "Semaphore(2) should let two tasks sleep concurrently, and the last"
                " task should depend on the first"
            ),
        )
