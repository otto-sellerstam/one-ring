from contextlib import contextmanager
from typing import TYPE_CHECKING

from one_ring_loop.exceptions import Cancelled
from one_ring_loop.log import get_logger
from one_ring_loop.task import CancelScope, _create_standalone_task
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from collections.abc import Generator

    from one_ring_loop.typedefs import Coro

logger = get_logger(__name__)


@contextmanager
def fail_after(delay: float, *, shield: bool = False) -> Generator[CancelScope]:
    """Cancels cancel scope and throws Cancelled after delay."""

    def cancellation_task(cancel_scope: CancelScope) -> Coro[None]:
        """Background task that sleeps for delay.

        Cancels the cancel scope if not finished after sleep.
        """
        yield from sleep(delay)
        if not finished:
            cancel_scope.cancel()

    finished = False
    with CancelScope(shielded=shield) as scope:
        _create_standalone_task(cancellation_task(scope), None, None)
        yield scope
    finished = True


@contextmanager
def move_on_after(delay: float, *, shield: bool = False) -> Generator[CancelScope]:
    """Moves on after delay by catching Cancelled."""
    with fail_after(delay, shield=shield) as cancel_scope:
        try:
            yield cancel_scope
        except Cancelled:
            if not cancel_scope.cancelled:
                # Another scope cancelled from above. Re-raise.
                raise
