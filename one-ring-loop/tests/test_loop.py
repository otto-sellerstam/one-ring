from __future__ import annotations

import time
from typing import TYPE_CHECKING

from one_ring_loop.loop import create_task, join, run
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def entry() -> Coro:
    sleep1 = create_task(sleep(1))
    sleep2 = create_task(sleep(1))

    start_time = time.monotonic()
    yield from join(sleep1)
    yield from join(sleep2)

    assert time.monotonic() - start_time < 2


def test_tasks() -> None:
    run(entry())


test_tasks()
