"""Aroon Up — measures time since the highest high.

100 * (period - bars_since_highest) / period.
Values near 100 = recent new high (bullish), near 0 = no recent high.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam


@indicator(
    inputs=["high"],
    params={"period": IntParam(default=25, min=2, max=500)},
    outputs=["aroon_up"],
    description="Aroon Up — 100 * (N - bars_since_highest_high) / N.",
    version="1.0.0",
)
def compute(df, period: int = 25):
    high = df["high"]

    def _aroon_up(values):
        if len(values) < period:
            return np.nan
        idx = np.argmax(values)
        return 100.0 * idx / (period - 1)

    return high.rolling(period).apply(_aroon_up, raw=True)
