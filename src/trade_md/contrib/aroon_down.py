"""Aroon Down — measures time since the lowest low.

100 * (period - bars_since_lowest) / period.
Values near 100 = recent new low (bearish), near 0 = no recent low.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam


@indicator(
    inputs=["low"],
    params={"period": IntParam(default=25, min=2, max=500)},
    outputs=["aroon_down"],
    description="Aroon Down — 100 * (N - bars_since_lowest_low) / N.",
    version="1.0.0",
)
def compute(df, period: int = 25):
    low = df["low"]

    def _aroon_down(values):
        if len(values) < period:
            return np.nan
        idx = np.argmin(values)
        return 100.0 * idx / (period - 1)

    return low.rolling(period).apply(_aroon_down, raw=True)
