"""Tests for trade_md.compilers.freqtrade."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from trade_md.compilers.freqtrade import (
    compile_freqtrade,
    write_compiled_output,
    _version_matches_pin,
)
from trade_md.parser import parse_file, parse_string

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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


# ---- v0.2 custom indicator tests ------------------------------------------


def test_compiler_custom_indicator_directory_output():
    """Strategy with custom indicators produces directory output."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    result = compile_freqtrade(doc)
    assert isinstance(result, dict)
    assert "strategy.py" in result
    assert "__init__.py" in result
    assert "indicators/__init__.py" in result
    assert "indicators/test_ind.py" in result
    # strategy.py should be valid Python
    ast.parse(result["strategy.py"])
    # Should import the custom indicator
    assert "_test_score_compute" in result["strategy.py"]
    assert "from .indicators.test_ind import compute as _test_score_compute" in result["strategy.py"]


def test_compiler_custom_indicator_strategy_class():
    """Generated strategy.py contains correct class and calls."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    result = compile_freqtrade(doc)
    code = result["strategy.py"]
    assert "class TestStrategy(IStrategy)" in code
    # Custom indicator call should appear in populate_indicators
    assert "_test_score_compute(dataframe" in code


def test_compiler_version_pin_match():
    """Version pin "1.0" matches indicator version "1.0.0"."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    # Should not raise — pin is "1.0", indicator version is "1.0.0"
    result = compile_freqtrade(doc)
    assert isinstance(result, dict)


def test_compiler_version_pin_mismatch():
    """Version pin mismatch raises ValueError."""
    doc = parse_string("""---
trade_md_spec: "0.2"
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
custom_indicators:
  - module: indicators.test_ind
    as: test_score
    version_pin: "2.0"
signals:
  entry_long: {conditions: ["rsi(14) < 30"]}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
## Thesis
Test.
## When to disable
Never.
""", source_path=FIXTURES_DIR / "strategy_dir" / "TRADE.md")
    with pytest.raises(ValueError, match="does not match pin"):
        compile_freqtrade(doc)


def test_compiler_version_drift_allowed():
    """--allow-version-drift suppresses pin mismatch."""
    doc = parse_string("""---
trade_md_spec: "0.2"
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
custom_indicators:
  - module: indicators.test_ind
    as: test_score
    version_pin: "2.0"
signals:
  entry_long: {conditions: ["rsi(14) < 30"]}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
## Thesis
Test.
## When to disable
Never.
""", source_path=FIXTURES_DIR / "strategy_dir" / "TRADE.md")
    result = compile_freqtrade(doc, allow_version_drift=True)
    assert isinstance(result, dict)


def test_version_matches_pin():
    """Unit test for _version_matches_pin."""
    assert _version_matches_pin("1.0.0", "1.0") is True
    assert _version_matches_pin("1.0.3", "1.0") is True
    assert _version_matches_pin("1.1.0", "1.0") is False
    assert _version_matches_pin("2.0.0", "1") is False
    assert _version_matches_pin("1.5.0", "1") is True


def test_write_compiled_output_single_file(tmp_path):
    """write_compiled_output handles single-file string."""
    out = tmp_path / "output.py"
    msg = write_compiled_output("# test\n", str(out), "Test")
    assert out.exists()
    assert "1 lines" in msg


def test_write_compiled_output_directory(tmp_path):
    """write_compiled_output handles directory dict."""
    out_dir = tmp_path / "strat_pkg"
    files = {
        "__init__.py": "# init\n",
        "strategy.py": "# strategy\nclass T: pass\n",
        "indicators/__init__.py": "",
    }
    msg = write_compiled_output(files, str(out_dir), "T")
    assert (out_dir / "strategy.py").exists()
    assert (out_dir / "indicators" / "__init__.py").exists()
    assert "3 files" in msg


def test_write_compiled_output_no_out_directory_raises():
    """Directory output with no -o raises ValueError."""
    files = {"strategy.py": "# test\n"}
    with pytest.raises(ValueError, match="require -o"):
        write_compiled_output(files, None, "T")
