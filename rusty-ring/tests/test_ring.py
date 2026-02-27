import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from one_ring_loop.log import get_logger
from rusty_ring import Ring

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

SERVER_MESSAGE = b"A new client connected!"


class TestRing:
    def test_ring_context_manager(self) -> None:
        with Ring(32) as ring:
            assert isinstance(ring, Ring)

    def test_file_open_write_read(self, tmp_file_path: Path) -> None:
        file_content = b"Hello! :)"

        with Ring(32) as ring:
            ring.prep_openat(
                user_data=0, path=str(tmp_file_path), flags=66, mode=432, dir_fd=-100
            )
            ring.submit()
            open_event = ring.wait()
            logger.info("Got open event", io_event=open_event)
            fd = open_event.res

            write_buf = bytearray(file_content)
            ring.prep_write(0, fd=fd, buf=write_buf, nbytes=9, offset=0)
            ring.submit()
            write_event = ring.wait()
            logger.info("Got write event", io_event=write_event)

            read_buf = bytearray(9)
            ring.prep_read(0, fd=fd, buf=read_buf, nbytes=9, offset=0)
            ring.submit()
            read_event = ring.wait()
            logger.info("Got read event", io_event=read_event)
            assert bytes(read_buf) == file_content

    def test_timeout(self, timing) -> None:
        with Ring(32) as ring:
            sleep_for_sec = 1
            sleep_for_nsec = int(5e8)  # 0.5 seconds.
            ring.prep_timeout(0, sleep_for_sec, sleep_for_nsec)
            ring.submit()

            timing.start()
            ring.wait()
            timing.assert_elapsed_between(2.5, 2.6, msg="Should sleep for 2 secounds")

    def test_wait_does_not_hold_gil(self) -> None:
        flag = threading.Event()

        def background() -> None:
            logger.info("Sleeping for 0.5 seconds")
            time.sleep(0.5)
            logger.info("Setting flag")
            flag.set()

        with Ring(32) as ring, ThreadPoolExecutor(max_workers=2) as executor:
            ring.prep_timeout(0, sec=1, nsec=0)
            ring.submit()

            logger.info("Submitting background function")
            executor.submit(background)
            logger.info("Waiting on ring timeout")
            ring.wait()
            logger.info("Finished waiting")

            assert flag.is_set()
