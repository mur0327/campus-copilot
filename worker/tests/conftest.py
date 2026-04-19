from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def fixture_text() -> Callable[[str], str]:
    base_dir = Path(__file__).parent / "fixtures"

    def _read(name: str) -> str:
        return (base_dir / name).read_text(encoding="utf-8")

    return _read
