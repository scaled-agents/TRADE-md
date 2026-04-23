---
trade_md_spec: "0.2"
name: adx-smas
version: 0.1.0

market:
  regime: [trending]
  timeframe: 1h
  pair_universe:
    quote: USDT
    exchange: binance
    filter: top50_volume
    exclude: [stablecoins, leveraged]

signals:
  entry_long:
    conditions:
      - "adx(14) > 25"
      - "crosses_above(sma(3), sma(6))"
    tag: "adx_strong_sma_cross"
  exit_long:
    conditions:
      - "adx(14) < 25"
      - "crosses_above(sma(6), sma(3))"
    tag: "adx_weak_sma_reverse"

risk:
  stoploss: -0.08
  roi:
    "0": 0.10
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
  derived_from: "AdxSmas.py (nanoclaw / Gert Wohlgemuth)"
---

## Thesis

Trend-strength-filtered SMA crossover. Uses ADX(14) as a trend strength gate — only
enters when ADX > 25, confirming a directional market. The fast SMA(3)/SMA(6) crossover
captures momentum shifts within confirmed trends. Exits when trend strength fades
(ADX < 25) and the slow SMA crosses back above the fast SMA.

## When this works

- Markets with clear trending phases (ADX regularly above 25)
- 1h timeframe provides balance between signal quality and trade frequency
- Works best on pairs with sustained multi-hour moves

## When to disable

- Extended ranging markets where ADX stays below 25 for days — no signals generated
- During sudden regime shifts (flash crashes) where ADX spikes but direction is unclear
- Very low-volume overnight sessions on minor pairs

## Known failure modes

- **False ADX spikes**: ADX can briefly exceed 25 during a strong reversal candle,
  triggering entries against the new direction.
- **SMA lag**: SMA(3)/SMA(6) are very short-period — in noisy markets they cross
  frequently even with the ADX gate.
- **Exit requires two conditions**: Both ADX < 25 AND reverse SMA cross must happen,
  which can delay exits if only one condition is met.

## Notes

Ported from `AdxSmas.py` in the nanoclaw strategy collection (originally by Gert
Wohlgemuth, converted from C#). Required adding `adx(N)` as a new built-in indicator
to the DSL. Original stoploss was -0.25; tightened to -0.08.
