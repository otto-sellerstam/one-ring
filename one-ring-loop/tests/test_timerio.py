from __future__ import annotations

from typing import TYPE_CHECKING

from one_ring_loop.loop import run
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def test_sleep() -> None:
    def entry() -> Coro:
        yield from sleep(1)

    run(entry())
