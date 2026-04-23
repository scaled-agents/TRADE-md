"""Tests for trade_md.expr."""
from __future__ import annotations

import pytest

from trade_md.expr import compile_conditions, compile_expression
from trade_md.indicator import IndicatorMetadata
from trade_md.params import FloatParam, IntParam


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


def test_expr_adx():
    r = compile_expression("adx(14) > 25")
    assert r.mask_expr == "dataframe['adx_14'] > 25"
    assert {u.col for u in r.uses} == {"adx_14"}
    assert r.uses[0].kind == "builtin"
    assert r.uses[0].name == "adx"


def test_expr_crosses_above():
    r = compile_expression("crosses_above(ema(20), ema(50))")
    cols = {u.col for u in r.uses}
    assert "ema_20" in cols
    assert "ema_50" in cols
    assert "ema_20_shift_1" in cols
    assert "ema_50_shift_1" in cols


# ---- Custom indicator tests ----

def _make_custom_meta(
    name="test_ind",
    inputs=None,
    params=None,
    outputs=None,
    startup_candles=0,
    version="1.0.0",
):
    return IndicatorMetadata(
        inputs=inputs or ["close"],
        params=params or {"lookback": IntParam(default=100, min=10, max=500)},
        outputs=outputs or ["test_ind"],
        startup_candles=startup_candles,
        description="test",
        version=version,
        func_name="compute",
    )


def test_custom_indicator_basic():
    meta = _make_custom_meta()
    r = compile_expression(
        "test_ind(lookback=100) > 0.6",
        custom_indicators={"test_ind": meta},
    )
    assert "dataframe['test_ind_l100']" in r.mask_expr
    custom_uses = [u for u in r.uses if u.kind == "custom"]
    assert len(custom_uses) == 1
    assert custom_uses[0].name == "test_ind"


def test_custom_indicator_multiple_params():
    meta = _make_custom_meta(
        params={
            "lookback": IntParam(default=100, min=10, max=500),
            "smoothing": FloatParam(default=0.1, min=0.0, max=1.0),
        },
    )
    r = compile_expression(
        "test_ind(lookback=100, smoothing=0.1) > 0.6",
        custom_indicators={"test_ind": meta},
    )
    # Column name includes both param abbreviations, sorted by param name.
    assert "test_ind_l100_s0p1" in r.mask_expr


def test_custom_indicator_default_params():
    meta = _make_custom_meta(
        params={"lookback": IntParam(default=100, min=10, max=500)},
    )
    # Call without explicit value -- default fills in.
    r = compile_expression(
        "test_ind() > 0.6",
        custom_indicators={"test_ind": meta},
    )
    assert "test_ind_l100" in r.mask_expr


def test_custom_indicator_param_validation():
    meta = _make_custom_meta(
        params={"lookback": IntParam(default=100, min=10, max=500)},
    )
    with pytest.raises(ValueError, match="below minimum"):
        compile_expression(
            "test_ind(lookback=5) > 0.6",
            custom_indicators={"test_ind": meta},
        )


def test_custom_indicator_unknown_param():
    meta = _make_custom_meta(
        params={"lookback": IntParam(default=100)},
    )
    with pytest.raises(ValueError, match="Unknown parameter"):
        compile_expression(
            "test_ind(bogus=42) > 0.6",
            custom_indicators={"test_ind": meta},
        )


def test_custom_indicator_htf():
    meta = _make_custom_meta()
    r = compile_expression(
        "test_ind(lookback=200)@1h > 0.5",
        custom_indicators={"test_ind": meta},
    )
    assert r.timeframes == {"1h"}
    custom_uses = [u for u in r.uses if u.kind == "custom"]
    assert len(custom_uses) == 1
    assert custom_uses[0].timeframe == "1h"
    assert "1h" in custom_uses[0].col


def test_custom_indicator_dedup():
    meta = _make_custom_meta()
    r = compile_conditions(
        ["test_ind(lookback=100) > 0.6", "test_ind(lookback=100) < 0.9"],
        custom_indicators={"test_ind": meta},
    )
    custom_uses = [u for u in r.uses if u.kind == "custom"]
    assert len(custom_uses) == 1  # Deduplicated


def test_custom_indicator_positional_rejected():
    meta = _make_custom_meta()
    with pytest.raises(ValueError, match="keyword arguments"):
        compile_expression(
            "test_ind(100) > 0.6",
            custom_indicators={"test_ind": meta},
        )


def test_builtin_takes_precedence():
    """A custom indicator cannot shadow a built-in."""
    meta = _make_custom_meta()
    # rsi is a builtin; even if registered as custom, builtin wins.
    r = compile_expression(
        "rsi(14) < 30",
        custom_indicators={"rsi": meta},
    )
    # Should be treated as builtin rsi, not custom.
    assert "rsi_14" in r.mask_expr
    custom_uses = [u for u in r.uses if u.kind == "custom"]
    assert len(custom_uses) == 0
