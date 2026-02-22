from collections import deque
from typing import TYPE_CHECKING

import pytest

from one_ring_loop.log import get_logger
from one_ring_loop.sync_primitives import Condition, Event, Lock, Semaphore
from one_ring_loop.task import TaskGroup
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from collections.abc import Callable

    from one_ring_loop.typedefs import Coro


logger = get_logger(__name__)


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
            try:
                yield from sleep(0.1)
            finally:
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

    def test_release_without_lock_raises(self, run_coro) -> None:
        def entry() -> Coro[None]:
            yield from sleep(0)
            lock = Lock()
            lock.release()

        with pytest.raises(
            RuntimeError, match="Task not owning the lock attempted release"
        ):
            run_coro(entry())

    def test_locked(self, run_coro) -> None:
        def entry() -> Coro[None]:
            lock = Lock()
            yield from lock.acquire()
            try:
                assert lock.locked()
            finally:
                lock.release()

            assert not lock.locked()

        run_coro(entry())


class TestSemaphore:
    def test_serializes_concurrent_tasks(self, run_coro, timing) -> None:
        def coro(semaphore: Semaphore, time: float) -> Coro[None]:
            yield from semaphore.acquire()
            try:
                yield from sleep(time)
            finally:
                semaphore.release()

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

    def test_semaphore_nothing_to_release_raises(self, run_coro) -> None:
        def entry() -> Coro[None]:
            yield from sleep(0)
            semaphore = Semaphore(2)
            semaphore.release()

        with pytest.raises(RuntimeError, match="Nothing to release"):
            run_coro(entry())


class TestCondition:
    def test_waits_for_predicate(self, run_coro, timing) -> None:
        def coro_wait(
            condition: Condition, queue: deque[int], expected: int
        ) -> Coro[None]:
            yield from condition.acquire()
            try:
                while not queue:
                    yield from condition.wait()

                assert queue.popleft() == expected
            finally:
                condition.release()

        def coro_notify(
            condition: Condition, queue: deque[int], value: int
        ) -> Coro[None]:
            yield from condition.acquire()
            try:
                queue.append(value)
                condition.notify(1)
            finally:
                condition.release()

        def entry() -> Coro[None]:
            tg = TaskGroup()

            condition = Condition()
            queue: deque[int] = deque()

            timing.start()
            tg.enter()
            try:
                tg.create_task(coro_wait(condition, queue, 1))
                tg.create_task(coro_wait(condition, queue, 2))
                tg.create_task(coro_notify(condition, queue, 1))
                tg.create_task(coro_notify(condition, queue, 2))
                yield from tg.wait()
            finally:
                yield from tg.exit()

        run_coro(entry())

    def test_notify_no_waiters(self, run_coro) -> None:
        def entry() -> Coro[None]:
            condition = Condition()
            yield from condition.acquire()
            condition.notify(1)  # should not raise
            condition.notify_all()  # should not raise
            condition.release()

        run_coro(entry())

    def test_requeue_ordering(self, run_coro) -> None:
        results: list[str] = []

        def waiter(condition: Condition, name: str, predicate: Callable) -> Coro[None]:
            yield from condition.acquire()
            try:
                while not predicate():
                    yield from condition.wait()

                results.append(name)
            finally:
                condition.release()

        def notifier(condition: Condition, state: dict) -> Coro[None]:
            yield from condition.acquire()
            try:
                state["value"] = "B"
                condition.notify_all()
            finally:
                condition.release()

            # Second notify: now "A" matches
            yield from condition.acquire()
            try:
                state["value"] = "A"
                condition.notify_all()
            finally:
                condition.release()

        def entry() -> Coro[None]:
            tg = TaskGroup()
            condition = Condition()
            state = {"value": None}
            tg.enter()
            try:
                tg.create_task(waiter(condition, "A", lambda: state["value"] == "A"))
                tg.create_task(waiter(condition, "B", lambda: state["value"] == "B"))
                tg.create_task(notifier(condition, state))
                yield from tg.wait()
            finally:
                yield from tg.exit()
            assert results == ["B", "A"]

        run_coro(entry())

    def test_notify_without_lock_raises(self, run_coro) -> None:
        def entry() -> Coro[None]:
            yield from sleep(0)
            condition = Condition()
            with pytest.raises(RuntimeError):
                condition.notify()

        run_coro(entry())
