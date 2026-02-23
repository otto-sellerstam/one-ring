from __future__ import annotations

import errno
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_core.log import get_logger
from one_ring_core.operations import Cancel, IOOperation
from one_ring_core.worker import IOWorker
from one_ring_loop._utils import _get_new_operation_id, _local
from one_ring_loop.exceptions import Cancelled
from one_ring_loop.operations import Checkpoint, Park, WaitsOn

if TYPE_CHECKING:
    from collections.abc import Generator

    from one_ring_core.results import IOCompletion, IOResult
    from one_ring_loop.task import Task
    from one_ring_loop.typedefs import Coro, TaskID

logger = get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class Loop:
    """The one-ring-loop. Bask in it's glory."""

    # TODO: See if there's a nice way to consolidate the below three attributes.
    """The tasks currently running."""
    tasks: dict[TaskID, Task] = field(default_factory=dict, init=False)

    """Says which other tasks depends on a given task."""
    task_dependencies: defaultdict[TaskID, set[TaskID]] = field(
        default_factory=lambda: defaultdict(set), init=False
    )

    """The task which is currently executing synchronously"""
    _current_task: Task | None = None

    """Maps operation id to task id for in-flight operations"""
    operation_to_task: dict[int, TaskID] = field(default_factory=dict, init=False)

    def run_until_complete(self) -> None:
        """Runs the event loop until all tasks are complete."""
        with IOWorker() as worker:
            while self.tasks:
                self._handle_cancellations(worker)
                self._start_tasks()
                self._register_tasks(worker)
                self._drive_unparked_tasks()
                self._drive_completed_tasks(worker)
                self._drive_checkpointed_tasks()
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
            if isinstance(task.awaiting_operation, Park):
                # No kernel op, throw directly
                with self.set_current_task(task):
                    task.throw(Cancelled())
                continue
            if task.waiting and task.in_flight_op_id is not None:
                # Check if the task is inside a shielded scope, until hitting the
                # cancelled CancelScope.
                for cancel_scope in reversed(task.cancel_scopes):
                    if cancel_scope.cancelled or cancel_scope.shielded:
                        break

                if cancel_scope.cancelled:
                    cancel_op = Cancel(target_identifier=task.in_flight_op_id)
                    worker.register(cancel_op, _get_new_operation_id())

        if should_submit:
            worker.submit()

    def _start_tasks(self) -> None:
        """Starts unstarted tasks."""
        unstarted_tasks = [task for task in self.tasks.values() if not task.started]
        for task in unstarted_tasks:
            with self.set_current_task(task):
                task.start()

    # TODO: Simplify this method.
    def _register_tasks(self, worker: IOWorker) -> None:  # noqa: C901
        tasks_to_register = [
            task
            for task in self.tasks.values()
            # TODO: I really need to merge this into one state.
            if not task.waiting and task.started and not task.done
        ]
        for task in tasks_to_register:
            for cancel_scope in reversed(task.cancel_scopes):
                if cancel_scope.cancelled and not isinstance(
                    task.awaiting_operation, WaitsOn
                ):
                    # The task is canceled, and the task has no current IO in progress.
                    with self.set_current_task(task):
                        task.throw(Cancelled(f"Task {task.task_id} was cancelled"))

                if cancel_scope.shielded:
                    break

            # If a .throw call finished the task, don't register it.
            if task.done:
                continue

            match task.awaiting_operation:
                case IOOperation():
                    op_id = _get_new_operation_id()
                    worker.register(task.awaiting_operation, op_id)
                    self.operation_to_task[op_id] = task.task_id
                    task.in_flight_op_id = op_id
                case WaitsOn(task_ids=task_ids):
                    for task_id in task_ids:
                        self.task_dependencies[task_id].add(task.task_id)
                case Park():
                    pass
                case Checkpoint():
                    continue
                case None:
                    continue

            task.waiting = True

        if tasks_to_register:
            worker.submit()

    def _get_completed_operations(
        self, worker: IOWorker
    ) -> set[IOCompletion[IOResult]]:
        completions: set[IOCompletion] = set()

        if all(task.waiting for task in self.tasks.values()):
            if all(
                isinstance(t.awaiting_operation, WaitsOn | Park)
                for t in self.tasks.values()
            ):
                logger.info("Raising Deadlock error", tasks=self.tasks)
                raise RuntimeError(
                    "Deadlock: all tasks waiting on dependencies, no pending I/O"
                )
            completion = worker.wait()
            completions.add(completion)
        else:
            # Peek until we get None.
            while (completion := worker.peek()) is not None:
                completions.add(completion)

        return completions

    def _drive_completed_tasks(self, worker: IOWorker) -> None:
        completions = self._get_completed_operations(worker)
        for completion in completions:
            op_id = completion.user_data
            task_id = self.operation_to_task.pop(op_id, None)

            if task_id is None:
                continue
            task = self.tasks.get(task_id)
            if task is None:
                continue

            with self.set_current_task(task):
                if (
                    isinstance(oserror := completion.result, OSError)
                    and oserror.errno is not None
                    and oserror.errno == errno.ECANCELED
                ):
                    task.throw(Cancelled())
                else:
                    task.drive(completion)

    def _drive_unparked_tasks(self) -> None:
        """Drives tasks that have been unparked.

        Needs to run before _drive_completed_tasks to avoid deadlocks.
        """
        while _local.unpark_queue:
            unparked_task_id = _local.unpark_queue.popleft()
            unparked_task = self.tasks[unparked_task_id]

            with self.set_current_task(unparked_task):
                unparked_task.drive(None)

    def _drive_checkpointed_tasks(self) -> None:
        """Drives tasks that have been checkpointed."""
        checkpointed_tasks = [
            task
            for task in self.tasks.values()
            if isinstance(task.awaiting_operation, Checkpoint)
        ]

        for task in checkpointed_tasks:
            with self.set_current_task(task):
                task.drive(None)

    def _remove_done_tasks(self) -> None:
        done_tasks = [task for task in self.tasks.values() if task.done]
        for done_task in done_tasks:
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
    _create_standalone_task(gen, None, None)
    _local.loop.run_until_complete()
    _local.cleanup()
