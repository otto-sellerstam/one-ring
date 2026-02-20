from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_loop.lowlevel import get_current_task, unpark
from one_ring_loop.operations import Park

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro, TaskID

# TODO: For fun, implement Condition, Semaphore, BoundedSemaphore and Barrier.


@dataclass
class Event:
    """Event primitive."""

    """Whether wait will block or not."""
    ready: bool = field(default=False, init=False)

    """Internally used to unpark."""
    _task_id: TaskID | None = field(default=None, init=False)

    def set(self) -> None:
        """Sets the event as ready, and unparks related task."""
        self.ready = True
        if self._task_id is not None:
            unpark(self._task_id)

    def wait(self) -> Coro[None]:
        """Parks the executing task until unparked."""
        if self.ready:
            return

        self._task_id = get_current_task().task_id

        yield Park()


@dataclass
class Lock:
    """Lock primitive."""

    _events: deque[Event] = field(default_factory=deque, init=False)

    def acquire(self) -> Coro[None]:
        """Attempts to acquire the lock."""
        if self._events:
            dependant_event = self._events[-1]
            event = Event()
            self._events.append(event)
            yield from dependant_event.wait()
        else:
            event = Event()
            self._events.append(event)

    def release(self) -> None:
        """Releases the lock for the next task to acquire it."""
        try:
            self._events.popleft().set()
        except IndexError as e:
            raise RuntimeError("Nothing to release") from e
