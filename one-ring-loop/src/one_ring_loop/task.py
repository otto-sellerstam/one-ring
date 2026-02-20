from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, overload, override

from one_ring_core.log import get_logger
from one_ring_loop._utils import _get_new_operation_id
from one_ring_loop.cancellation import CancelScope
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.lowlevel import get_current_task, get_running_loop
from one_ring_loop.operations import Park, WaitsOn

if TYPE_CHECKING:
    from collections.abc import Generator

    from one_ring_core.operations import IOOperation
    from one_ring_core.results import IOCompletion
    from one_ring_loop.typedefs import Coro, TaskID

logger = get_logger(__name__)


class NotDone:
    """Sentinel for unfinished Task."""

    @override
    def __repr__(self) -> str:
        """Pretty printing."""
        return "NotDone"


_not_done = NotDone()


@dataclass
class Task[TResult]:
    """Drives coroutines forwards."""

    """The generator coroutine wrapped by the task."""
    gen: Coro = field(repr=False)

    """The ID of the task."""
    task_id: TaskID

    """Cancel scope stack for the task"""
    cancel_scopes: deque[CancelScope]

    """For the task to know where it lives."""
    task_group: TaskGroup | None = field(repr=False)

    # TODO: Below attributes four could be made an enum to make invalid states
    # unrepresentable, but would also come at the cost of verbose pattern matching.

    """If the task is currently waiting on the kernel to finish IO."""
    waiting: bool = field(default=False, init=False)

    """The current IO operation that is performed."""
    awaiting_operation: IOOperation | WaitsOn | Park | None = field(
        default=None, init=False
    )

    """If the task has been started or not."""
    started: bool = field(default=False, init=False)

    """Final result of the task."""
    _result: TResult | NotDone | BaseException = field(default=_not_done, init=False)

    def start(self) -> None:
        """Starts the task."""
        if self.started:
            msg = f"Task with task_id {self.task_id} already running"
            raise RuntimeError(msg)

        self.drive(None)
        self.started = True

    def drive(self, value: IOCompletion | None) -> None:
        """Drives the attached generator coroutine forwards."""
        self.waiting = False
        with self._handle_drive_exc():
            if value is None:
                self.awaiting_operation = self.gen.send(None)
            else:
                self.awaiting_operation = self.gen.send(value)

    def throw(self, exc: BaseException) -> None:
        """Throws an exception into the task's generator."""
        self.waiting = False
        with self._handle_drive_exc():
            self.awaiting_operation = self.gen.throw(exc)

    @property
    def done(self) -> bool:
        """If a task has finished."""
        return not isinstance(self._result, NotDone)

    @property
    def result(self) -> TResult:
        """Gets the result of a finished task."""
        if isinstance(self._result, NotDone):
            raise RuntimeError("Task result access before task was finished")  # noqa: TRY004
        if isinstance(self._result, BaseException):
            raise self._result

        return self._result

    def wait(self) -> Coro[TResult]:
        """Waits on a Task, so that another Task can yield from it."""
        yield from wait_on(self)
        return self.result

    def enter_cancel_scope(self, cancel_scope: CancelScope) -> None:
        """Enters a cancel scope by appending it to the cancel scope stack."""
        self.cancel_scopes.append(cancel_scope)
        cancel_scope.add_task(self.task_id)

    def exit_cancel_scope(self) -> CancelScope:
        """Exits a cancel scope by popping it from the cancel scope stack."""
        cancel_scope = self.cancel_scopes.pop()
        cancel_scope.remove_task(self.task_id)
        return cancel_scope

    def current_cancel_scope(self) -> CancelScope | None:
        """Gets the lowest level nested cancel scope."""
        if not self.cancel_scopes:
            return None

        return self.cancel_scopes[-1]

    def set_error(self, exc: BaseException) -> None:
        """Sets the result of the task to an exception."""
        self._result = exc

    @contextmanager
    def _handle_drive_exc(self) -> Generator[None]:
        try:
            yield
        except StopIteration as e:
            self._result = e.value
        except BaseException as e:
            self.set_error(e)
            if self.task_group is not None:
                self.task_group.set_error(e)
            else:
                raise


@dataclass
class TaskGroup:
    """Trio style nursery.

    Lots of boiler-plate due to not being compatible with CM protocol.
    """

    """Holds the IDs of all the tasks within the group."""
    tasks: list[Task] = field(default_factory=list, init=False)

    """Common cancel scope for all tasks in the group."""
    cancel_scope: CancelScope = field(default_factory=CancelScope, init=False)

    """List of errors produced by children."""
    _errors: list[BaseException] = field(default_factory=list, init=False)

    def create_task(self, gen: Coro) -> None:
        """Creates a task managed by the task group."""
        task = _create_standalone_task(gen, get_current_task().cancel_scopes, self)
        for cancel_scope in task.cancel_scopes:
            cancel_scope.add_task(task.task_id)
        self.tasks.append(task)

    def enter(self) -> None:
        """Nop enter."""
        get_current_task().enter_cancel_scope(self.cancel_scope)

    def exit(
        self,
    ) -> Coro[None]:
        """If an exception occurred, cancel all tasks."""
        cancel_scope = get_current_task().exit_cancel_scope()
        if not all(task.done for task in self.tasks):
            cancel_scope.cancel()
        yield from self.wait()

        if self._errors:
            raise BaseExceptionGroup(
                "unhandled errors in TaskGroup", self._errors
            ) from None

    def wait(self) -> Coro[None]:
        """Waits for all children to finish."""
        yield from wait_on(*self.tasks)

    def set_error(self, exc: BaseException) -> None:
        """Tells the task group that an error occurred."""
        # Skip cancelled errors if cancellation was caused by the group itself.
        if self._errors and isinstance(exc, Cancelled):
            return

        self._errors.append(exc)
        self.cancel_scope.cancel()


def wait_on(*tasks: Task) -> Coro[None]:
    """Yield until all given tasks are done.

    Args:
        tasks: the tasks for which we want to wait for
    """
    while not all(task.done for task in tasks):
        unfinished = tuple(task.task_id for task in tasks if not task.done)
        yield WaitsOn(unfinished)


def _create_standalone_task[T](
    gen: Coro[T], cancel_scopes: deque[CancelScope], task_group: TaskGroup | None
) -> Task[T]:
    """Creates a task by adding it to the event loop.

    This function is not meant to be used by users. Right now, it's only exposed for the
    bridging example.

    Args:
        gen: the coroutine for the Task to wrap
        cancel_scopes: the cancel scopes relevant to the task
        task_group: the task group to which the task belongs to
    """
    task: Task[T] = Task(gen, _get_new_operation_id(), deque(cancel_scopes), task_group)
    get_running_loop().add_task(task)
    return task


# Yes, this is stupid. But Python doesn't have "Map" for VarTypeTyple yet.
# This is what asyncio does for gather.


@overload
def gather[T1](task1: Task[T1], /) -> Coro[tuple[T1]]: ...


@overload
def gather[T1, T2](task1: Task[T1], task2: Task[T2], /) -> Coro[tuple[T1, T2]]: ...


@overload
def gather[T1, T2, T3](
    task1: Task[T1], task2: Task[T2], task3: Task[T3], /
) -> Coro[tuple[T1, T2, T3]]: ...


@overload
def gather[T1, T2, T3, T4](
    task1: Task[T1], task2: Task[T2], task3: Task[T3], task4: Task[T4], /
) -> Coro[tuple[T1, T2, T3, T4]]: ...


@overload
def gather[T1, T2, T3, T4, T5](
    task1: Task[T1],
    task2: Task[T2],
    task3: Task[T3],
    task4: Task[T4],
    task5: Task[T5],
    /,
) -> Coro[tuple[T1, T2, T3, T4, T5]]: ...


@overload
def gather[T1, T2, T3, T4, T5, T6](
    task1: Task[T1],
    task2: Task[T2],
    task3: Task[T3],
    task4: Task[T4],
    task5: Task[T5],
    task6: Task[T6],
    /,
) -> Coro[tuple[T1, T2, T3, T4, T5, T6]]: ...


def gather[T](*tasks: Task[T]) -> Coro[tuple[T, ...]]:
    """Wrapper to await multiple tasks.

    Args:
        tasks: the task you want to yield from (await)

    Returns:
        Final return value when yielded from will be a tuple of task results
    """
    yield from wait_on(*tasks)
    return tuple(task.result for task in tasks)
