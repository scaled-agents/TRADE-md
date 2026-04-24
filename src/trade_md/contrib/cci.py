"""Commodity Channel Index (CCI).

Measures the deviation of the typical price from its simple moving average.
"""
from __future__ import annotations

from trade_md import indicator, IntParam


@indicator(
    inputs=["high", "low", "close"],
    params={"period": IntParam(default=20, min=2, max=500)},
    outputs=["cci"],
    description="Commodity Channel Index — (TP - SMA(TP)) / (0.015 * MAD(TP)).",
    version="1.0.0",
)
def compute(df, period: int = 20):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: abs(x - x.mean()).mean(), raw=True)
    return (tp - sma) / (0.015 * mad)
