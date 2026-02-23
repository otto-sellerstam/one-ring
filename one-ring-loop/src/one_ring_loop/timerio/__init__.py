from typing import TYPE_CHECKING

from one_ring_core.operations import Sleep
from one_ring_loop._utils import _execute
from one_ring_loop.lowlevel import checkpoint

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def sleep(time: float) -> Coro[None]:
    """Sleep coroutine."""
    if time == 0:
        yield from checkpoint()
    else:
        yield from _execute(Sleep(time=time))
    return None
