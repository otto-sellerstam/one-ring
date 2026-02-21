from typing import TYPE_CHECKING

import pytest

from one_ring_loop.cancellation import fail_after, move_on_after
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


class TestFailAfter:
    def test_cancels_when_timeout_expires(self, run_coro, timing) -> None:
        def coro() -> Coro[None]:
            timing.start()
            with fail_after(0.1):
                yield from sleep(0.5)

        with pytest.raises(Cancelled):
            run_coro(coro())

        timing.assert_elapsed_between(
            0.05, 0.3, msg="fail_after(0.1) should fire near 0.1s"
        )

    def test_completes_when_work_finishes_first(self, run_coro, timing) -> None:
        def coro() -> Coro[None]:
            timing.start()
            with fail_after(0.2):
                yield from sleep(0.1)

        run_coro(coro())

        timing.assert_elapsed_between(0.05, 0.15, msg="fail_after shouldn't block")

    def test_cancel_scope_not_cancelled_on_normal_exit(self, run_coro) -> None:
        def coro() -> Coro[None]:
            with fail_after(0.5) as cancel_scope:
                yield from sleep(0.1)
            assert not cancel_scope.cancelled

        run_coro(coro())


class TestMoveOnAfter:
    def test_moves_on_when_timeout_expires(self, run_coro, timing) -> None:
        def coro() -> Coro[None]:
            timing.start()
            with move_on_after(0.1):
                yield from sleep(0.5)

        run_coro(coro())

        timing.assert_elapsed_between(
            0.05, 0.2, msg="move_on_after(0.1) should cancel silently near 0.1s"
        )

    def test_outer_scope_cancellation_propagates(self, run_coro) -> None:
        def coro() -> Coro[None]:
            with fail_after(0.1), move_on_after(0.5):
                yield from sleep(1)

        with pytest.raises(Cancelled):
            run_coro(coro())


class TestShielding:
    def test_shield_blocks_then_outer_scope_raises(self, run_coro, timing) -> None:
        def coro() -> Coro[None]:
            timing.start()
            with fail_after(0.1):
                with move_on_after(0.2, shield=True):
                    yield from sleep(0.5)
                yield from sleep(0.1)  # Should raise from outer fail_after

        with pytest.raises(Cancelled):
            run_coro(coro())

        timing.assert_elapsed_between(
            0.15, 0.5, msg="shield(0.2) protects inner, then outer raises"
        )

    def test_shield_protects_from_outer_cancellation(self, run_coro, timing) -> None:
        def coro() -> Coro[None]:
            timing.start()
            with fail_after(0.1), move_on_after(0.2, shield=True):
                yield from sleep(0.5)

        run_coro(coro())

        timing.assert_elapsed_between(
            0.15, 0.5, msg="shield absorbs both inner and outer cancellation"
        )
