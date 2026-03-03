import time
from typing import TYPE_CHECKING

import pytest

from one_ring_loop.task import TaskGroup
from one_ring_loop.threadpool import run_in_thread

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def test_threads_do_not_block(run_coro, timing) -> None:
    def sleep(timeout: float) -> None:
        time.sleep(timeout)

    def entry() -> Coro[None]:
        tg = TaskGroup()
        tg.enter()
        try:
            timing.start()
            tg.create_task(run_in_thread(sleep, 0.2))
            tg.create_task(run_in_thread(sleep, 0.1))
            yield from tg.wait()
        finally:
            yield from tg.exit()

    run_coro(entry())
    timing.assert_elapsed_between(0.2, 0.21, msg="Threads should not block")


def test_threads_raises(run_coro, timing) -> None:
    def sleep(timeout: float) -> None:
        time.sleep(timeout)
        raise RuntimeError("Oopsie")

    def entry() -> Coro[None]:
        tg = TaskGroup()
        tg.enter()
        try:
            timing.start()
            tg.create_task(run_in_thread(sleep, 0.2))
            tg.create_task(run_in_thread(sleep, 0.1))
            yield from tg.wait()
        finally:
            yield from tg.exit()

    with pytest.raises(ExceptionGroup) as exc_info:
        run_coro(entry())

    assert len(exc_info.value.exceptions) == 1
    assert isinstance(exc_info.value.exceptions[0], RuntimeError)
