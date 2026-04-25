"""LuxAlgo Squeeze Momentum — linear regression of close deviation from midpoint.

Used by the LuxAlgo Breakout Suite. Momentum = LINEARREG(close - midpoint, N)
where midpoint = (highest_high + lowest_low + SMA) / 3 over a lookback window.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam


@indicator(
    inputs=["high", "low", "close"],
    params={
        "mom_period": IntParam(default=19, min=2, max=100),
        "lookback": IntParam(default=20, min=2, max=500),
    },
    outputs=["luxalgo_momentum"],
    description="LuxAlgo squeeze momentum — LINEARREG(close - midpoint, N).",
    version="1.0.0",
)
def compute(df, mom_period: int = 19, lookback: int = 20):
    close = df["close"]
    high = df["high"]
    low = df["low"]

    sma = close.rolling(lookback).mean()
    highest = high.rolling(lookback).max()
    lowest = low.rolling(lookback).min()
    midpoint = (highest + lowest + sma) / 3.0
    mom_source = close - midpoint

    def _linreg(values):
        n = len(values)
        if n < 2:
            return np.nan
        x = np.arange(n)
        x_mean = x.mean()
        y_mean = values.mean()
        denom = ((x - x_mean) ** 2).sum()
        if denom == 0:
            return 0.0
        slope = ((x - x_mean) * (values - y_mean)).sum() / denom
        return y_mean + slope * (n - 1)

    return mom_source.rolling(mom_period).apply(_linreg, raw=True)
