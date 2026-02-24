from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from one_ring_loop.typedefs import EventLoopOperation


@dataclass(slots=True, kw_only=True)
class Created:
    """Task exists but hasn't been started."""


@dataclass(slots=True, kw_only=True)
class Ready:
    """Task has been driven and produced an operation."""

    operation: EventLoopOperation


@dataclass(slots=True)
class Submitted:
    """Loop has processed the operation. Task is blocked until woken."""

    operation: EventLoopOperation
    op_id: int | None = None  # Only set for kernel IO operations


@dataclass(slots=True, kw_only=True)
class Done[T]:
    """Task has finished."""

    result: T | BaseException


type TaskState[T] = Created | Ready | Submitted | Done[T]
