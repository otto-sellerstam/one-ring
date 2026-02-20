import time
from typing import TYPE_CHECKING

import pytest

from one_ring_loop.cancellation import fail_after, move_on_after
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.loop import run
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def test_fails_after_raises() -> None:
    def entry() -> Coro[None]:
        start_time = time.monotonic()
        try:
            with fail_after(1):
                yield from sleep(2)
        finally:
            assert time.monotonic() - start_time < 2

    with pytest.raises(Cancelled):
        run(entry())


def test_fails_after_does_not_raise() -> None:
    def entry() -> Coro[None]:
        start_time = time.monotonic()
        try:
            with fail_after(2):
                yield from sleep(1)
        finally:
            assert time.monotonic() - start_time < 2

    run(entry())


def test_fails_after_does_not_cancel() -> None:
    def entry() -> Coro[None]:
        with fail_after(2) as cancel_scope:
            yield from sleep(1)
        yield from sleep(2)  # Wait for the internal background task to finish.
        assert not cancel_scope.cancelled

    run(entry())


def test_move_on_after() -> None:
    def entry() -> Coro[None]:
        start_time = time.monotonic()
        with move_on_after(1):
            yield from sleep(2)

        assert time.monotonic() - start_time < 2

    run(entry())


def test_move_on_after_cancels_from_outer_scope() -> None:
    def entry() -> Coro[None]:
        start_time = time.monotonic()
        with fail_after(1), move_on_after(2):
            yield from sleep(3)

        assert time.monotonic() - start_time < 2

    with pytest.raises(Cancelled):
        run(entry())


if __name__ == "__main__":
    # test_fails_after_raises()
    # test_fails_after_does_not_raise()
    # test_fails_after_does_not_cancel()
    # test_move_on_after()
    test_move_on_after_cancels_from_outer_scope()
