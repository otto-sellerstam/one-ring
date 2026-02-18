from __future__ import annotations

from typing import TYPE_CHECKING

from one_ring_loop.fileio import open_file
from one_ring_loop.loop import run

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def entry() -> Coro:
    file_write_content = "Hello!"

    # Open file and get file object.
    file = yield from open_file("./tmp/fileio_test.txt", "rwc")

    try:
        # Write to file.
        yield from file.write(file_write_content)

        # Read result.
        content = yield from file.read()

        assert content == file_write_content
    finally:
        yield from file.close()


def test_fileio() -> None:
    run(entry())


test_fileio()
