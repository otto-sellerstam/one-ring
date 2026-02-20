import time
from typing import TYPE_CHECKING

import pytest

from one_ring_loop.cancellation import fail_after, move_on_after
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.loop import run
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def test_fails_after() -> None:
    def entry() -> Coro[None]:
        start_time = time.monotonic()
        try:
            with fail_after(1):
                yield from sleep(2)
        finally:
            assert time.monotonic() - start_time < 2

    with pytest.raises(Cancelled):
        run(entry())


def test_move_on_after() -> None:
    def entry() -> Coro[None]:
        start_time = time.monotonic()
        with move_on_after(1):
            yield from sleep(2)

        assert time.monotonic() - start_time < 2

    run(entry())


if __name__ == "__main__":
    test_fails_after()
    test_move_on_after()
