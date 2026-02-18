from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import override

from one_ring_core.operations import IOOperation
from one_ring_core.results import IOCompletion, IOResult
from one_ring_core.typedefs import WorkerOperationID


class NotDone:
    """Sentinal for unfinished Task."""

    @override
    def __repr__(self) -> str:
        """Pretty printing."""
        return "NotDone"


@dataclass
class WaitsOn:
    """Sentinel for dependency relationships between tasks."""

    task_id: int


type TaskID = WorkerOperationID
type Coro[T] = Generator[IOOperation | WaitsOn, IOCompletion[IOResult] | None, T]
