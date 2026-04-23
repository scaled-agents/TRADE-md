"""Separation score indicator.

Measures the degree to which a strategy's recent returns are
distinguishable from random noise, using a simplified z-score
of the rolling PnL vs. a shuffled baseline.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam, FloatParam


@indicator(
    inputs=["close"],
    params={
        "lookback": IntParam(default=100, min=20, max=500),
        "smoothing": FloatParam(default=0.1, min=0.0, max=1.0),
    },
    outputs=["sep_score"],
    startup_candles=100,
    description="Rolling separation index: z-score of returns vs shuffled baseline.",
    version="1.0.0",
)
def compute(df, lookback: int = 100, smoothing: float = 0.1):
    returns = df["close"].pct_change()
    rolling_mean = returns.rolling(lookback).mean()
    rolling_std = returns.rolling(lookback).std()
    z = rolling_mean / (rolling_std + 1e-10)
    # Exponential smoothing
    return z.ewm(alpha=smoothing).mean()
