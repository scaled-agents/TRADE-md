"""Tests for trade_md.explain."""
from __future__ import annotations

from pathlib import Path

from trade_md.explain import explain_json, explain_text
from trade_md.parser import parse_file, parse_string

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_explain_text(example_doc):
    text = explain_text(example_doc)
    assert "heritage-rsi-ema" in text
    assert "0.3.1" in text
    assert "Thesis:" in text
    assert "Market:" in text
    assert "Risk:" in text
    assert "Sizing:" in text
    assert "Provenance:" in text
    assert "Lineage:" in text
    assert "Disable when:" in text


def test_explain_json(example_doc):
    data = explain_json(example_doc)
    assert data["strategy"]["name"] == "heritage-rsi-ema"
    assert data["strategy"]["version"] == "0.3.1"
    assert len(data["logic"]["entry_long_conditions"]) > 0
    assert data["risk_profile"]["stoploss"] == -0.03
    assert len(data["disable_when"]) == 4
    assert len(data["disable_when_humanized"]) == 4


def test_explain_text_no_provenance():
    doc = parse_string("""---
name: bare
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
## Thesis
Bare strategy.
## When to disable
Never.
""")
    text = explain_text(doc)
    assert "bare" in text
    assert "Provenance:" not in text


def test_explain_text_no_lineage():
    doc = parse_string("""---
name: no-lineage
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    text = explain_text(doc)
    assert "Lineage:" not in text


def test_explain_text_no_trailing():
    doc = parse_string("""---
name: no-trail
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}, trailing: {enabled: false}}
sizing: {method: fixed_stake, max_open_trades: 3}
---
""")
    text = explain_text(doc)
    assert "no trailing" in text


def test_explain_text_custom_indicators():
    """explain text includes custom indicators section."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    text = explain_text(doc)
    assert "Custom indicators:" in text
    assert "test_score" in text
    assert "indicators.test_ind" in text


def test_explain_json_custom_indicators():
    """explain JSON includes custom_indicators list."""
    doc = parse_file(FIXTURES_DIR / "strategy_dir")
    data = explain_json(doc)
    assert len(data["custom_indicators"]) == 1
    assert data["custom_indicators"][0]["as_name"] == "test_score"
    assert data["custom_indicators"][0]["version_pin"] == "1.0"
