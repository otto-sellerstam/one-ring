from __future__ import annotations

import errno
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_core.log import get_logger
from one_ring_core.operations import Cancel, IOOperation
from one_ring_core.worker import IOWorker
from one_ring_loop._utils import _get_new_operation_id, _local
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.typedefs import WaitsOn

if TYPE_CHECKING:
    from collections.abc import Generator

    from one_ring_core.results import IOCompletion, IOResult
    from one_ring_loop.task import Task
    from one_ring_loop.typedefs import Coro, TaskID

logger = get_logger(__name__)


@dataclass
class Loop:
    """The event loop."""

    """The tasks currently running."""
    tasks: dict[TaskID, Task] = field(default_factory=dict, init=False)

    """Says which other tasks depends on a given task."""
    task_dependencies: defaultdict[TaskID, set[TaskID]] = field(
        default_factory=lambda: defaultdict(set), init=False
    )

    """The task which is currently executing synchronously"""
    _current_task: Task | None = None

    def run_until_complete(self) -> None:
        """Runs the event loop until all tasks are complete."""
        with IOWorker() as worker:
            while self.tasks:
                self._handle_cancellations(worker)
                self._start_tasks()
                self._register_tasks(worker)
                self._drive_completed_tasks(worker)
                self._remove_done_tasks()

    def _handle_cancellations(self, worker: IOWorker) -> None:
        """Drains cancellation queue and registers and submits cancellations events."""
        should_submit = False
        while _local.cancel_queue:
            should_submit = True

            task_id = _local.cancel_queue.popleft()
            if task_id not in self.tasks:
                continue
            task = self.tasks[task_id]
            if isinstance(task.awaiting_operation, WaitsOn):
                continue
            if task.waiting:
                cancel_operation = Cancel(task_id)
                worker.register(cancel_operation, _get_new_operation_id())

        if should_submit:
            worker.submit()

    def _start_tasks(self) -> None:
        """Starts unstarted tasks."""
        unstarted_tasks = [task for task in self.tasks.values() if not task.started]
        for task in unstarted_tasks:
            with self.set_current_task(task):
                task.start()

    def _register_tasks(self, worker: IOWorker) -> None:
        tasks_to_register = [
            task
            for task in self.tasks.values()
            # TODO: I really need to merge this into one state.
            if not task.waiting and task.started and not task.done
        ]
        for task in tasks_to_register:
            # The task is canceled, and the task has no current IO in progress.
            if (
                (cancel_scope := task.current_cancel_scope()) is not None
                and cancel_scope.cancelled
                and not isinstance(task.awaiting_operation, WaitsOn)
            ):
                with self.set_current_task(task):
                    task.throw(Cancelled(f"Task {task.task_id} was cancelled"))

                # If the .throw call finished the task, don't register it.
                if task.done:
                    continue

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

    def _get_completed_operations(
        self, worker: IOWorker
    ) -> set[IOCompletion[IOResult]]:
        completions: set[IOCompletion] = set()

        if all(task.waiting for task in self.tasks.values()):
            if all(
                isinstance(t.awaiting_operation, WaitsOn) for t in self.tasks.values()
            ):
                raise RuntimeError(
                    "Deadlock: all tasks waiting on dependencies, no pending I/O"
                )
            completion = worker.wait()
            completions.add(completion)
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

            with self.set_current_task(task):
                if (
                    isinstance(oserror := completion.result, OSError)
                    and oserror.errno is not None
                    and oserror.errno == errno.ECANCELED
                ):
                    task.throw(Cancelled())
                else:
                    task.drive(completion)

    def _remove_done_tasks(self) -> None:
        done_tasks = [task for task in self.tasks.values() if task.done]
        for done_task in done_tasks:
            logger.info("Task finished", task_id=done_task.task_id)

            # Now drive tasks that were dependant on the done tasks.
            while self.task_dependencies[done_task.task_id]:
                waiting_task_id = self.task_dependencies[done_task.task_id].pop()
                waiting_task = self.tasks[waiting_task_id]
                if waiting_task.done:
                    # The loop has already driven this forward, for example if all tasks
                    # waiting_task depended on finished in the same loop iteration.
                    continue
                with self.set_current_task(waiting_task):
                    waiting_task.drive(None)

            self.task_dependencies.pop(done_task.task_id)

        self.tasks = {
            task_id: task for task_id, task in self.tasks.items() if not task.done
        }

    @property
    def current_task(self) -> Task:
        """Gets currently executing task."""
        if self._current_task is None:
            raise RuntimeError("No task currently executing")

        return self._current_task

    @contextmanager
    def set_current_task(self, task: Task) -> Generator[None]:
        """Utility wrapper for setting and removing currently executing task."""
        self._current_task = task
        try:
            yield
        finally:
            self._current_task = None

    def add_task(self, task: Task) -> None:
        """Adds a task to be run by the event loop."""
        self.tasks[task.task_id] = task


def run(gen: Coro) -> None:
    """Entry point for running the event loop.

    Creates a Task from the generator on the event loop, and runs the loop.

    Args:
        gen: the entry coroutine
    """
    from one_ring_loop.task import _create_standalone_task  # noqa: PLC0415

    _local.loop = Loop()
    _create_standalone_task(gen, deque(), None)
    _local.loop.run_until_complete()
    _local.cleanup()


def get_running_loop() -> Loop:
    """Gets the currently running event loop."""
    if _local.loop is None:
        raise RuntimeError("No event loop running")

    return _local.loop
