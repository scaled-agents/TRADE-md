"""Kaufman Adaptive Moving Average (KAMA).

Adapts its smoothing constant based on the efficiency ratio — fast during
trends, slow during chop.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam


@indicator(
    inputs=["close"],
    params={
        "period": IntParam(default=10, min=2, max=500),
        "fast_period": IntParam(default=2, min=2, max=50),
        "slow_period": IntParam(default=30, min=5, max=200),
    },
    outputs=["kama"],
    description="Kaufman Adaptive Moving Average — adapts speed to market conditions.",
    version="1.0.0",
)
def compute(df, period: int = 10, fast_period: int = 2, slow_period: int = 30):
    close = df["close"].values
    n = len(close)

    fast_sc = 2.0 / (fast_period + 1)
    slow_sc = 2.0 / (slow_period + 1)

    kama = np.full(n, np.nan)
    if n < period:
        import pandas as pd
        return pd.Series(kama, index=df.index)

    kama[period - 1] = close[period - 1]

    for i in range(period, n):
        direction = abs(close[i] - close[i - period])
        volatility = sum(abs(close[j] - close[j - 1]) for j in range(i - period + 1, i + 1))

        if volatility == 0:
            er = 0.0
        else:
            er = direction / volatility

        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        kama[i] = kama[i - 1] + sc * (close[i] - kama[i - 1])

    import pandas as pd
    return pd.Series(kama, index=df.index)
