from typing import TYPE_CHECKING

import pytest

from one_ring_loop.fileio import open_file

if TYPE_CHECKING:
    from pathlib import Path

    from one_ring_loop.typedefs import Coro


class TestFileIO:
    @pytest.mark.io
    def test_write_and_read_back(self, run_coro, tmp_file_path: Path) -> None:
        content = "Hello!"

        def coro() -> Coro[None]:
            file = yield from open_file(str(tmp_file_path), "rwc")
            try:
                yield from file.write(content)
                result = yield from file.read()
                assert result == content, f"Expected {content!r}, got {result!r}"
            finally:
                yield from file.close()

        run_coro(coro())
