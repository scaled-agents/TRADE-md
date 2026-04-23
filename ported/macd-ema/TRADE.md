---
trade_md_spec: "0.2"
name: macd-ema
version: 0.1.0

market:
  regime: [trending]
  timeframe: 5m
  pair_universe:
    quote: USDT
    exchange: binance
    filter: top50_volume
    exclude: [stablecoins, leveraged]

signals:
  entry_long:
    conditions:
      - "crosses_above(macd(), macd_signal())"
      - "close > ema(200)"
    tag: "macd_cross_above_ema200"
  exit_long:
    conditions:
      - "crosses_below(macd(), macd_signal())"
      - "close < ema(200)"
    tag: "macd_cross_below_ema200"

risk:
  stoploss: -0.04
  roi:
    "0": 0.05
    "20": 0.04
    "30": 0.03
    "60": 0.01
  trailing:
    enabled: false

sizing:
  method: fixed_stake
  max_open_trades: 3

provenance: {}

lineage:
  parent: none
  kata_iteration: 0
  graduation_status: simulation
  derived_from: "MACD_EMA.py (nanoclaw)"
---

## Thesis

MACD crossover in the direction of a long-term EMA(200) trend filter. Enters long
when the MACD line crosses above the signal line while price is above the 200-period
EMA, confirming a bullish trend context. Exits when the MACD crosses below the signal
and price falls below EMA(200).

## When this works

- Trending markets with sustained directional moves
- Pairs with clean momentum signatures on the 5m timeframe
- Sufficient volume and liquidity to avoid slippage on entry/exit

## When to disable

- Ranging or choppy markets — MACD crossovers produce excessive whipsaws
- Very low volatility regimes where 4-5% ROI targets are unreachable
- During exchange maintenance or extreme spread conditions

## Known failure modes

- **Whipsaw in ranges**: MACD crosses frequently in sideways markets, producing
  many small losses. The EMA(200) filter helps but doesn't eliminate this.
- **Late entries**: MACD is a lagging indicator — entries occur after the move
  has already started, reducing available profit.
- **Gap moves**: Sudden price jumps can bypass the stoploss level.

## Notes

Ported from `MACD_EMA.py` in the nanoclaw strategy collection. Original stoploss
was -0.25 (very loose); tightened to -0.04 for better risk/reward alignment with
the ROI tiers.
