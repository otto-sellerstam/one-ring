from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_loop._utils import _local
from one_ring_loop.log import get_logger

if TYPE_CHECKING:
    from one_ring_loop.typedefs import TaskID

logger = get_logger(__name__)


@dataclass
class CancelScope:
    """Cancel scope, inspired by Trio."""

    """Whether the cancel scope is cancelled or not"""
    cancelled: bool = field(default=False, init=False)

    """IDs of the tasks within the cancel scope."""
    task_ids: set[TaskID] = field(default_factory=set, init=False)

    def cancel(self) -> None:
        """Cancels the cancel scope."""
        self.cancelled = True
        _local.cancel_queue.extend(self.task_ids)

    def add_task(self, task_id: TaskID) -> None:
        """Adds a task to the cancel scope."""
        self.task_ids.add(task_id)

    def remove_task(self, task_id: TaskID) -> None:
        """Removes a task from the cancel scope."""
        self.task_ids.remove(task_id)
