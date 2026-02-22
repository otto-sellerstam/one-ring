"""This namespace includes extra operations for the event loop.

This extends the operations provided by one_ring_core.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from one_ring_loop.typedefs import TaskID


@dataclass
class WaitsOn:
    """For dependency relationships between tasks."""

    task_ids: tuple[TaskID, ...]


@dataclass
class Park:
    """Parks the yielding task until resumed by another task."""


@dataclass
class Checkpoint:
    """Sentinel that yields control back to event loop."""
