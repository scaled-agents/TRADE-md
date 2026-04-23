"""Test indicator for fixtures."""
from __future__ import annotations

from trade_md import indicator, IntParam, FloatParam


@indicator(
    inputs=["close", "volume"],
    params={
        "lookback": IntParam(default=100, min=20, max=500),
        "smoothing": FloatParam(default=0.1, min=0.0, max=1.0),
    },
    outputs=["test_score"],
    startup_candles=100,
    description="Test indicator for unit tests.",
    version="1.0.0",
)
def compute(df, lookback: int = 100, smoothing: float = 0.1):
    return df["close"] * 0
