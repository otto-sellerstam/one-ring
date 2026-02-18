from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_core.log import get_logger
from one_ring_loop.typedefs import NotDone, WaitsOn

if TYPE_CHECKING:
    from one_ring_core.operations import IOOperation
    from one_ring_core.results import IOCompletion
    from one_ring_loop.typedefs import Coro, TaskID

logger = get_logger(__name__)

_not_done = NotDone()


@dataclass
class Task[TResult]:
    """Drives coroutines forwards."""

    """The generator coroutine wrapped by the task."""
    gen: Coro = field(repr=False)

    """The ID of the task."""
    task_id: TaskID

    """If the task is currently waiting on the kernel to finish IO."""
    waiting: bool = field(default=False, init=False)

    # TODO: Make enum?
    """The current IO operation that is performed."""
    awaiting_operation: IOOperation | WaitsOn | None = field(default=None, init=False)

    """If the task has been started or not."""
    started: bool = field(default=False, init=False)

    """Final result of the task."""
    _result: TResult | NotDone = field(default=_not_done, init=False)

    def start(self) -> None:
        """Starts the task."""
        if self.started:
            msg = f"Task with task_id {self.task_id} already running"
            raise RuntimeError(msg)

        self.awaiting_operation = next(self.gen)
        self.started = True
        logger.info(
            "Set initial operation",
        )

    def drive(self, value: IOCompletion | None) -> None:
        """Drives the attached generator coroutine forwards."""
        self.waiting = False
        try:
            if value is None:
                self.awaiting_operation = next(self.gen)
            else:
                self.awaiting_operation = self.gen.send(value)
        except StopIteration as e:
            self._result = e.value

    @property
    def done(self) -> bool:
        """If a task has finished."""
        return not isinstance(self._result, NotDone)

    @property
    def result(self) -> TResult:
        """Gets the result of a finished task."""
        if isinstance(self._result, NotDone):
            raise RuntimeError("Task result access before task was finished")  # noqa: TRY004

        return self._result

    def wait(self) -> Coro[TResult]:
        """Waits on a Task, so that another Task can yield from it."""
        yield from _wait_on(self)
        return self.result


def _wait_on(*tasks: Task) -> Coro[None]:
    """Yield until all given tasks are done.

    Args:
        tasks: the tasks for which we want to wait for
    """
    while not all(task.done for task in tasks):
        unfinished = tuple(task.task_id for task in tasks if not task.done)
        yield WaitsOn(unfinished)
