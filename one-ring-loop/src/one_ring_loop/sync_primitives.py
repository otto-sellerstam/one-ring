from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_loop.log import get_logger
from one_ring_loop.lowlevel import get_current_task, unpark
from one_ring_loop.operations import Park
from one_ring_loop.timerio import sleep

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro, TaskID

# TODO: For fun, implement BoundedSemaphore and Barrier.

logger = get_logger()


@dataclass(slots=True, kw_only=True)
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


@dataclass(slots=True, kw_only=True)
class Lock:
    """Lock primitive (classic mutex)."""

    """ID of the task currently holding the lock."""
    owner: TaskID | None = field(default=None, init=False, repr=False)

    _semaphore: Semaphore = field(
        default_factory=lambda: Semaphore(initial_value=1), init=False
    )

    def acquire(self) -> Coro[None]:
        """Attempts to acquire the lock."""
        yield from self._semaphore.acquire()
        self.owner = get_current_task().task_id

    def release(self) -> None:
        """Releases the lock for the next task to acquire it."""
        if not self.owner == get_current_task().task_id:
            raise RuntimeError("Task not owning the lock attempted release")
        self._semaphore.release()
        self.owner = None

    def locked(self) -> bool:
        """Checks if the lock is currently held."""
        return self._semaphore.value == 1


@dataclass(slots=True, kw_only=True)
class Semaphore:
    """Semaphore primitive."""

    """Max number of entries without release allowed."""
    initial_value: int

    _events: deque[Event] = field(default_factory=deque, init=False)

    def acquire(self) -> Coro[None]:
        """Attempts to acquire the lock."""
        yield from sleep(0)
        event = Event()
        self._events.append(event)

        if len(self._events) - 1 >= self.initial_value:
            dependant_event = self._events[-(self.initial_value + 1)]
            yield from dependant_event.wait()

    def release(self) -> None:
        """Releases the semaphore for the next task to acquire it."""
        try:
            self._events.popleft().set()
        except IndexError as e:
            raise RuntimeError("Nothing to release") from e

    @property
    def value(self) -> int:
        """Returns the current number of entries without releases."""
        return len(self._events)


@dataclass(slots=True, kw_only=True)
class Condition:
    """Trio style Condition primitive."""

    """The lock object to use internally"""
    lock: Lock = field(default_factory=Lock)

    _events: deque[Event] = field(default_factory=deque, init=False)

    def acquire(self) -> Coro[None]:
        """Acquires the underlying lock."""
        yield from self.lock.acquire()

    def notify(self, n: int = 1, /) -> None:
        """Wakes up one more more tasks that are blocked in `wait`."""
        if not self.lock.owner == get_current_task().task_id:
            raise RuntimeError("Calling task does not hold condition lock")
        for _ in range(min(n, len(self._events))):
            event = self._events.popleft()
            event.set()

    def notify_all(self) -> None:
        """Wakes up all tasks that are blocked in `wait`."""
        self.notify(len(self._events))

    def release(self) -> None:
        """Releases the underlying lock."""
        self.lock.release()

    def wait(self) -> Coro[None]:
        """Waits for a respective `notify` call."""
        self.lock.release()
        event = Event()
        self._events.append(event)
        yield from event.wait()
        yield from self.lock.acquire()
