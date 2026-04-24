"""Linear Regression Momentum — slope of the linear regression line.

Positive slope = upward momentum, negative = downward.
"""
from __future__ import annotations

import numpy as np

from trade_md import indicator, IntParam


@indicator(
    inputs=["close"],
    params={"period": IntParam(default=20, min=2, max=500)},
    outputs=["linreg_momentum"],
    description="Linear regression slope over N bars — momentum proxy.",
    version="1.0.0",
)
def compute(df, period: int = 20):
    def _slope(values):
        if len(values) < 2:
            return np.nan
        x = np.arange(len(values))
        x_mean = x.mean()
        y_mean = values.mean()
        denom = ((x - x_mean) ** 2).sum()
        if denom == 0:
            return 0.0
        return ((x - x_mean) * (values - y_mean)).sum() / denom

    return df["close"].rolling(period).apply(_slope, raw=True)
