from __future__ import annotations

from typing import TYPE_CHECKING

from one_ring_core.results import IOResult

if TYPE_CHECKING:
    from one_ring_core.operations import IOOperation
    from one_ring_loop.typedefs import Coro


def _execute[T: IOResult](op: IOOperation[T]) -> Coro[T]:
    """Unwrap an IO completion into the expected result type."""
    expected = op.result_type
    completion = yield op
    if completion is not None and isinstance(result := completion.unwrap(), expected):
        return result
    msg = f"Expected {expected.__name__}, got {type(completion)}"
    raise TypeError(msg)
