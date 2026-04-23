"""Tests for trade_md.parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from trade_md.parser import CustomIndicatorRef, parse_file, parse_string

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parser_basic():
    doc = parse_string("""---
name: foo
version: 0.1.0
---

## Thesis
Hello world.

## When to disable
On Tuesdays.
""")
    assert doc.name == "foo"
    assert doc.version == "0.1.0"
    assert "Thesis" in doc.prose_sections
    assert doc.prose_sections["Thesis"] == "Hello world."
    assert doc.prose_sections["When to disable"] == "On Tuesdays."


def test_parser_rejects_no_front_matter():
    with pytest.raises(ValueError, match="front matter"):
        parse_string("# just a markdown file\n")


def test_parser_rejects_non_mapping():
    with pytest.raises(ValueError, match="YAML mapping"):
        parse_string("---\n- a list\n---\n")


def test_parser_properties(example_doc):
    assert example_doc.name == "heritage-rsi-ema"
    assert example_doc.version == "0.3.1"
    assert "entry_long" in example_doc.signals
    assert "trend_filter" in example_doc.indicators
    assert example_doc.risk["stoploss"] == -0.03
    assert example_doc.market["timeframe"] == "5m"
    assert example_doc.sizing["method"] == "kelly_fraction"


def test_parser_file(example_doc):
    assert example_doc.source_path is not None
    assert example_doc.source_path.name == "TRADE.md"


def test_parse_directory():
    """parse_file accepts a directory path and resolves to TRADE.md."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    assert doc.name == "test-strategy"
    assert doc.source_path is not None
    assert doc.source_path.name == "TRADE.md"
    assert doc.strategy_dir == FIXTURES_DIR / "strategy_dir"


def test_parse_custom_indicators_block():
    """custom_indicators block is parsed into CustomIndicatorRef list."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir" / "TRADE.md")
    assert len(doc.custom_indicators) == 1
    ref = doc.custom_indicators[0]
    assert isinstance(ref, CustomIndicatorRef)
    assert ref.module == "indicators.test_ind"
    assert ref.as_name == "test_score"
    assert ref.version_pin == "1.0"


def test_parse_no_custom_indicators():
    """v0.1 example has no custom_indicators — empty list."""
    doc = parse_string("---\nname: foo\nversion: 0.1.0\n---\n")
    assert doc.custom_indicators == []


def test_custom_indicators_rejected_on_v01():
    """custom_indicators block on spec 0.1 raises ValueError."""
    with pytest.raises(ValueError, match="not allowed when trade_md_spec is '0.1'"):
        parse_string("""---
trade_md_spec: "0.1"
name: t
version: 0.1.0
custom_indicators:
  - module: foo
    as: bar
---
""")


def test_custom_indicators_malformed():
    """Malformed custom_indicators block raises ValueError."""
    with pytest.raises(ValueError, match="must be a list"):
        parse_string("""---
name: t
version: 0.1.0
custom_indicators: "not a list"
---
""")


def test_load_custom_indicators():
    """load_custom_indicators imports the module and returns metadata."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    metas = doc.load_custom_indicators()
    assert "test_score" in metas
    meta = metas["test_score"]
    assert meta.version == "1.0.0"
    assert meta.inputs == ["close", "volume"]
    assert "lookback" in meta.params


def test_strategy_dir_none_for_string():
    """String-parsed doc has strategy_dir = None."""
    doc = parse_string("---\nname: t\nversion: 0.1.0\n---\n")
    assert doc.strategy_dir is None
