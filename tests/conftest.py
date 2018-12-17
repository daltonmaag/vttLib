from pathlib import Path

import pytest


@pytest.fixture
def original_shared_datadir(request) -> Path:
    return Path(request.fspath.dirname, "data")
