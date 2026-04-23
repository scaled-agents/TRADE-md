---
trade_md_spec: "0.2"
name: test-strategy
version: 0.1.0
market:
  regime: [trending]
  timeframe: 5m
  pair_universe:
    quote: USDT
    exchange: binance
    filter: top50_volume
custom_indicators:
  - module: indicators.test_ind
    as: test_score
    version_pin: "1.0"
signals:
  entry_long:
    conditions:
      - "rsi(14) < 30"
      - "test_score(lookback=100) > 0.6"
risk:
  stoploss: -0.05
  roi:
    "0": 0.10
sizing:
  method: fixed_stake
  max_open_trades: 3
---

## Thesis

Test strategy for unit tests.

## When to disable

Never.
