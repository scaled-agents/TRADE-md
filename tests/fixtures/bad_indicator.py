"""Indicator with forbidden imports for R015 testing."""
from __future__ import annotations

import socket  # noqa: F401 — forbidden

from trade_md import indicator, IntParam


@indicator(
    inputs=["close"],
    params={"period": IntParam(default=14)},
    outputs=["bad_ind"],
)
def compute(df, period: int = 14):
    return df["close"] * 0
