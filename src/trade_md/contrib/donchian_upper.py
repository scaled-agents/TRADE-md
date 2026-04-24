"""Donchian Channel — upper band (rolling max of high)."""
from __future__ import annotations

from trade_md import indicator, IntParam


@indicator(
    inputs=["high"],
    params={"period": IntParam(default=20, min=2, max=500)},
    outputs=["donchian_upper"],
    description="Donchian Channel upper band — rolling max of high.",
    version="1.0.0",
)
def compute(df, period: int = 20):
    return df["high"].rolling(period).max()
