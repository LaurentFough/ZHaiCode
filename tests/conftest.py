"""Project-local retained test outputs; no automatic file or database deletion."""

from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def workspace():
    path = Path.cwd() / ".runtime" / "tests" / uuid4().hex
    path.mkdir(parents=True)
    return path
