from typing import TYPE_CHECKING

from one_ring_core.operations import Sleep
from one_ring_core.results import (
    SleepResult,
)

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def sleep(time: int) -> Coro[bool]:
    """Test file open coroutine."""
    sleep_completion = yield Sleep(time)
    if sleep_completion is not None and isinstance(
        result := sleep_completion.unwrap(), SleepResult
    ):
        return result.success

    raise ValueError("sleep received wrong result type")
