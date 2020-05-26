from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def original_shared_datadir(request: Any) -> Path:
    return Path(request.fspath.dirname, "data")
