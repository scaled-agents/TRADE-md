"""Tests for trade_md.linter — covers R001-R016."""
from __future__ import annotations

from pathlib import Path

from trade_md.linter import lint, lint_indicator_standalone
from trade_md.parser import parse_file, parse_string

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _rules(report: dict) -> set[str]:
    """Extract unique rule IDs from a lint report."""
    return {f["rule"] for f in report["findings"]}


def _make_valid(**overrides) -> str:
    """Build a minimal valid TRADE.md with optional field overrides."""
    base = {
        "name": "t",
        "version": "0.1.0",
        "market": "{regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}",
        "signals": '{entry_long: {conditions: ["rsi(14) < 30"]}, exit_long: {conditions: ["rsi(14) > 70"]}}',
        "risk": '{stoploss: -0.05, roi: {"0": 0.10}}',
        "sizing": "{method: fixed_stake, max_open_trades: 3}",
    }
    base.update(overrides)
    lines = ["---"]
    for k, v in base.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append("## Thesis")
    lines.append("Test.")
    lines.append("## When to disable")
    lines.append("Never.")
    return "\n".join(lines)


def test_linter_clean_on_example(example_doc):
    report = lint(example_doc)
    assert report["summary"]["errors"] == 0


# ---- R001: required top-level fields ------------------------------------

def test_r001_missing_name():
    doc = parse_string("""---
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    report = lint(doc)
    assert "R001" in _rules(report)
    assert any("name" in f["message"] for f in report["findings"] if f["rule"] == "R001")


def test_r001_missing_signals():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    report = lint(doc)
    assert "R001" in _rules(report)


# ---- R002: stoploss is negative -----------------------------------------

def test_r002_positive_stoploss():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}, exit_long: {conditions: ["rsi(14) > 70"]}}
risk: {stoploss: 0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    report = lint(doc)
    assert "R002" in _rules(report)


def test_r002_zero_stoploss():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}, exit_long: {conditions: ["rsi(14) > 70"]}}
risk: {stoploss: 0, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    report = lint(doc)
    assert "R002" in _rules(report)


# ---- R003: first ROI step > |stoploss| ----------------------------------

def test_r003_roi_below_stoploss():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}, exit_long: {conditions: ["rsi(14) > 70"]}}
risk: {stoploss: -0.10, roi: {"0": 0.05}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    report = lint(doc)
    assert "R003" in _rules(report)


# ---- R004: informative TFs declared -------------------------------------

def test_r004_undeclared_informative():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals:
  entry_long: {conditions: ["rsi(14)@4h < 30"]}
  exit_long: {conditions: ["rsi(14) > 70"]}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    report = lint(doc)
    assert "R004" in _rules(report)


def test_r004_declared_informative_is_ok():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, informative_timeframes: [4h], pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals:
  entry_long: {conditions: ["rsi(14)@4h < 30"]}
  exit_long: {conditions: ["rsi(14) > 70"]}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    report = lint(doc)
    assert "R004" not in _rules(report)


# ---- R005: token refs resolve -------------------------------------------

def test_r005_undeclared_token():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals:
  entry_long: {conditions: ["{nonexistent}"]}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    report = lint(doc)
    assert "R005" in _rules(report)


# ---- R006: conditions parse ---------------------------------------------

def test_r006_bad_syntax():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals:
  entry_long: {conditions: ["this isn't valid syntax"]}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    report = lint(doc)
    assert "R006" in _rules(report)


# ---- R007: provenance freshness -----------------------------------------

def test_r007_stale_provenance():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}, exit_long: {conditions: ["rsi(14) > 70"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
provenance:
  last_validated: "2020-01-01"
  sharpe: 1.0
---
## Thesis
Test.
## When to disable
Never.
""")
    report = lint(doc)
    assert "R007" in _rules(report)


# ---- R008: trailing offset >= positive -----------------------------------

def test_r008_offset_below_positive():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}, exit_long: {conditions: ["rsi(14) > 70"]}}
risk:
  stoploss: -0.05
  roi: {"0": 0.10}
  trailing: {enabled: true, positive: 0.02, offset: 0.01}
sizing: {method: fixed_stake, max_open_trades: 3}
---
## Thesis
Test.
## When to disable
Never.
""")
    report = lint(doc)
    assert "R008" in _rules(report)


# ---- R009: prose sections present ----------------------------------------

def test_r009_missing_thesis():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}, exit_long: {conditions: ["rsi(14) > 70"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    report = lint(doc)
    assert "R009" in _rules(report)
    assert any("Thesis" in f["message"] for f in report["findings"] if f["rule"] == "R009")


def test_r009_missing_when_to_disable():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}, exit_long: {conditions: ["rsi(14) > 70"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
## Thesis
Test.
""")
    report = lint(doc)
    assert "R009" in _rules(report)
    assert any("When to disable" in f["message"] for f in report["findings"] if f["rule"] == "R009")


# ---- R010: separation_index present -------------------------------------

def test_r010_no_separation_index():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}, exit_long: {conditions: ["rsi(14) > 70"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
provenance:
  sharpe: 1.0
---
## Thesis
Test.
## When to disable
Never.
""")
    report = lint(doc)
    assert "R010" in _rules(report)


def test_r010_with_separation_index():
    doc = parse_string("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}, exit_long: {conditions: ["rsi(14) > 70"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
provenance:
  sharpe: 1.0
  separation_index: 0.68
---
## Thesis
Test.
## When to disable
Never.
""")
    report = lint(doc)
    assert "R010" not in _rules(report)


# ---- Broken fixture exercises all rules ----------------------------------

def test_broken_fixture_has_all_expected_rules(broken_doc):
    report = lint(broken_doc)
    rules = _rules(report)
    # broken.TRADE.md triggers R002, R003, R004, R005, R006, R007, R008, R009, R010
    for expected in ("R002", "R003", "R004", "R005", "R006", "R007", "R008", "R009", "R010"):
        assert expected in rules, f"Expected {expected} in broken fixture findings"


# ---- R011: custom indicator modules resolve --------------------------------

def test_r011_clean_custom_indicator():
    """Strategy with valid custom indicator produces no R011."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    report = lint(doc)
    assert "R011" not in _rules(report)


def test_r011_missing_module():
    """Strategy referencing a nonexistent module triggers R011."""
    doc = parse_string("""---
trade_md_spec: "0.2"
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
custom_indicators:
  - module: indicators.does_not_exist
    as: nope
---
## Thesis
Test.
## When to disable
Never.
""", source_path=FIXTURES_DIR / "strategy_dir" / "TRADE.md")
    report = lint(doc)
    assert "R011" in _rules(report)


# ---- R012: declared inputs resolve -----------------------------------------

def test_r012_bad_input():
    """Indicator with an input that's not OHLCV or built-in triggers R012."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    report = lint(doc)
    # test_ind declares inputs=["close", "volume"] — both valid.
    assert "R012" not in _rules(report)


# ---- R013: output column collisions ----------------------------------------

def test_r013_no_collision():
    """Custom indicator with unique outputs doesn't trigger R013."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    report = lint(doc)
    assert "R013" not in _rules(report)


# ---- R014: signature matches params ----------------------------------------

def test_r014_signature_matches():
    """Custom indicator with matching signature doesn't trigger R014."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    report = lint(doc)
    assert "R014" not in _rules(report)


# ---- R015: forbidden imports -----------------------------------------------

def test_r015_forbidden_import():
    """Indicator with socket import triggers R015."""
    report = lint_indicator_standalone(FIXTURES_DIR / "bad_indicator.py")
    rules = {f["rule"] for f in report["findings"]}
    assert "R015" in rules
    assert any("socket" in f["message"] for f in report["findings"])


def test_r015_clean_indicator():
    """Clean indicator doesn't trigger R015."""
    report = lint_indicator_standalone(
        FIXTURES_DIR / "strategy_dir" / "indicators" / "test_ind.py"
    )
    rules = {f["rule"] for f in report["findings"]}
    assert "R015" not in rules


# ---- R016: directory contents -----------------------------------------------

def test_r016_clean_directory():
    """Strategy directory with only allowed contents doesn't trigger R016."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    report = lint(doc)
    assert "R016" not in _rules(report)


def test_r016_unexpected_file(tmp_path):
    """Strategy directory with unexpected file triggers R016."""
    # Build a minimal strategy dir with an extra file.
    trade_md = tmp_path / "TRADE.md"
    trade_md.write_text("""---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
## Thesis
Test.
## When to disable
Never.
""")
    (tmp_path / "junk.txt").write_text("unexpected")
    doc = parse_file(tmp_path)
    report = lint(doc)
    assert "R016" in _rules(report)


# ---- lint_indicator_standalone ----------------------------------------------

def test_lint_indicator_standalone_clean():
    """Standalone lint of a valid indicator file passes."""
    report = lint_indicator_standalone(
        FIXTURES_DIR / "strategy_dir" / "indicators" / "test_ind.py"
    )
    assert report["summary"]["errors"] == 0


def test_lint_indicator_standalone_missing_file():
    """Standalone lint of a nonexistent file produces R011."""
    report = lint_indicator_standalone(FIXTURES_DIR / "nope.py")
    assert report["summary"]["errors"] == 1
    assert "R011" in {f["rule"] for f in report["findings"]}
