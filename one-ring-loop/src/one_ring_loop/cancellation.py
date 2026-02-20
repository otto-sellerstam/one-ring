from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_loop.exceptions import Cancelled
from one_ring_loop.log import get_logger
from one_ring_loop.lowlevel import get_current_task
from one_ring_loop.task import CancelScope, _create_standalone_task
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from collections.abc import Generator

    from one_ring_loop.typedefs import Coro

logger = get_logger(__name__)


@dataclass
class _FailAfter:
    """Class based implementation of fail_after.

    Throws a Cancelled exception after timeout.
    """

    """The delay for the timeout."""
    delay: float

    """Internal time check."""
    _finished: bool = field(default=False, init=False)

    def _cancellation_task(self, cancel_scope: CancelScope) -> Coro[None]:
        """Background task that sleeps for delay.

        Cancels the cancel scope if not self._finished after sleep.
        """
        yield from sleep(self.delay)
        if not self._finished:
            cancel_scope.cancel()

    def start(self) -> None:
        """Starts a background task which checks for timeout."""
        self._finished = False
        cancel_scope = get_current_task().current_cancel_scope()

        _create_standalone_task(self._cancellation_task(cancel_scope), None, None)

    def end(self) -> None:
        """Registers the timeout block as finished.

        Note: this does not cancel the cancellation task, which is a potential resource
        leak, but I don't think it should matter.
        """
        self._finished = True


@contextmanager
def fail_after(delay: float) -> Generator:
    """Cancels cancel scope and throws Cancelled after delay."""
    _fail_after = _FailAfter(delay=delay)
    _fail_after.start()
    try:
        yield
    finally:
        _fail_after.end()


@contextmanager
def move_on_after(delay: float) -> Generator:
    """Moves on after delay by catching Cancelled."""
    with suppress(Cancelled), fail_after(delay):
        yield
