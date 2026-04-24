"""Choppiness Index — measures market trendiness vs choppiness.

Values above 61.8 suggest choppy/range-bound; below 38.2 suggest trending.
Formula: 100 * LOG10(SUM(ATR,N) / (Highest-Lowest over N)) / LOG10(N)
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam


@indicator(
    inputs=["high", "low", "close"],
    params={"period": IntParam(default=14, min=2, max=500)},
    outputs=["chop"],
    description="Choppiness Index — 100 * log10(sum(ATR)/range) / log10(N).",
    version="1.0.0",
)
def compute(df, period: int = 14):
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # True range
    prev_close = close.shift(1)
    tr = np.maximum(high - low, np.maximum(abs(high - prev_close), abs(low - prev_close)))

    atr_sum = tr.rolling(period).sum()
    highest = high.rolling(period).max()
    lowest = low.rolling(period).min()
    hl_range = highest - lowest

    return 100 * np.log10(atr_sum / hl_range.replace(0, np.nan)) / np.log10(period)
