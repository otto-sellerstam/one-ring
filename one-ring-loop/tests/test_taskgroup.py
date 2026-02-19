import time
from typing import TYPE_CHECKING

import pytest

from one_ring_loop.loop import run
from one_ring_loop.task import TaskGroup
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def test_taskgroup_raises_exception_group() -> None:
    def sleep_with_error(time: int, error_type: type[BaseException]) -> Coro[None]:
        yield from sleep(time)
        raise error_type("Oopsie!")

    def run_taskgroup(tg: TaskGroup) -> Coro[None]:
        start_time = time.monotonic()
        try:
            tg.create_task(sleep_with_error(2, RuntimeError))
            tg.create_task(sleep_with_error(2, ValueError))
            yield from sleep(4)
            yield from sleep(5)
            yield from tg.wait()
        finally:
            assert time.monotonic() - start_time < 2.1
            yield from tg.exit()

    def entry() -> Coro[None]:
        tg = TaskGroup()
        tg.enter()
        with pytest.raises(BaseExceptionGroup) as exc_info:
            yield from run_taskgroup(tg)

        assert len(exc_info.value.exceptions) == 2
        assert isinstance(exc_info.value.exceptions[0], ValueError)
        assert isinstance(exc_info.value.exceptions[1], RuntimeError)

        start_time = time.monotonic()
        yield from sleep(2)
        assert time.monotonic() - start_time < 2.1

    run(entry())


def test_taskgroup_raises_exception_group_during_start() -> None:
    def sleep_with_error(time: int, error_type: type[BaseException]) -> Coro[None]:
        raise error_type("Oopsie!")
        yield from sleep(2)  # pyrefly: ignore

    def run_taskgroup(tg: TaskGroup) -> Coro[None]:
        start_time = time.monotonic()
        try:
            tg.create_task(sleep_with_error(2, RuntimeError))
            tg.create_task(sleep_with_error(2, ValueError))
            yield from sleep(4)
            yield from sleep(5)
            yield from tg.wait()
        finally:
            assert time.monotonic() - start_time < 2.1
            yield from tg.exit()

    def entry() -> Coro[None]:
        tg = TaskGroup()
        tg.enter()
        with pytest.raises(BaseExceptionGroup) as exc_info:
            yield from run_taskgroup(tg)

        assert len(exc_info.value.exceptions) == 2
        assert isinstance(exc_info.value.exceptions[0], RuntimeError)
        assert isinstance(exc_info.value.exceptions[1], ValueError)

        start_time = time.monotonic()
        yield from sleep(2)
        assert time.monotonic() - start_time < 2.1

    run(entry())


if __name__ == "__main__":
    test_taskgroup_raises_exception_group_during_start()
