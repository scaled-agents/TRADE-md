"""Parabolic SAR (Stop and Reverse).

Implements Welles Wilder's Parabolic SAR with configurable acceleration
factor and maximum.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, FloatParam


@indicator(
    inputs=["high", "low", "close"],
    params={
        "af_start": FloatParam(default=0.02, min=0.001, max=0.1),
        "af_max": FloatParam(default=0.2, min=0.01, max=0.5),
    },
    outputs=["sar"],
    startup_candles=50,
    description="Parabolic SAR — trend-following stop level.",
    version="1.0.0",
)
def compute(df, af_start: float = 0.02, af_max: float = 0.2):
    high = df["high"].values
    low = df["low"].values
    n = len(high)

    sar = np.full(n, np.nan)
    if n < 2:
        import pandas as pd
        return pd.Series(sar, index=df.index)

    # Initialize: assume uptrend
    is_long = True
    af = af_start
    ep = high[0]
    sar[0] = low[0]

    for i in range(1, n):
        prev_sar = sar[i - 1]

        if is_long:
            sar_i = prev_sar + af * (ep - prev_sar)
            sar_i = min(sar_i, low[i - 1])
            if i >= 2:
                sar_i = min(sar_i, low[i - 2])

            if low[i] < sar_i:
                is_long = False
                sar_i = ep
                ep = low[i]
                af = af_start
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_start, af_max)
        else:
            sar_i = prev_sar + af * (ep - prev_sar)
            sar_i = max(sar_i, high[i - 1])
            if i >= 2:
                sar_i = max(sar_i, high[i - 2])

            if high[i] > sar_i:
                is_long = True
                sar_i = ep
                ep = high[i]
                af = af_start
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_start, af_max)

        sar[i] = sar_i

    import pandas as pd
    return pd.Series(sar, index=df.index)
