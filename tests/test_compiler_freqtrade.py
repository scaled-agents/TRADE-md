"""Tests for trade_md.compilers.freqtrade."""
from __future__ import annotations

import ast

from trade_md.compilers.freqtrade import compile_freqtrade
from trade_md.parser import parse_string


def test_compiler_produces_valid_python(example_doc):
    code = compile_freqtrade(example_doc)
    ast.parse(code)
    assert "class HeritageRsiEma(IStrategy)" in code
    assert "def populate_indicators" in code
    assert "def populate_entry_trend" in code
    assert "def populate_exit_trend" in code
    assert "merge_informative_pair" in code
    assert "ta.RSI" in code


def test_compiler_handles_no_informative():
    doc = parse_string("""---
name: simple
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals:
  entry_long: {conditions: ["rsi(14) < 30"]}
  exit_long: {conditions: ["rsi(14) > 70"]}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
## Thesis
Simple.
## When to disable
Never.
""")
    code = compile_freqtrade(doc)
    ast.parse(code)
    assert "informative_pairs" not in code or "def informative_pairs" not in code
    assert "class Simple(IStrategy)" in code


def test_round_trip_parse_compile_ast_parse(example_doc):
    """Round-trip: parse example, compile, ast.parse the output, confirm class name."""
    code = compile_freqtrade(example_doc)
    tree = ast.parse(code)
    class_defs = [
        node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    ]
    assert len(class_defs) == 1
    assert class_defs[0].name == "HeritageRsiEma"


def test_compiler_emits_protections(example_doc):
    code = compile_freqtrade(example_doc)
    assert "StoplossGuard" in code
    assert "MaxDrawdown" in code


def test_compiler_emits_trailing(example_doc):
    code = compile_freqtrade(example_doc)
    assert "trailing_stop = True" in code
    assert "trailing_stop_positive" in code


def test_compiler_no_exit_conditions():
    doc = parse_string("""---
name: entry-only
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals:
  entry_long: {conditions: ["rsi(14) < 30"]}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    code = compile_freqtrade(doc)
    ast.parse(code)
    assert "no exit_long conditions" in code
