from typing import TYPE_CHECKING

from one_ring_core.operations import FileOpen
from one_ring_core.results import FileOpenResult

if TYPE_CHECKING:
    from one_ring_loop.typedefs import Coro


def open_file(path: str) -> Coro[int]:
    """Test file open coroutine."""
    open_completion = yield FileOpen(path.encode(), "r")
    if open_completion is not None and isinstance(
        result := open_completion.unwrap(), FileOpenResult
    ):
        return result.fd

    raise ValueError("open_file received wrong result type")
