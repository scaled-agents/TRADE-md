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
    assert "no exit conditions" in code


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


# ---- Short-side emission tests --------------------------------------------


def _doc_with_shorts(*, long_only=False, short_only=False, both=False):
    long_block = (
        "  entry_long: {conditions: ['rsi(14) < 30'], tag: long_in}\n"
        "  exit_long: {conditions: ['rsi(14) > 70'], tag: long_out}\n"
    )
    short_block = (
        "  entry_short: {conditions: ['rsi(14) > 70'], tag: short_in}\n"
        "  exit_short: {conditions: ['rsi(14) < 30'], tag: short_out}\n"
    )
    signals = ""
    if long_only or both:
        signals += long_block
    if short_only or both:
        signals += short_block
    return parse_string(f"""---
name: shorts-test
version: 0.1.0
market: {{regime: [trending], timeframe: 5m, pair_universe: {{quote: USDT, exchange: binance, filter: top50_volume}}}}
signals:
{signals}risk: {{stoploss: -0.05, roi: {{"0": 0.10}}}}
sizing: {{method: fixed_stake, max_open_trades: 3}}
---
## Thesis
Test.
## When to disable
Never.
""")


def test_compiler_can_short_false_when_no_shorts():
    code = compile_freqtrade(_doc_with_shorts(long_only=True))
    ast.parse(code)
    assert "can_short = False" in code
    assert "enter_short" not in code
    assert "exit_short" not in code


def test_compiler_can_short_true_when_shorts_present():
    code = compile_freqtrade(_doc_with_shorts(both=True))
    ast.parse(code)
    assert "can_short = True" in code


def test_compiler_emits_short_entry_block():
    code = compile_freqtrade(_doc_with_shorts(both=True))
    ast.parse(code)
    assert "['enter_short', 'enter_tag']" in code
    assert "(1, 'short_in')" in code
    # long side still present
    assert "['enter_long', 'enter_tag']" in code
    assert "(1, 'long_in')" in code


def test_compiler_emits_short_exit_block():
    code = compile_freqtrade(_doc_with_shorts(both=True))
    ast.parse(code)
    assert "['exit_short', 'exit_tag']" in code
    assert "(1, 'short_out')" in code
    assert "['exit_long', 'exit_tag']" in code
    assert "(1, 'long_out')" in code


def test_compiler_short_only_no_long_emission():
    code = compile_freqtrade(_doc_with_shorts(short_only=True))
    ast.parse(code)
    assert "can_short = True" in code
    assert "['enter_short', 'enter_tag']" in code
    assert "['exit_short', 'exit_tag']" in code
    assert "['enter_long', 'enter_tag']" not in code
    assert "['exit_long', 'exit_tag']" not in code


# ---- BBANDS float-coercion regression test --------------------------------


def test_bbands_emits_nbdev_as_float():
    """talib BBANDS rejects int nbdevup/nbdevdn — the compiler must coerce to float."""
    doc = parse_string("""---
name: bb-test
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals:
  entry_long: {conditions: ["close > bb_upper(20, 2)"]}
  exit_long: {conditions: ["close < bb_lower(20, 2)"]}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    code = compile_freqtrade(doc)
    ast.parse(code)
    # Must emit floats, not ints, otherwise talib raises TypeError at runtime.
    assert "nbdevup=2.0" in code
    assert "nbdevdn=2.0" in code
    assert "nbdevup=2," not in code  # no bare int


# ---- Custom stoploss / custom exit tests ----------------------------------


def _doc_with_custom(*, stoploss=None, exit_block=None):
    extras = ""
    if stoploss:
        extras += f"  custom_stoploss:\n"
        for k, v in stoploss.items():
            extras += f"    {k}: {v}\n"
    if exit_block:
        extras += f"  custom_exit:\n"
        for k, v in exit_block.items():
            extras += f"    {k}: {v}\n"
    return parse_string(f"""---
name: custom-hooks
version: 0.1.0
market: {{regime: [trending], timeframe: 15m, pair_universe: {{quote: USDT, exchange: binance, filter: top50_volume}}}}
signals:
  entry_long: {{conditions: ["rsi(14) < 30"], tag: l_in}}
  exit_long: {{conditions: ["rsi(14) > 70"], tag: l_out}}
risk:
  stoploss: -0.05
  roi: {{"0": 0.10}}
{extras}sizing: {{method: fixed_stake, max_open_trades: 3}}
---
## Thesis
Test.
## When to disable
Never.
""")


def test_custom_stoploss_atr_wick_emits_method_and_indicator():
    doc = _doc_with_custom(stoploss={"type": "atr_wick", "atr_period": 14, "atr_multiplier": 1.5})
    code = compile_freqtrade(doc)
    ast.parse(code)
    assert "use_custom_stoploss = True" in code
    assert "def custom_stoploss" in code
    assert "ta.ATR(dataframe, timeperiod=14)" in code  # auto-injected
    assert "atr * 1.5" in code
    assert "trade.is_short" in code


def test_custom_stoploss_atr_wick_defaults():
    doc = _doc_with_custom(stoploss={"type": "atr_wick"})
    code = compile_freqtrade(doc)
    ast.parse(code)
    assert "ta.ATR(dataframe, timeperiod=14)" in code  # default period
    assert "atr * 1.5" in code                          # default multiplier


def test_custom_stoploss_unknown_type_raises():
    doc = _doc_with_custom(stoploss={"type": "wat"})
    with pytest.raises(ValueError, match="Unsupported custom_stoploss.type"):
        compile_freqtrade(doc)


def test_custom_exit_time_bailout_emits_method_15m():
    doc = _doc_with_custom(exit_block={"type": "time_bailout", "max_candles": 16, "tag": "tb"})
    code = compile_freqtrade(doc)
    ast.parse(code)
    assert "def custom_exit" in code
    # 16 candles * 15 minutes * 60 seconds = 14400
    assert "elapsed >= 14400" in code
    assert "return 'tb'" in code


def test_custom_exit_time_bailout_default_tag():
    doc = _doc_with_custom(exit_block={"type": "time_bailout", "max_candles": 8})
    code = compile_freqtrade(doc)
    ast.parse(code)
    assert "return 'time_bailout'" in code  # default tag


def test_custom_exit_unknown_type_raises():
    doc = _doc_with_custom(exit_block={"type": "wat"})
    with pytest.raises(ValueError, match="Unsupported custom_exit.type"):
        compile_freqtrade(doc)


def test_custom_hooks_omitted_when_not_configured():
    doc = _doc_with_custom()  # no custom blocks
    code = compile_freqtrade(doc)
    ast.parse(code)
    assert "use_custom_stoploss" not in code
    assert "def custom_stoploss" not in code
    assert "def custom_exit" not in code
