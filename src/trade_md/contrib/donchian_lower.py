"""Donchian Channel — lower band (rolling min of low)."""
from __future__ import annotations

from trade_md import indicator, IntParam


@indicator(
    inputs=["low"],
    params={"period": IntParam(default=20, min=2, max=500)},
    outputs=["donchian_lower"],
    description="Donchian Channel lower band — rolling min of low.",
    version="1.0.0",
)
def compute(df, period: int = 20):
    return df["low"].rolling(period).min()
