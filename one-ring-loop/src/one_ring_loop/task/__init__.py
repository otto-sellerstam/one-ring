from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self, overload, override

from one_ring_core.log import get_logger
from one_ring_loop._utils import _get_new_operation_id, _local
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.lowlevel import get_current_task, get_running_loop
from one_ring_loop.operations import Checkpoint, Park, WaitsOn
from one_ring_loop.task.state import Created, Done, Ready, Submitted, TaskState

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import TracebackType

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


@dataclass(slots=True, kw_only=True)
class CancelScope:
    """Cancel scope, inspired by Trio."""

    """If the scope is shielded from cancellation or not."""
    shielded: bool = field(default=False)

    """Whether the cancel scope is cancelled or not"""
    cancelled: bool = field(default=False, init=False)

    """IDs of the tasks within the cancel scope."""
    task_ids: set[TaskID] = field(default_factory=set, init=False)

    def cancel(self) -> None:
        """Cancels the cancel scope."""
        self.cancelled = True
        _local.cancel_queue.extend(self.task_ids)

    def __enter__(self) -> Self:
        """Adds the current task to the scope."""
        get_current_task().enter_cancel_scope(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Removes the current task from the scope."""
        get_current_task().exit_cancel_scope()

    def add_task(self, task_id: TaskID) -> None:
        """Adds a task to the cancel scope."""
        self.task_ids.add(task_id)

    def remove_task(self, task_id: TaskID) -> None:
        """Removes a task from the cancel scope."""
        self.task_ids.remove(task_id)


@dataclass(slots=True, kw_only=True)
class Task[TResult]:
    """Drives coroutines forwards."""

    """The generator coroutine wrapped by the task."""
    gen: Coro = field(repr=False)

    """The ID of the task."""
    task_id: TaskID

    """Cancel scope stack for the task"""
    cancel_scopes: deque[CancelScope] = field(repr=False)

    """For the task to know where it lives."""
    task_group: TaskGroup | None = field(repr=False)

    """Union encompassing the current state of the task"""
    state: TaskState[TResult] = field(default_factory=Created)

    def start(self) -> None:
        """Starts the task."""
        if not isinstance(self.state, Created):
            msg = f"Task with task_id {self.task_id} has already been started"
            raise RuntimeError(msg)  # noqa: TRY004

        self.drive(None)

    def drive(self, value: IOCompletion | None) -> None:
        """Drives the attached generator coroutine forwards."""
        with self._handle_drive_exc():
            op = self.gen.send(value)
            self.state = Ready(operation=op)

    def throw(self, exc: BaseException) -> None:
        """Throws an exception into the task's generator."""
        with self._handle_drive_exc():
            op = self.gen.throw(exc)
            self.state = Ready(operation=op)

    def pending_cancel_op_id(self) -> int | None:
        """Returns the kernel op_id to cancel, or None if not applicable."""
        if not isinstance(self.state, Submitted):
            return None
        return self.state.op_id

    @property
    def is_started(self) -> bool:
        """Checks if a task has been started."""
        return not isinstance(self.state, Created)

    @property
    def is_checkpointed(self) -> bool:
        """Checks if a task is currently checkpointed."""
        return isinstance(self.state, Ready) and isinstance(
            self.state.operation, Checkpoint
        )

    @property
    def is_parked(self) -> bool:
        """If the task is currently parked."""
        return isinstance(self.state, Submitted) and isinstance(
            self.state.operation, Park
        )

    @property
    def is_waiting_on(self) -> bool:
        """If the task is currently waiting on other task dependancies."""
        return isinstance(self.state, Submitted) and isinstance(
            self.state.operation, WaitsOn
        )

    @property
    def has_pending_io(self) -> bool:
        """Checks if the task is currently waiting on I/O result from kernel."""
        return isinstance(self.state, Submitted) and self.state.op_id is not None

    @property
    def is_ready(self) -> bool:
        """If a task is ready to be processed."""
        return isinstance(self.state, Ready)

    @property
    def is_submitted(self) -> bool:
        """If a task has had its operation submitted."""
        return isinstance(self.state, Submitted)

    @property
    def is_done(self) -> bool:
        """If a task has finished."""
        return isinstance(self.state, Done)

    @property
    def result(self) -> TResult:
        """Gets the result of a finished task."""
        if not isinstance(self.state, Done):
            raise RuntimeError("Task result access before task was finished")  # noqa: TRY004
        if isinstance(self.state.result, BaseException):
            raise self.state.result

        return self.state.result

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

    def current_cancel_scope(self) -> CancelScope:
        """Gets the lowest level nested cancel scope."""
        if not self.cancel_scopes:
            raise RuntimeError("Task created without cancel scope")

        return self.cancel_scopes[-1]

    def should_cancel(self) -> bool:
        """Determines if a task should be cancelled from its cancel scopes."""
        for cancel_scope in reversed(self.cancel_scopes):
            if cancel_scope.cancelled:
                return True
            if cancel_scope.shielded:
                return False

        return False

    def set_error(self, exc: BaseException) -> None:
        """Sets the result of the task to an exception."""
        self.state = Done(result=exc)

    @contextmanager
    def _handle_drive_exc(self) -> Generator[None]:
        try:
            yield
        except StopIteration as e:
            self.state = Done(result=e.value)
        except BaseException as e:
            self.set_error(e)
            if self.task_group is not None:
                self.task_group.set_error(e)
            else:
                raise


@dataclass(slots=True, kw_only=True)
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
        # Same as CancelScope.__enter__
        get_current_task().enter_cancel_scope(self.cancel_scope)

    def exit(
        self,
    ) -> Coro[None]:
        """If an exception occurred, cancel all tasks."""
        # Like CancelScope.__exit__, but fetches cancel scope, cancels, and awaits.
        cancel_scope: CancelScope = get_current_task().exit_cancel_scope()
        if not all(task.is_done for task in self.tasks):
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
    while not all(task.is_done for task in tasks):
        unfinished = tuple(task.task_id for task in tasks if not task.is_done)
        yield WaitsOn(task_ids=unfinished)


def _create_standalone_task[T](
    gen: Coro[T], cancel_scopes: deque[CancelScope] | None, task_group: TaskGroup | None
) -> Task[T]:
    """Creates a task by adding it to the event loop.

    This function is not meant to be used by users. Right now, it's only exposed for the
    bridging example.

    Args:
        gen: the coroutine for the Task to wrap
        cancel_scopes: the cancel scopes relevant to the task
        task_group: the task group to which the task belongs to
    """
    task_id = _get_new_operation_id()
    if cancel_scopes is None:
        new_cancel_scope = CancelScope()
        new_cancel_scope.add_task(task_id)
        _cancel_scopes = deque([new_cancel_scope])
    else:
        _cancel_scopes = deque(cancel_scopes)

    task: Task[T] = Task(
        gen=gen, task_id=task_id, cancel_scopes=_cancel_scopes, task_group=task_group
    )
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
