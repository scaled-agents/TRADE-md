"""Tests for trade_md.linter — covers R001-R010."""
from __future__ import annotations

from trade_md.linter import lint
from trade_md.parser import parse_string


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
