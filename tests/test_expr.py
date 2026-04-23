"""Tests for trade_md.expr."""
from __future__ import annotations

import pytest

from trade_md.expr import compile_conditions, compile_expression


def test_expr_simple():
    r = compile_expression("rsi(14) < 30")
    assert r.mask_expr == "dataframe['rsi_14'] < 30"
    assert {u.col for u in r.uses} == {"rsi_14"}


def test_expr_token_ref():
    inds = {"tf": {"expr": "close > ema(200)"}}
    r = compile_expression("{tf}", inds)
    assert "dataframe['close']" in r.mask_expr
    assert "dataframe['ema_200']" in r.mask_expr


def test_expr_htf():
    r = compile_expression("close@1h > ema(50)@1h")
    assert r.timeframes == {"1h"}
    assert "close_1h" in r.mask_expr
    assert "ema_50_1h" in r.mask_expr


def test_expr_rolling():
    r = compile_expression("volume > volume.rolling(20).mean()")
    cols = {u.col for u in r.uses}
    assert "volume_roll_20_mean" in cols


def test_expr_or_becomes_bitwise_or():
    r = compile_expression("rsi(14) < 30 or rsi(14) > 70")
    assert " | " in r.mask_expr
    assert " or " not in r.mask_expr


def test_expr_and_becomes_bitwise_and():
    r = compile_conditions(["rsi(14) < 30", "close > ema(200)"])
    assert " & " in r.mask_expr
    assert " and " not in r.mask_expr


def test_expr_unknown_function():
    with pytest.raises(ValueError, match="Unknown function"):
        compile_expression("fnord(42) < 10")


def test_expr_unknown_token():
    with pytest.raises(ValueError, match="Unknown indicator token"):
        compile_expression("{does_not_exist}", {})


def test_expr_crosses_above():
    r = compile_expression("crosses_above(ema(20), ema(50))")
    cols = {u.col for u in r.uses}
    assert "ema_20" in cols
    assert "ema_50" in cols
    assert "ema_20_shift_1" in cols
    assert "ema_50_shift_1" in cols
