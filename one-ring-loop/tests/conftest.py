"""Shared test fixtures for one-ring-loop."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_file_path(tmp_path: Path) -> Path:
    """Provide a temporary file path for file I/O tests.

    Uses pytest's built-in "tmp_path" fixture.
    """
    return tmp_path / "test_file.txt"
