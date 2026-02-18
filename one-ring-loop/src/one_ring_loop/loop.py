from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, overload

from one_ring_core.log import get_logger
from one_ring_core.operations import IOOperation
from one_ring_core.worker import IOWorker
from one_ring_loop.task import Task, _wait_on
from one_ring_loop.typedefs import WaitsOn

if TYPE_CHECKING:
    from one_ring_core.results import IOCompletion
    from one_ring_loop.typedefs import Coro, TaskID

logger = get_logger(__name__)


def _get_new_task_id() -> TaskID:
    """TODO: Optimize."""
    task_id = 1
    while task_id <= len(_loop.tasks):
        if task_id not in _loop.tasks:
            break

        task_id += 1

    return task_id


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
                self._start_tasks()
                self._register_tasks(worker)
                self._drive_completed_tasks(worker)
                self._remove_done_tasks()

    def _start_tasks(self) -> None:
        """Starts unstarted tasks."""
        unstarted_tasks = [task for task in self.tasks.values() if not task.started]
        for task in unstarted_tasks:
            task.start()

    def _register_tasks(self, worker: IOWorker) -> None:
        tasks_to_register = [task for task in self.tasks.values() if not task.waiting]
        for task in tasks_to_register:
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
            # completion.user_data should be renamed.
            task = self.tasks[completion.user_data]
            logger.info("Driving task", task_id=task.task_id)
            task.drive(completion)

    def _remove_done_tasks(self) -> None:
        done_tasks = [task for task in self.tasks.values() if task.done]
        for task in done_tasks:
            logger.info("Task finished", task_id=task.task_id)
            for waiting_task_id in self.task_dependencies[task.task_id]:
                self.tasks[waiting_task_id].drive(None)

        self.tasks = {
            task_id: task for task_id, task in self.tasks.items() if not task.done
        }

    def add_task(self, task: Task) -> None:
        """Adds a task to be run by the event loop."""
        self.tasks[task.task_id] = task


_loop = Loop()


def create_task[T](gen: Coro[T]) -> Task[T]:
    """Creates a task by adding it to the event loop.

    Args:
        gen: the coroutine for the Task to wrap
    """
    task: Task[T] = Task(gen, _get_new_task_id())
    _loop.add_task(task)
    return task


def run(gen: Coro) -> None:
    """Entry point for running the event loop.

    Creates a Task from the generator on the event loop, and runs the loop.

    Args:
        gen: the entry coroutine
    """
    create_task(gen)
    _loop.run()


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
    """Wrapper to await tasks.

    Args:
        tasks: the task you want to yield from (await)
    """
    yield from _wait_on(*tasks)
    return tuple(task.result for task in tasks)
