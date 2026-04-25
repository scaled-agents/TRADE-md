"""Aroon Oscillator — Aroon Up minus Aroon Down.

Positive = bullish momentum, negative = bearish momentum.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam


@indicator(
    inputs=["high", "low"],
    params={"period": IntParam(default=25, min=2, max=500)},
    outputs=["aroon_osc"],
    description="Aroon Oscillator — Aroon Up - Aroon Down.",
    version="1.0.0",
)
def compute(df, period: int = 25):
    high = df["high"]
    low = df["low"]

    def _aroon_up(values):
        if len(values) < period:
            return np.nan
        return 100.0 * np.argmax(values) / (period - 1)

    def _aroon_down(values):
        if len(values) < period:
            return np.nan
        return 100.0 * np.argmin(values) / (period - 1)

    up = high.rolling(period).apply(_aroon_up, raw=True)
    down = low.rolling(period).apply(_aroon_down, raw=True)
    return up - down
