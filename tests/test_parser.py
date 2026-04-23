"""Tests for trade_md.parser."""
from __future__ import annotations

import pytest

from trade_md.parser import parse_string


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
