"""Keltner Channel — Upper Band.

KC Upper = EMA(period) + ATR(period) * mult.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam, FloatParam


@indicator(
    inputs=["high", "low", "close"],
    params={
        "period": IntParam(default=20, min=2, max=500),
        "mult": FloatParam(default=2.0, min=0.1, max=5.0),
    },
    outputs=["kc_upper"],
    description="Keltner Channel upper band — EMA + ATR * mult.",
    version="1.0.0",
)
def compute(df, period: int = 20, mult: float = 2.0):
    close = df["close"]
    high = df["high"]
    low = df["low"]

    ema = close.ewm(span=period, adjust=False).mean()

    prev_close = close.shift(1)
    tr = np.maximum(high - low,
                    np.maximum(abs(high - prev_close), abs(low - prev_close)))
    atr = tr.rolling(period).mean()

    return ema + atr * mult
