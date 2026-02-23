from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from one_ring_core.results import IOResult

if TYPE_CHECKING:
    from one_ring_core.operations import IOOperation
    from one_ring_loop.loop import Loop
    from one_ring_loop.typedefs import Coro, TaskID


def _get_new_operation_id() -> TaskID:
    """Gets an unused ID to submit to the IO worker."""
    ret = _local.free_operation_id
    _local.free_operation_id += 1

    return ret


def _execute[T: IOResult](op: IOOperation[T]) -> Coro[T]:
    """Unwrap an IO completion into the expected result type."""
    expected = op.result_type
    completion = yield cast("IOOperation[IOResult]", op)
    if completion is not None and isinstance(result := completion.unwrap(), expected):
        return result
    elif completion is None:
        raise RuntimeError("Low level coroutine was sent None")

    msg = f"Expected {expected.__name__}, got {type(completion)}. Expected {expected}"
    raise TypeError(msg)


@dataclass(kw_only=True)
class _Local(threading.local):
    """Wrapper around threading.local for proper type annotations."""

    loop: Loop | None = None
    free_operation_id: int = 1

    # TODO: Move the below two to be attributes on Loop.
    cancel_queue: deque[TaskID] = field(default_factory=deque)
    unpark_queue: deque[TaskID] = field(default_factory=deque)

    def cleanup(self) -> None:
        """Resets all attributes."""
        self.loop = None
        self.free_operation_id = 1

        self.cancel_queue = deque()
        self.unpark_queue = deque()


_local = _Local()

__all__ = [
    "_execute",
    "_get_new_operation_id",
    "_local",
]
