from __future__ import annotations

import pytest

from one_ring_loop.lowlevel import get_running_loop


def test_get_running_loop_errors() -> None:
    with pytest.raises(RuntimeError, match="No event loop running"):
        get_running_loop()
