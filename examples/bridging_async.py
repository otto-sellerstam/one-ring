"""This example shows how to bridge one_ring to use modern Python "await" syntax.

Note: the project applies a structurred approach similar to Trio. However, I have not
yet taken the time to implement an async version of the TaskGroup, which kind of breaks
this example...
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from one_ring_loop import run
from one_ring_loop.task import _create_standalone_task
from one_ring_loop.task import gather as _gen_gather
from one_ring_loop.timerio import sleep as _gen_sleep

if TYPE_CHECKING:
    from one_ring_loop import Task
    from one_ring_loop.typedefs import Coro

### Define "await" compatible sleep ###


@dataclass(slots=True, kw_only=True)
class Sleep:
    """Asynchonous sleep."""

    time: int

    def __await__(self) -> Coro[None]:
        """Yields timer instructions to event loop."""
        yield from _gen_sleep(self.time)


async def sleep(time: int) -> int:
    """Coroutine wrapping Sleep object."""
    await Sleep(time)
    return time


### Define "await" compatible gather.await ###


class Gather:
    """Gathers multiple tasks to await them as one."""

    def __init__(self, *tasks: Task) -> None:
        self.tasks = tasks

    def __await__(self) -> Coro[tuple]:
        """Wrapper around generator based one_ring_loop.loop.gather."""
        results = yield from _gen_gather(*self.tasks)
        return results


async def gather(*tasks: Task) -> tuple:
    """Coroutine wrapping Gather object."""
    return await Gather(*tasks)


async def entry() -> None:
    """Entry point for example."""
    start_time = time.monotonic()

    # Creates task using private function. Internally, this function is only used
    # by the "run" function, as well as task groups.
    task1 = _create_standalone_task(sleep(1), deque(), None)
    task2 = _create_standalone_task(sleep(2), deque(), None)

    time1, time2 = await gather(task1, task2)

    print(f"Slept for {time.monotonic() - start_time}")
    print(f"time1: {time1}")
    print(f"time2: {time2}")


if __name__ == "__main__":
    run(entry())
