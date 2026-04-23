---
trade_md_spec: "0.1"
name: heritage-rsi-ema
version: 0.3.1

market:
  regime: [trending, high-volatility]
  timeframe: 5m
  informative_timeframes: [1h]
  pair_universe:
    quote: USDT
    exchange: binance
    filter: top50_volume
    exclude: [stablecoins, leveraged]

indicators:
  trend_filter:
    expr: "close > ema(200)"
  trend_filter_htf:
    expr: "close@1h > ema(50)@1h"
  vol_surge:
    expr: "volume > volume.rolling(20).mean() * 1.5"

signals:
  entry_long:
    conditions:
      - "rsi(14) < 30"
      - "{trend_filter}"
      - "{trend_filter_htf}"
      - "{vol_surge}"
    tag: "rsi_oversold_uptrend"
  exit_long:
    conditions:
      - "rsi(14) > 70 or close < ema(50)"
    tag: "rsi_overbought_or_ema50_break"

risk:
  stoploss: -0.03
  roi:
    "0": 0.04
    "30": 0.02
    "60": 0.01
    "120": 0
  trailing:
    enabled: true
    positive: 0.01
    offset: 0.015
    only_offset_is_reached: true
  protections:
    - type: StoplossGuard
      lookback: 60
      trade_limit: 2
      stop_duration: 60
    - type: MaxDrawdown
      lookback: 48
      max_allowed_drawdown: 0.10

sizing:
  method: kelly_fraction
  fraction: 0.25
  max_open_trades: 5

portfolio:
  preferred_cells: ["B7", "B8", "C7"]
  correlation_max: 0.7
  regime_agreement_required: true

freqai:
  enabled: false

provenance:
  backtest_period: "2024-01-01..2025-12-31"
  exchange: "binance"
  pairs_sample: 20
  sharpe: 1.8
  sortino: 2.3
  max_dd: 0.12
  win_rate: 0.58
  trades: 412
  profit_factor: 1.6
  separation_index: 0.68
  last_validated: "2026-04-15"
  backtest_engine: "freqtrade-2026.3"

lineage:
  parent: heritage-rsi-ema@0.3.0
  kata_iteration: 14
  graduation_status: simulation
  derived_from: "classic_rsi_mean_reversion"

disable_when:
  - separation_index_below: 0.55
    lookback_trades: 100
  - max_drawdown_exceeds: 0.15
    lookback_days: 30
  - regime_shifts_to: ["crashing", "ranging"]
  - correlation_exceeds: 0.8
    window_days: 7
---

## Thesis

Oversold pullbacks in established uptrends on mid-cap alts. Volume-confirmed RSI
oversold above EMA(200), with HTF trend agreement, is a liquidity-driven
mean-reversion signal — *not* a trend break. The 5m primary captures the reversal
while the 1h informative prevents entries into a cracking daily structure.

## When this works

- Trending or high-volatility regimes with genuine pullback behaviour
- Sufficient intraday volatility for 4% TP within 30 minutes
- Liquid pairs — top-50-volume filter eliminates ghost books

## When to disable

- Separation Index drops below 0.55 over trailing 100 trades → monitor flips off
- 30-day max drawdown exceeds 15% → cooling-off period
- Regime shifts to `crashing` or `ranging` → EMA(200) filter becomes unreliable
- Correlation with active strategies exceeds 0.8 → portfolio concentration risk

## Kata lineage

- **v0.3.0 → v0.3.1**: Added `vol_surge` filter after v0.3.0 produced false signals
  during low-liquidity overnight sessions on mid-caps. Sharpe 1.5 → 1.8, max DD 0.15 → 0.12.
- **v0.2.x → v0.3.0**: Introduced 1h informative timeframe filter to prevent
  counter-trend entries during regime shifts.
- **v0.1.x**: Original RSI(14) + EMA(200) mean-reversion baseline.

## Known failure modes

- **Announcement pumps**: invalidate the mean-reversion thesis — RSI drops while
  price keeps climbing. Protection: StoplossGuard catches repeat losses fast.
- **Extended bear markets**: EMA(200) breaks even on quality coins; HTF filter
  reduces but doesn't eliminate this risk.
- **Stablecoin depegs**: spurious volume spikes satisfy `vol_surge`. Excluded
  explicitly via `pair_universe.exclude`.

## Notes

This strategy is a candidate for cell B7 in the 560-grid (mid-cap trending, 5m
timeframe). Under active kata iteration — do not promote past `simulation` without
two full out-of-sample backtests and paper-trade confirmation.
