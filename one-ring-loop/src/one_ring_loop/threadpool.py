import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from one_ring_core.operations import Read
from one_ring_loop._utils import _execute

if TYPE_CHECKING:
    from collections.abc import Callable

    from one_ring_loop.typedefs import Coro


@dataclass(slots=True, kw_only=True)
class EventFD:
    """Wrapper for easy eventfd."""

    """The file descriptor for the event"""
    fd: int = field(init=False)

    def __post_init__(self) -> None:
        """Creates an eventfd."""
        self.fd = os.eventfd(0, os.EFD_NONBLOCK | os.EFD_CLOEXEC)

    def wait(self) -> Coro[None]:
        """Waits for the eventfd to be set."""
        yield from _execute(Read(fd=self.fd, size=8))

    def notify(self) -> None:
        """Called from worker threads to notify that they're done."""
        os.eventfd_write(self.fd, 1)

    def close(self) -> None:
        """Closes the eventfd."""
        os.close(self.fd)


_executor = ThreadPoolExecutor()


# TODO: This creates a new eventfd per thread. Not optimal, but otherwise requires
# plumbing into event loop for a clean solution. To fix later, if it becomes a problem.
# Architecture idea:
# 1. Create queue to put thread results into.
# 2. Park thread tasks waiting on result.
# 3. Have event loop check queue, and send results to relevant tasks.
# This achieves a solution using a single eventfd, at the cost of more complexity in the
# loop.
def run_in_thread[T, **P](
    func: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> Coro[T]:
    """Runs a function in a threadpool."""
    eventfd = EventFD()

    def wrapper() -> T:
        ret = func(*args, **kwargs)
        eventfd.notify()
        return ret

    fut = _executor.submit(wrapper)
    yield from eventfd.wait()
    ret = fut.result()
    eventfd.close()

    return ret
