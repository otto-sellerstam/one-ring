from pathlib import Path

from one_ring_core.log import get_logger
from one_ring_core.operations import Statx
from one_ring_core.results import StatxResult
from one_ring_core.worker import IOWorker

logger = get_logger(__name__)


def test_statx() -> None:
    path = "./README.md"

    op = Statx.from_path(path=path)
    with IOWorker() as worker:
        worker.register(op, 0)
        worker.submit()
        res = worker.wait().result

    assert isinstance(res, StatxResult)
    assert Path(path).stat().st_size == res.size
