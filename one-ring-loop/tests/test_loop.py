from __future__ import annotations

from typing import TYPE_CHECKING

from one_ring_loop.fileio import open_file
from one_ring_loop.loop import Task, create_task, join, run

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def my_coro(path: str) -> Coro[str]:
    """Test coro for event loop."""
    yield from open_file(path)
    return "hello"


def entry() -> Coro[None]:
    """Test entrypoint."""
    task: Task[str] = create_task(my_coro("./tmp/hello.txt"))
    create_task(my_coro("./tmp/world.txt"))

    test = yield from join(task)
    assert test == "hello"


def test_tasks() -> None:
    run(entry())
