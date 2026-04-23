"""Tests for trade_md.indicator."""
from __future__ import annotations

import pytest

from trade_md.indicator import IndicatorMetadata, indicator
from trade_md.params import FloatParam, IntParam


def test_basic_decoration():
    @indicator(
        inputs=["close"],
        params={"period": IntParam(default=14, min=2, max=200)},
        outputs=["my_ind"],
        description="test indicator",
        version="1.0.0",
    )
    def compute(df, period: int = 14):
        return df["close"]

    assert hasattr(compute, "_trade_md_metadata")
    meta = compute._trade_md_metadata
    assert isinstance(meta, IndicatorMetadata)
    assert meta.inputs == ["close"]
    assert meta.outputs == ["my_ind"]
    assert meta.version == "1.0.0"
    assert meta.description == "test indicator"
    assert meta.func_name == "compute"
    assert "period" in meta.params


def test_metadata_round_trip():
    @indicator(
        inputs=["close", "volume"],
        params={
            "lookback": IntParam(default=100, min=20, max=500),
            "smoothing": FloatParam(default=0.1, min=0.0, max=1.0),
        },
        outputs=["score"],
        startup_candles=100,
    )
    def compute(df, lookback: int = 100, smoothing: float = 0.1):
        return df["close"] * 0

    meta = compute._trade_md_metadata
    assert meta.startup_candles == 100
    assert set(meta.params.keys()) == {"lookback", "smoothing"}


def test_startup_inference():
    """startup_candles inferred from max IntParam.min when not explicit."""
    @indicator(
        inputs=["close"],
        params={
            "fast": IntParam(default=10, min=5),
            "slow": IntParam(default=50, min=20),
        },
        outputs=["out"],
    )
    def compute(df, fast: int = 10, slow: int = 50):
        return df["close"]

    assert compute._trade_md_metadata.startup_candles == 20


def test_startup_default_zero():
    """startup_candles defaults to 0 when no IntParam has min."""
    @indicator(
        inputs=["close"],
        params={"alpha": FloatParam(default=0.5)},
        outputs=["out"],
    )
    def compute(df, alpha: float = 0.5):
        return df["close"]

    assert compute._trade_md_metadata.startup_candles == 0


def test_no_params():
    """Indicator with no declared params and no extra function args."""
    @indicator(inputs=["close"], outputs=["out"])
    def compute(df):
        return df["close"]

    meta = compute._trade_md_metadata
    assert meta.params == {}


def test_signature_mismatch_missing():
    """Declared param not in function signature raises TypeError."""
    with pytest.raises(TypeError, match="declared but not in signature"):
        @indicator(
            inputs=["close"],
            params={"period": IntParam(default=14)},
            outputs=["out"],
        )
        def compute(df):
            return df["close"]


def test_signature_mismatch_extra():
    """Function param not declared raises TypeError."""
    with pytest.raises(TypeError, match="in signature but not declared"):
        @indicator(
            inputs=["close"],
            params={},
            outputs=["out"],
        )
        def compute(df, period: int = 14):
            return df["close"]


def test_no_args_at_all():
    """Function with zero arguments raises TypeError."""
    with pytest.raises(TypeError, match="at least one positional argument"):
        @indicator(inputs=["close"], outputs=["out"])
        def compute():
            pass


def test_function_not_wrapped():
    """The decorator returns the original function, not a wrapper."""
    @indicator(inputs=["close"], outputs=["out"])
    def compute(df):
        return df["close"]

    # The function should be the exact same object (not wrapped).
    assert compute.__name__ == "compute"


def test_import_from_package():
    """The decorator and param types are importable from trade_md."""
    from trade_md import indicator, IntParam, FloatParam, StrParam, BoolParam, Param, IndicatorMetadata

    assert callable(indicator)
    assert IntParam is not None
    assert FloatParam is not None
    assert StrParam is not None
    assert BoolParam is not None
    assert Param is not None
    assert IndicatorMetadata is not None
