from typing import TYPE_CHECKING

from one_ring_core.operations import Sleep
from one_ring_core.results import SleepResult
from one_ring_loop.typedefs import _execute

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def sleep(time: int) -> Coro[None]:
    """Sleep coroutine."""
    yield from _execute(Sleep(time), SleepResult)
    return None
