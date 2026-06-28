from collections.abc import Callable
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--mode",
        action="store",
        default="fast",
        help="Live crawl target report mode: fast or full.",
    )
    parser.addoption(
        "--force",
        action="store_true",
        default=False,
        help="Refresh cached live crawl fetch responses.",
    )
    parser.addoption(
        "--out-dir",
        action="store",
        default=None,
        help="Directory for live crawl target CSV report files.",
    )
    parser.addoption(
        "--timestamp",
        action="store",
        default=None,
        help="Timestamp suffix for live crawl target CSV report files.",
    )
    parser.addoption(
        "--verbose-fetch",
        action="store_true",
        default=False,
        help="Print each live crawl fetch URL.",
    )


@pytest.fixture
def fixture_text() -> Callable[[str], str]:
    base_dir = Path(__file__).parent / "fixtures"

    def _read(name: str) -> str:
        return (base_dir / name).read_text(encoding="utf-8")

    return _read
