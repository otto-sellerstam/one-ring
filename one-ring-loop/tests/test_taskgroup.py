import time
from typing import TYPE_CHECKING

import pytest

from one_ring_loop.loop import run
from one_ring_loop.task import TaskGroup
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def sleep_with_error(time: int) -> Coro[None]:
    yield from sleep(2)
    raise RuntimeError("Oopsie!")


def run_taskgroup(tg: TaskGroup) -> Coro[None]:
    start_time = time.monotonic()
    try:
        tg.create_task(sleep_with_error(2))
        tg.create_task(sleep(3))
        yield from sleep(4)
        yield from sleep(5)
        yield from tg.wait()
    finally:
        assert time.monotonic() - start_time < 2.1
        yield from tg.exit()


def entry() -> Coro[None]:
    tg = TaskGroup()
    tg.enter()
    with pytest.raises(RuntimeError, match="Oopsie!"):
        yield from run_taskgroup(tg)

    start_time = time.monotonic()
    yield from sleep(2)
    assert time.monotonic() - start_time < 2.1


def test_taskgroup() -> None:
    run(entry())


test_taskgroup()
