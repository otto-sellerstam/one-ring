from typing import TYPE_CHECKING

import pytest

from one_ring_loop.exceptions import Cancelled
from one_ring_loop.task import TaskGroup
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


class TestTaskGroup:
    def test_raises_exception_group_from_task(self, run_coro, timing) -> None:
        def sleep_with_error(
            duration: float, error_type: type[BaseException]
        ) -> Coro[None]:
            yield from sleep(duration)
            raise error_type("Oopsie!")

        def run_taskgroup(tg: TaskGroup) -> Coro[None]:
            timing.start()
            try:
                tg.create_task(sleep_with_error(0.2, RuntimeError))
                tg.create_task(sleep_with_error(0.2, ValueError))
                yield from sleep(0.4)
                yield from sleep(0.5)
                yield from tg.wait()
            finally:
                yield from tg.exit()

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            with pytest.raises(BaseExceptionGroup) as exc_info:
                yield from run_taskgroup(tg)

            assert len(exc_info.value.exceptions) == 2
            assert isinstance(exc_info.value.exceptions[0], ValueError | RuntimeError)
            assert isinstance(exc_info.value.exceptions[1], ValueError | RuntimeError)

            timing.start()
            yield from sleep(0.2)
            timing.assert_elapsed_between(
                0.1, 0.4, msg="sleep after exception group should work normally"
            )

        run_coro(entry())

    def test_raises_exception_group_during_start(self, run_coro, timing) -> None:
        def sleep_with_error(
            duration: float, error_type: type[BaseException]
        ) -> Coro[None]:
            raise error_type("Oopsie!")
            yield from sleep(0.2)  # pyrefly: ignore

        def run_taskgroup(tg: TaskGroup) -> Coro[None]:
            timing.start()
            try:
                tg.create_task(sleep_with_error(0.2, RuntimeError))
                tg.create_task(sleep_with_error(0.2, ValueError))
                yield from sleep(0.4)
                yield from sleep(0.5)
                yield from tg.wait()
            finally:
                yield from tg.exit()

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            with pytest.raises(BaseExceptionGroup) as exc_info:
                yield from run_taskgroup(tg)

            assert len(exc_info.value.exceptions) == 2
            assert isinstance(exc_info.value.exceptions[0], RuntimeError)
            assert isinstance(exc_info.value.exceptions[1], ValueError)

            timing.start()
            yield from sleep(0.2)
            timing.assert_elapsed_between(
                0.1, 0.4, msg="sleep after exception group should work normally"
            )

        run_coro(entry())

    def test_raises_exception_group_from_group(self, run_coro, timing) -> None:
        def sleep_with_error(
            duration: float, error_type: type[BaseException]
        ) -> Coro[None]:
            yield from sleep(0.2)
            raise error_type("Oopsie!")

        def run_taskgroup(tg: TaskGroup) -> Coro[None]:
            timing.start()
            try:
                tg.create_task(sleep(0.4))
                yield from sleep_with_error(0.2, RuntimeError)
                yield from tg.wait()
            finally:
                yield from tg.exit()

        def entry() -> Coro[None]:
            tg = TaskGroup()
            tg.enter()
            with pytest.raises(BaseExceptionGroup) as exc_info:
                yield from run_taskgroup(tg)

            assert len(exc_info.value.exceptions) == 1
            assert isinstance(exc_info.value.exceptions[0], Cancelled)

            timing.start()
            yield from sleep(0.2)
            timing.assert_elapsed_between(
                0.1, 0.4, msg="sleep after exception group should work normally"
            )

        run_coro(entry())
