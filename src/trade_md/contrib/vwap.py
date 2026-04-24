"""Volume-Weighted Average Price (VWAP).

Rolling VWAP over a configurable window (not session-based).
"""
from __future__ import annotations

from trade_md import indicator, IntParam


@indicator(
    inputs=["high", "low", "close", "volume"],
    params={"period": IntParam(default=20, min=2, max=1000)},
    outputs=["vwap"],
    description="Rolling VWAP — sum(TP*volume) / sum(volume) over N bars.",
    version="1.0.0",
)
def compute(df, period: int = 20):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    tp_vol = tp * df["volume"]
    return tp_vol.rolling(period).sum() / df["volume"].rolling(period).sum()
