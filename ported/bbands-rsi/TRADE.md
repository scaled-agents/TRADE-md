---
trade_md_spec: "0.2"
name: bbands-rsi
version: 0.1.0

market:
  regime: [ranging, high-volatility]
  timeframe: 5m
  pair_universe:
    quote: USDT
    exchange: binance
    filter: top50_volume
    exclude: [stablecoins, leveraged]

signals:
  entry_long:
    conditions:
      - "rsi(14) < 30"
      - "close < bb_lower(20, 2)"
      - "volume > 0"
    tag: "rsi_oversold_below_bb"
  exit_long:
    conditions:
      - "rsi(14) > 70"
    tag: "rsi_overbought"

risk:
  stoploss: -0.10
  roi:
    "0": 0.15
    "60": 0.05
    "120": 0.01
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
  derived_from: "BBandsRSI.py (nanoclaw)"
---

## Thesis

Classic mean-reversion: enter when price is both RSI-oversold (< 30) and below the
lower Bollinger Band (20, 2), indicating a statistically extreme downward deviation.
Exit when RSI crosses above 70 (overbought), signaling the reversion is complete.

## When this works

- Ranging or mean-reverting markets where price oscillates around a stable mean
- High-volatility regimes where bands widen, providing clear entry signals
- Liquid pairs where the Bollinger Band calculation reflects genuine price action

## When to disable

- Strong trending markets — price can stay below the lower band for extended periods,
  causing repeated stoploss hits
- During sustained bear moves where "oversold" doesn't mean "about to revert"
- Low-volume periods where Bollinger Bands contract excessively

## Known failure modes

- **Trending breakdowns**: In a downtrend, RSI < 30 and close < bb_lower can persist
  for many candles. Each entry stops out, compounding losses.
- **Exit lag**: RSI > 70 exit can trigger too early in strong bounces or too late in
  weak bounces. No trailing mechanism to capture extended moves.
- **Volume filter is minimal**: `volume > 0` is a sanity check, not a real filter.
  Consider adding a volume surge requirement for higher signal quality.

## Notes

Ported from `BBandsRSI.py` in the nanoclaw strategy collection. Original used
`ROI = {"0": 0.0}` (exit at any profit) and `stoploss = -0.15`. Adjusted to
`ROI = {"0": 0.15}` with tiered levels and `stoploss = -0.10` to pass R003
validation while maintaining mean-reversion intent.
