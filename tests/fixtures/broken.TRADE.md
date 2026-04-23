---
name: broken-example
version: 0.0.1

market:
  regime: [trending]
  timeframe: 5m
  # Note: informative_timeframes NOT declared, but 4h is used below
  pair_universe:
    quote: USDT
    exchange: binance
    filter: top50_volume

indicators:
  vol_surge:
    expr: "volume > volume.rolling(20).mean() * 1.5"

signals:
  entry_long:
    conditions:
      - "rsi(14) < 30"
      - "{vol_surge}"
      - "close@4h > ema(200)@4h"   # 4h not declared → R004
      - "{nonexistent_token}"        # undeclared token → R005
      - "this isn't valid syntax"    # bad expr → R006
    tag: "test"

risk:
  stoploss: 0.05       # positive → R002
  roi:
    "0": 0.01          # < |stoploss| (0.05) → R003
    "30": 0
  trailing:
    enabled: true
    positive: 0.02
    offset: 0.01       # offset < positive → R008

sizing:
  method: fixed_stake
  stake: 100
  max_open_trades: 3

provenance:
  backtest_period: "2020-01-01..2021-01-01"
  last_validated: "2020-06-01"   # >90d old → R007
  sharpe: 1.0
  max_dd: 0.2
  # no separation_index → R010
---

## Thesis
Intentionally broken example for linter testing.
