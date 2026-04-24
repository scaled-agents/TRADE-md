"""Donchian Channel — middle band (midpoint of upper and lower)."""
from __future__ import annotations

from trade_md import indicator, IntParam


@indicator(
    inputs=["high", "low"],
    params={"period": IntParam(default=20, min=2, max=500)},
    outputs=["donchian_middle"],
    description="Donchian Channel middle band — midpoint of rolling max/min.",
    version="1.0.0",
)
def compute(df, period: int = 20):
    upper = df["high"].rolling(period).max()
    lower = df["low"].rolling(period).min()
    return (upper + lower) / 2
