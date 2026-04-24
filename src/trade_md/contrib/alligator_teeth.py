"""Williams Alligator — Teeth line (SMMA 8, offset 5)."""
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
        "period": IntParam(default=8, min=2, max=200),
        "offset": IntParam(default=5, min=0, max=50),
    },
    outputs=["alligator_teeth"],
    description="Williams Alligator Teeth — SMMA(8) shifted forward by 5 bars.",
    version="1.0.0",
)
def compute(df, period: int = 8, offset: int = 5):
    hl2 = (df["high"].values + df["low"].values) / 2
    teeth = _smma(hl2, period)

    import pandas as pd
    result = pd.Series(teeth, index=df.index)
    if offset > 0:
        result = result.shift(offset)
    return result
