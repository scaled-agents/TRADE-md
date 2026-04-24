"""Bollinger Band / Keltner Channel Squeeze detection.

Returns 1.0 when BB is inside KC (squeeze on), 0.0 otherwise.
Used by the LuxAlgo Breakout Suite and similar momentum strategies.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam, FloatParam


@indicator(
    inputs=["high", "low", "close"],
    params={
        "bb_period": IntParam(default=20, min=2, max=500),
        "bb_mult": FloatParam(default=2.0, min=0.1, max=5.0),
        "kc_period": IntParam(default=20, min=2, max=500),
        "kc_mult": FloatParam(default=1.5, min=0.1, max=5.0),
    },
    outputs=["bb_kc_squeeze"],
    description="Squeeze detection — 1.0 when Bollinger Bands are inside Keltner Channels.",
    version="1.0.0",
)
def compute(df, bb_period: int = 20, bb_mult: float = 2.0,
            kc_period: int = 20, kc_mult: float = 1.5):
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # Bollinger Bands
    bb_sma = close.rolling(bb_period).mean()
    bb_std = close.rolling(bb_period).std()
    bb_upper = bb_sma + bb_mult * bb_std
    bb_lower = bb_sma - bb_mult * bb_std

    # Keltner Channels (using ATR)
    prev_close = close.shift(1)
    tr = np.maximum(high - low,
                    np.maximum(abs(high - prev_close), abs(low - prev_close)))
    atr = tr.rolling(kc_period).mean()
    kc_mid = close.rolling(kc_period).mean()
    kc_upper = kc_mid + kc_mult * atr
    kc_lower = kc_mid - kc_mult * atr

    # Squeeze: BB inside KC
    squeeze = ((bb_lower > kc_lower) & (bb_upper < kc_upper)).astype(float)
    return squeeze
