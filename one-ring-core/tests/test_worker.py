import pytest

from one_ring_core.log import get_logger
from one_ring_core.operations import FileOpen
from one_ring_core.results import FileOpenResult
from one_ring_core.worker import IOWorker

logger = get_logger(__name__)


def test_io_worker_single_read_wait() -> None:
    with IOWorker() as worker:
        worker.register(FileOpen(b"./tmp/hello.txt", "rwc"), 1)
        worker.submit()
        completion = worker.wait()
        if isinstance(result := completion.unwrap(), FileOpenResult):
            logger.info("Opened file with file descriptor", fd=result.fd)


def test_io_worker_multi_read_peek() -> None:
    with IOWorker() as worker:
        worker.register(FileOpen(b"./tmp/hello.txt", "rwc"), 1)
        worker.register(FileOpen(b"./tmp/world.txt", "rwc"), 2)
        worker.register(FileOpen(b"./tmp/exclamation.txt", "rwc"), 3)
        worker.submit()
        i = 0
        while i < 3:
            completion = worker.peek()
            if completion is not None and isinstance(
                result := completion.unwrap(), FileOpenResult
            ):
                logger.info("Opened file with file descriptor", fd=result.fd)
                i += 1


def test_io_worker_no_such_file() -> None:
    with IOWorker() as worker:
        worker.register(FileOpen(b"./tmp/should_not_exist.txt", "rw"), 1)
        worker.submit()
        completion = worker.wait()
        with pytest.raises(FileNotFoundError, match="No such file or directory"):
            completion.unwrap()
