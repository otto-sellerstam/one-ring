from typing import TYPE_CHECKING

from one_ring_core.operations import Sleep
from one_ring_core.results import (
    SleepResult,
)

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def sleep(time: int) -> Coro[None]:
    """Test file open coroutine."""
    sleep_completion = yield Sleep(time)
    if sleep_completion is not None and isinstance(
        sleep_completion.unwrap(), SleepResult
    ):
        return None

    raise ValueError("sleep received wrong result type")
