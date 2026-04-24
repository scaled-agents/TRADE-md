"""Williams Alligator — Jaw line (SMMA 13, offset 8).

The slowest of the three alligator lines. Represents the "jaw" of the
alligator — when it opens (diverges from teeth/lips), a trend is forming.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam


def _smma(series, period):
    """Smoothed Moving Average (SMMA / Modified MA)."""
    result = np.full(len(series), np.nan)
    if len(series) < period:
        return result
    result[period - 1] = series[:period].mean()
    for i in range(period, len(series)):
        result[i] = (result[i - 1] * (period - 1) + series[i]) / period
    return result


@indicator(
    inputs=["high", "low"],
    params={
        "period": IntParam(default=13, min=2, max=200),
        "offset": IntParam(default=8, min=0, max=50),
    },
    outputs=["alligator_jaw"],
    description="Williams Alligator Jaw — SMMA(13) shifted forward by 8 bars.",
    version="1.0.0",
)
def compute(df, period: int = 13, offset: int = 8):
    hl2 = (df["high"].values + df["low"].values) / 2
    jaw = _smma(hl2, period)

    import pandas as pd
    result = pd.Series(jaw, index=df.index)
    if offset > 0:
        result = result.shift(offset)
    return result
