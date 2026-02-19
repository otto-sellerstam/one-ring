from __future__ import annotations

import time
from typing import TYPE_CHECKING

from one_ring_loop.task import TaskGroup
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def _gather() -> Coro:
    tg = TaskGroup()
    tg.enter()

    try:
        tg.create_task(sleep(1))
        tg.create_task(sleep(1))

        yield from tg.wait()
        start_time = time.monotonic()
        assert time.monotonic() - start_time < 2
    finally:
        yield from tg.exit()


def test_tasks() -> None:
    _gather()
