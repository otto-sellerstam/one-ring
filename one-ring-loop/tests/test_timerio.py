from typing import TYPE_CHECKING

from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def test_sleep(run_coro) -> None:
    def coro() -> Coro:
        yield from sleep(0.1)

    run_coro(coro())
