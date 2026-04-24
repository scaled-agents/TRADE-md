"""SuperTrend — trend-following indicator value.

Returns the SuperTrend level: support in uptrend, resistance in downtrend.
Use supertrend_direction for the +1/-1 signal.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam, FloatParam


@indicator(
    inputs=["high", "low", "close"],
    params={
        "period": IntParam(default=10, min=2, max=500),
        "multiplier": FloatParam(default=3.0, min=0.1, max=10.0),
    },
    outputs=["supertrend"],
    description="SuperTrend value — support in uptrend, resistance in downtrend.",
    version="1.0.0",
)
def compute(df, period: int = 10, multiplier: float = 3.0):
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(close)

    st = np.full(n, np.nan)
    if n < period:
        import pandas as pd
        return pd.Series(st, index=df.index)

    # ATR via rolling true range
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(abs(high - prev_close), abs(low - prev_close)))

    atr = np.full(n, np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    direction = np.ones(n)  # 1 = up, -1 = down

    for i in range(1, n):
        if np.isnan(atr[i]):
            st[i] = np.nan
            continue

        if close[i - 1] > upper_band[i - 1]:
            direction[i] = 1
        elif close[i - 1] < lower_band[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]

        if direction[i] == 1:
            lower_band[i] = max(lower_band[i], lower_band[i - 1]) if direction[i - 1] == 1 else lower_band[i]
            st[i] = lower_band[i]
        else:
            upper_band[i] = min(upper_band[i], upper_band[i - 1]) if direction[i - 1] == -1 else upper_band[i]
            st[i] = upper_band[i]

    import pandas as pd
    return pd.Series(st, index=df.index)
