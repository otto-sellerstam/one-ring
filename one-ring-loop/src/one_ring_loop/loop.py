from __future__ import annotations

import errno
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_core.log import get_logger
from one_ring_core.operations import Cancel, IOOperation
from one_ring_core.worker import IOWorker
from one_ring_loop._utils import _get_new_operation_id
from one_ring_loop.cancellation import cancel_queue
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.typedefs import WaitsOn

if TYPE_CHECKING:
    from collections.abc import Generator

    from one_ring_core.results import IOCompletion
    from one_ring_loop.task import Task
    from one_ring_loop.typedefs import Coro, TaskID

logger = get_logger(__name__)


_current_task: Task | None = None


def _set_current_task(task: Task | None) -> None:
    global _current_task  # noqa: PLW0603

    _current_task = task


def current_task() -> Task:
    """Returns the Task currently driven by the event loop."""
    if _current_task is None:
        raise RuntimeError("No running tasks")

    return _current_task


@contextmanager
def register_error(task: Task) -> Generator[None]:
    """Utility function to register errors during drive/throw on a task."""
    try:
        yield
    except BaseException as e:
        task.set_error(e)
        if task.task_group is not None:
            task.task_group.set_error(e)
        else:
            raise


@dataclass
class Loop:
    """The event loop."""

    """The tasks currently running."""
    tasks: dict[TaskID, Task] = field(default_factory=dict, init=False)

    """Says which other tasks depends on a given task."""
    task_dependencies: defaultdict[TaskID, set[TaskID]] = field(
        default_factory=lambda: defaultdict(set), init=False
    )

    def run(self) -> None:
        """Runs the event loop."""
        with IOWorker() as worker:
            while self.tasks:
                self._handle_cancellations(worker)
                self._start_tasks()
                self._register_tasks(worker)
                self._drive_completed_tasks(worker)
                self._remove_done_tasks()

    def _handle_cancellations(self, worker: IOWorker) -> None:
        """Drains cancellation queue and registers and submits cancellations events."""
        while cancel_queue:
            task_id = cancel_queue.popleft()
            if task_id not in self.tasks:
                continue
            task = self.tasks[task_id]
            if isinstance(task.awaiting_operation, WaitsOn):
                continue
            if task.waiting:
                cancel_operation = Cancel(task_id)
                worker.register(cancel_operation, _get_new_operation_id())

        worker.submit()

    def _start_tasks(self) -> None:
        """Starts unstarted tasks."""
        unstarted_tasks = [task for task in self.tasks.values() if not task.started]
        for task in unstarted_tasks:
            _set_current_task(task)
            task.start()
            _set_current_task(None)

    def _register_tasks(self, worker: IOWorker) -> None:
        tasks_to_register = [task for task in self.tasks.values() if not task.waiting]
        for task in tasks_to_register:
            # The task is canceled, and the task has no current IO in progress.
            if (
                cancel_scope := task.current_cancel_scope()
            ) is not None and cancel_scope.cancelled:
                _set_current_task(task)
                if not isinstance(task.awaiting_operation, WaitsOn):
                    task.throw(Cancelled(f"Task {task.task_id} was cancelled"))
                _set_current_task(None)

            match task.awaiting_operation:
                case IOOperation():
                    worker.register(task.awaiting_operation, task.task_id)
                    logger.info("Registered task", task_id=task.task_id)
                    task.waiting = True
                case WaitsOn(task_ids=task_ids):
                    for task_id in task_ids:
                        self.task_dependencies[task_id].add(task.task_id)
                    task.waiting = True

        if tasks_to_register:
            worker.submit()

    def _get_completed_operations(self, worker: IOWorker) -> set[IOCompletion]:
        completions: set[IOCompletion] = set()

        if all(task.waiting for task in self.tasks.values()):
            if all(
                isinstance(t.awaiting_operation, WaitsOn) for t in self.tasks.values()
            ):
                raise RuntimeError(
                    "Deadlock: all tasks waiting on dependencies, no pending I/O"
                )
            logger.info("Awaiting completion for unknown task")
            completion = worker.wait()
            completions.add(completion)
            logger.info("Added completion", task_id=completion.user_data)
        else:
            # Peek until we get None.
            while (completion := worker.peek()) is not None:
                completions.add(completion)
                logger.info("Added completion", task_id=completion.user_data)

        return completions

    def _drive_completed_tasks(self, worker: IOWorker) -> None:
        completions = self._get_completed_operations(worker)
        for completion in completions:
            if completion.user_data not in self.tasks:
                # At the moment, this means that it's a cancellation.
                # TODO: Make more general and reliable.
                continue

            # completion.user_data should be renamed.
            task = self.tasks[completion.user_data]
            logger.info("Driving task", task_id=task.task_id)

            _set_current_task(task)
            if (
                isinstance(oserror := completion.result, OSError)
                and oserror.errno is not None
                and oserror.errno == errno.ECANCELED
            ):
                with register_error(task):
                    task.throw(Cancelled())
            else:
                with register_error(task):
                    task.drive(completion)

            _set_current_task(None)

    def _remove_done_tasks(self) -> None:
        done_tasks = [task for task in self.tasks.values() if task.done]
        for task in done_tasks:
            logger.info("Task finished", task_id=task.task_id)
            for waiting_task_id in self.task_dependencies[task.task_id]:
                waiting_task = self.tasks[waiting_task_id]
                _set_current_task(waiting_task)
                waiting_task.drive(None)
                _set_current_task(None)

        self.tasks = {
            task_id: task for task_id, task in self.tasks.items() if not task.done
        }

    def add_task(self, task: Task) -> None:
        """Adds a task to be run by the event loop."""
        self.tasks[task.task_id] = task


_loop = Loop()


def run(gen: Coro) -> None:
    """Entry point for running the event loop.

    Creates a Task from the generator on the event loop, and runs the loop.

    Args:
        gen: the entry coroutine
    """
    from one_ring_loop.task import _create_standalone_task  # noqa: PLC0415

    _create_standalone_task(gen, deque(), None)
    _loop.run()
