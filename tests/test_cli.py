"""Tests for trade_md.cli."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from trade_md.cli import main


def test_cli_lint_clean(example_doc, capsys):
    path = str(example_doc.source_path)
    rc = main(["lint", path])
    assert rc == 0
    captured = capsys.readouterr()
    assert "errors:" in captured.out


def test_cli_lint_broken(broken_fixture_path, capsys):
    rc = main(["lint", str(broken_fixture_path)])
    assert rc == 1


def test_cli_lint_json(example_doc, capsys):
    path = str(example_doc.source_path)
    rc = main(["lint", path, "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["errors"] == 0


def test_cli_explain(example_doc, capsys):
    path = str(example_doc.source_path)
    rc = main(["explain", path])
    assert rc == 0
    captured = capsys.readouterr()
    assert "heritage-rsi-ema" in captured.out


def test_cli_explain_json(example_doc, capsys):
    path = str(example_doc.source_path)
    rc = main(["explain", path, "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["strategy"]["name"] == "heritage-rsi-ema"


def test_cli_compile(example_doc, capsys):
    path = str(example_doc.source_path)
    rc = main(["compile", "--target", "freqtrade", path])
    assert rc == 0
    captured = capsys.readouterr()
    assert "class HeritageRsiEma" in captured.out


def test_cli_compile_to_file(example_doc, tmp_path):
    path = str(example_doc.source_path)
    out = str(tmp_path / "out.py")
    rc = main(["compile", "--target", "freqtrade", path, "-o", out])
    assert rc == 0
    assert Path(out).exists()
    ast.parse(Path(out).read_text())


def test_cli_compile_unknown_target(example_doc, capsys):
    path = str(example_doc.source_path)
    rc = main(["compile", "--target", "hummingbot", path])
    assert rc == 2


def test_cli_spec_rules(capsys):
    rc = main(["spec", "--rules-only"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "R001" in captured.out


def test_cli_spec_rules_json(capsys):
    rc = main(["spec", "--rules-only", "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["rules"]) == 16


def test_cli_diff_no_regression(tmp_path, capsys):
    """Diff two versions with improved metrics - exit 0."""
    v1 = """---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
provenance: {sharpe: 1.0, max_dd: 0.15}
---
"""
    v2 = """---
name: t
version: 0.2.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
provenance: {sharpe: 1.5, max_dd: 0.10}
---
"""
    f1 = tmp_path / "v1.TRADE.md"
    f2 = tmp_path / "v2.TRADE.md"
    f1.write_text(v1)
    f2.write_text(v2)
    rc = main(["diff", str(f1), str(f2)])
    assert rc == 0


def test_cli_diff_regression(tmp_path, capsys):
    """Diff two versions with worsened metrics - exit 1."""
    v1 = """---
name: t
version: 0.1.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
provenance: {sharpe: 1.5, max_dd: 0.10}
---
"""
    v2 = """---
name: t
version: 0.2.0
market: {regime: [trending], timeframe: 5m, pair_universe: {quote: USDT, exchange: binance, filter: top50_volume}}
signals: {entry_long: {conditions: ["rsi(14) < 30"]}}
risk: {stoploss: -0.05, roi: {"0": 0.10}}
sizing: {method: fixed_stake, max_open_trades: 3}
provenance: {sharpe: 1.0, max_dd: 0.15}
---
"""
    f1 = tmp_path / "v1.TRADE.md"
    f2 = tmp_path / "v2.TRADE.md"
    f1.write_text(v1)
    f2.write_text(v2)
    rc = main(["diff", str(f1), str(f2)])
    assert rc == 1
