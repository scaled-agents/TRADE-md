"""Shared fixtures for trade-md tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from trade_md.parser import TradeDoc, parse_file

FIXTURES_DIR = Path(__file__).parent / "fixtures"
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture
def example_doc() -> TradeDoc:
    """Parsed heritage-rsi-ema example strategy."""
    return parse_file(EXAMPLES_DIR / "heritage-rsi-ema" / "TRADE.md")


@pytest.fixture
def broken_fixture_path() -> Path:
    """Path to the broken TRADE.md fixture (exercises every linter rule)."""
    return FIXTURES_DIR / "broken.TRADE.md"


@pytest.fixture
def broken_doc(broken_fixture_path: Path) -> TradeDoc:
    """Parsed broken TRADE.md fixture."""
    return parse_file(broken_fixture_path)
