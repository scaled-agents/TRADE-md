"""Directional Movement Index — Plus DI (+DI).

Measures upward directional movement strength.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam


@indicator(
    inputs=["high", "low", "close"],
    params={"period": IntParam(default=14, min=2, max=500)},
    outputs=["dmi_plus_di"],
    description="Plus Directional Indicator (+DI) — upward movement strength.",
    version="1.0.0",
)
def compute(df, period: int = 14):
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    # Directional movement
    plus_dm = np.where((high - prev_high) > (prev_low - low),
                       np.maximum(high - prev_high, 0), 0)

    # True range
    tr = np.maximum(high - low,
                    np.maximum(abs(high - prev_close), abs(low - prev_close)))

    import pandas as pd
    plus_dm_s = pd.Series(plus_dm, index=df.index).rolling(period).sum()
    tr_s = pd.Series(tr, index=df.index).rolling(period).sum()

    return 100 * plus_dm_s / tr_s.replace(0, np.nan)
