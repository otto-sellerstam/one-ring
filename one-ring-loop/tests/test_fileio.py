from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from one_ring_loop.fileio import open_file
from one_ring_loop.loop import run

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def entry() -> Coro:
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "fileio_test.txt"
        file_write_content = "Hello!"

        # Open file and get file object.
        file = yield from open_file(str(test_path), "rwc")

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
