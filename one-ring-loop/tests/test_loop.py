from __future__ import annotations

import time
from typing import TYPE_CHECKING

from one_ring_loop.loop import create_task, gather
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def _gather() -> Coro:
    sleep_task1 = create_task(sleep(1))
    sleep_task2 = create_task(sleep(1))

    start_time = time.monotonic()
    yield from gather(sleep_task1, sleep_task2)

    assert time.monotonic() - start_time < 2


def _task_wait() -> Coro:
    sleep_task = create_task(sleep(1))
    success = yield from sleep_task.wait()
    assert success


def test_tasks() -> None:
    _gather()
    _task_wait()
