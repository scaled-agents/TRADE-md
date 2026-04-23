---
trade_md_spec: "0.2"
name: heritage-rsi-ema
version: 0.4.0

market:
  regime: [trending, high-volatility]
  timeframe: 5m
  informative_timeframes: [1h]
  pair_universe:
    quote: USDT
    exchange: binance
    filter: top50_volume

custom_indicators:
  - module: indicators.sep_score
    as: sep_score
    version_pin: "1.0"

indicators:
  trend_filter: "ema(200)"
  trend_filter_htf: "ema(50)@1h"
  vol_surge: "volume > sma(20).rolling(20).mean() * 1.5"

signals:
  entry_long:
    conditions:
      - "rsi(14) < 30"
      - "close > {trend_filter}"
      - "ema(50)@1h > ema(200)@1h"
      - "{vol_surge}"
      - "sep_score(lookback=100, smoothing=0.1) > 0.5"
    tag: heritage_rsi_v4_entry

  exit_long:
    conditions:
      - "rsi(14) > 70 or close < ema(50)"
    tag: heritage_rsi_v4_exit

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
      lookback: 24
      trade_limit: 4
      stop_duration: 2
      only_per_pair: false
    - type: MaxDrawdown
      lookback: 48
      max_allowed_drawdown: 0.20
      stop_duration: 12
      only_per_pair: false

sizing:
  method: kelly_fraction
  fraction: 0.25
  max_open_trades: 5

portfolio:
  preferred_cells: [B7, B8, C7]
  max_correlation: 0.7
  regime_agreement: required

freqai:
  enabled: false

provenance:
  backtest_start: "2024-01-01"
  backtest_end: "2025-12-31"
  backtest_engine: freqtrade
  sharpe: 1.9
  sortino: 2.4
  max_dd: 0.12
  win_rate: 0.59
  profit_factor: 1.62
  trades: 312
  separation_index: 0.71
  last_validated: "2026-04-22"

lineage:
  parent: heritage-rsi-ema@0.3.1
  derived_from: heritage-rsi-ema@0.3.0
  kata_iteration: 15
  graduation_status: simulation

disable_when:
  - separation_index_below: 0.55
    lookback_trades: 50
  - max_drawdown_exceeds: 0.15
    lookback_days: 14
  - regime_shifts_to: [ranging, low-volatility]
  - correlation_exceeds: 0.8
    window_days: 30
---

## Thesis

Oversold pullbacks in established uptrends on liquid USDT pairs. The
strategy exploits a liquidity-driven mean-reversion pattern: when RSI
dips below 30 during a macro uptrend (EMA 200 on 5m + EMA 50/200
crossover on 1h), the bounce is statistically significant on top-50
volume pairs. v0.4 adds a custom separation score indicator to filter
entries by regime quality.

## When this works

Best in trending / high-volatility regimes where pullbacks recover
quickly. Typical winning trade reaches the 4% TP within 30 minutes.
The 1h informative filter prevents entries during weak macro trends.
The separation score gate ensures the strategy only trades when its
recent performance is statistically distinguishable from noise.

## When to disable

- Separation index drops below 0.55 over trailing 50 trades
- Max drawdown exceeds 15% over 14 days
- Regime shifts to ranging or low-volatility
- Portfolio-level correlation with active strategies exceeds 0.8

## Kata lineage

- v0.4.0 (kata 15): Added sep_score custom indicator as entry gate;
  bumped to spec 0.2; improved provenance metrics.
- v0.3.1 (kata 14): Added vol_surge indicator for liquidity confirmation.
- v0.3.0 (kata 13): Added 1h informative timeframe for macro trend filter.

## Known failure modes

- Sudden exchange announcements can trigger false RSI dips.
- Extended bear markets invalidate the uptrend assumption.
- Stablecoin de-peg events cause correlated pair moves.

## Notes

Candidate for B7 cell in the portfolio matrix. Under active iteration.
Do not promote past simulation status without a fresh backtest covering
the most recent quarter.
