from typing import TYPE_CHECKING

from one_ring_loop._utils import _local
from one_ring_loop.operations import Checkpoint

if TYPE_CHECKING:
    from one_ring_loop.loop import Loop
    from one_ring_loop.task import Task
    from one_ring_loop.typedefs import Coro, TaskID


def get_running_loop() -> Loop:
    """Gets the currently running event loop. I don't want to expose this easily."""
    if _local.loop is None:
        raise RuntimeError("No event loop running")

    return _local.loop


def get_current_task() -> Task:
    """Gets the currently executing task from the loop."""
    return get_running_loop().current_task


def unpark(task_id: TaskID) -> None:
    """Unparks a parked task.

    Args:
        task_id: The id of the task to unpark
    """
    _local.unpark_queue.append(task_id)


def checkpoint() -> Coro[None]:
    """Nop that yields control back to event loop."""
    yield Checkpoint()
