from __future__ import annotations

from typing import TYPE_CHECKING

from one_ring_loop.loop import run
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def entry() -> Coro:
    success = yield from sleep(1)
    assert success


def test_fileio() -> None:
    run(entry())


test_fileio()
