from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

from one_ring_core.operations import IOOperation
from one_ring_core.results import IOCompletion, IOResult
from one_ring_core.typedefs import WorkerOperationID

if TYPE_CHECKING:
    from one_ring_loop.operations import Park, WaitsOn


type TaskID = WorkerOperationID

# TODO: Define an "Operation" type, including all operations suppported by the loop.
type Coro[T] = Generator[IOOperation | WaitsOn | Park, IOCompletion[IOResult] | None, T]
