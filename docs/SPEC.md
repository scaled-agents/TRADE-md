# TRADE.md Specification v0.1

**Status:** alpha · **Last updated:** 2026-04-22

A format specification for describing a trading strategy to coding agents and execution engines. TRADE.md gives agents a persistent, structured understanding of a strategy's behaviour, risk profile, and lineage.

---

## 1. Philosophy

A TRADE.md file combines **machine-readable strategy tokens** (YAML front matter) with **human-readable trading rationale** (markdown prose).

- Tokens give agents and compilers exact values — indicator parameters, risk limits, sizing rules.
- Prose tells them *why* those values exist, *when* the strategy is expected to work, and *when* it should be disabled.

This mirrors the DESIGN.md pattern, with one critical difference: a strategy's tokens are **executable semantics**. `rsi(14) < 30 and close > ema(200)` is not a value — it's a tiny program. TRADE.md therefore sits between a spec and a compilation target. An engine-specific compiler (v0.1: freqtrade) emits concrete strategy code from the file.

## 2. Design principles

1. **One strategy, one file.** A TRADE.md describes a strategy's identity and behaviour, not its deployment. Portfolio placement, cell assignment, and live/paper status are *preferences* expressible in the file but *not* identity.
2. **Engine-agnostic semantics, engine-specific compilers.** The format uses universal concepts (signals, risk, sizing, gates). Each engine (freqtrade, hummingbot, custom) implements its own compiler.
3. **Provenance is first-class.** Backtest results, Separation Index, kata lineage, and graduation status live in the file itself. A strategy without provenance is incomplete.
4. **Disable conditions are runtime, not documentation.** The "When to disable" prose section has a structured mirror (`disable_when`) that monitors read at runtime.
5. **Tokens are referenceable.** Define an indicator once, reference it by name in conditions.

## 3. File structure

```
---
<YAML front matter: machine-readable tokens>
---

## <Prose sections: rationale, lineage, failure modes>
```

The YAML block is required. Prose sections are recommended but not required for a file to lint.

## 4. Required top-level fields

### `name` (string)
Unique identifier within a repository. Kebab-case. Used for compiled class name generation.

### `version` (semver string)
`MAJOR.MINOR.PATCH`. Bump `PATCH` for safe iteration within a kata loop, `MINOR` for behavioural changes, `MAJOR` for thesis changes.

### `market` (object)
Describes the market context this strategy is designed for.

| Field | Type | Required | Notes |
|---|---|---|---|
| `regime` | `string[]` | yes | Values: `trending`, `ranging`, `high-volatility`, `low-volatility`, `crashing`, `recovering` |
| `timeframe` | `string` | yes | Primary candle interval: `1m`, `5m`, `15m`, `1h`, `4h`, `1d` |
| `informative_timeframes` | `string[]` | no | Higher timeframes consumed by conditions |
| `pair_universe` | `object` | yes | See §4.1 |

#### 4.1 `pair_universe` sub-fields

| Field | Type | Notes |
|---|---|---|
| `quote` | `string` | `USDT`, `USDC`, `BTC`, etc. |
| `exchange` | `string` | `binance`, `kraken`, `bybit`, … |
| `filter` | `string` | Named filter: `top50_volume`, `top100_marketcap`, `manual` |
| `include` | `string[]` | Explicit pairs when `filter: manual` |
| `exclude` | `string[]` | Always excluded pairs (stablecoins, leveraged tokens) |

### `signals` (object)

Each signal block names the directionality and lists conditions that must *all* be true for the signal to fire.

| Key | Meaning |
|---|---|
| `entry_long` | Conditions to open a long position |
| `exit_long` | Conditions to close a long position |
| `entry_short` | Conditions to open a short position (if exchange/mode supports) |
| `exit_short` | Conditions to close a short position |

Each signal block contains:

| Field | Type | Required |
|---|---|---|
| `conditions` | `string[]` | yes — expressions (see §5) |
| `confidence_gate` | `float` | no — minimum FreqAI probability when `freqai.enabled: true` |
| `tag` | `string` | no — emitted as freqtrade `enter_tag` / `exit_tag` |

### `risk` (object)

| Field | Type | Notes |
|---|---|---|
| `stoploss` | `float` | Negative decimal (`-0.05` = 5% stop) |
| `roi` | `object` | Minutes-held → minimum ROI, as keys-as-strings |
| `trailing` | `object` | `{ enabled, positive, offset, only_offset_is_reached }` |
| `protections` | `object[]` | Ordered list of protection rules |

### `sizing` (object)

| Field | Type | Notes |
|---|---|---|
| `method` | `string` | `fixed_stake`, `kelly_fraction`, `volatility_targeted`, `separation_weighted` |
| Method-specific keys | varies | e.g. `fraction` for Kelly, `target_vol` for vol-targeted |
| `max_open_trades` | `int` | Cap on concurrent positions for this strategy |

## 5. Indicator & condition DSL

Conditions are expressions written in a restricted Python-like syntax. The v0.1 reference compiler parses them with Python's `ast` module and rewrites function calls into engine-specific implementations.

### 5.1 OHLCV references
`open`, `high`, `low`, `close`, `volume`, `hl2`, `hlc3`, `ohlc4` — refer to the current candle on the primary timeframe.

### 5.2 Built-in indicators (v0.1)

| Call | Maps to |
|---|---|
| `rsi(N)` | Relative Strength Index, period N |
| `ema(N)` | Exponential MA, period N |
| `sma(N)` | Simple MA, period N |
| `atr(N)` | Average True Range, period N |
| `macd()` | MACD line (default 12, 26, 9) |
| `macd_signal()` | MACD signal line |
| `macd_hist()` | MACD histogram |
| `bb_upper(N, std)` | Bollinger upper band |
| `bb_lower(N, std)` | Bollinger lower band |
| `bb_middle(N)` | Bollinger middle band |
| `stoch_k(N)` | Stochastic %K |
| `stoch_d(N)` | Stochastic %D |

Additional indicators are declared in the `indicators:` block (§5.5).

### 5.3 Informative timeframes

Suffix any expression with `@<timeframe>` to read from an informative timeframe:
```
rsi(14)@1h < 30
close@4h > ema(50)@4h
```
The `market.informative_timeframes` array must include every timeframe referenced.

### 5.4 Pandas-style operators
`.rolling(N).mean()`, `.rolling(N).std()`, `.rolling(N).max()`, `.rolling(N).min()`, `.shift(N)`, `.pct_change(N)`.

### 5.5 User-defined indicators

```yaml
indicators:
  trend_filter:
    expr: "ema(200) - ema(50)"
  vol_surge:
    expr: "volume > volume.rolling(20).mean() * 1.5"
```

Reference them as `{trend_filter}` or `{vol_surge}` inside conditions.

### 5.6 Operators

- Comparison: `<`, `>`, `<=`, `>=`, `==`, `!=`
- Logical: `and`, `or`, `not`
- Arithmetic: `+`, `-`, `*`, `/`
- Crossovers (sugar): `crosses_above(a, b)`, `crosses_below(a, b)`

## 6. Portfolio integration

```yaml
portfolio:
  preferred_cells: ["B7", "B8", "C7"]     # 560-grid coordinates — soft preference
  correlation_max: 0.7                     # vs already-running strategies
  regime_agreement_required: true          # Monitor must confirm regime before enabling
```

These are **soft** placements — the portfolio orchestrator may override based on current slot availability and separation analysis.

## 7. FreqAI block (optional)

```yaml
freqai:
  enabled: true
  model: "LightGBMRegressor"
  label_period_candles: 24
  include_timeframes: ["5m", "1h"]
  feature_set: "default"
```

When `enabled: false` or absent, the compiler emits a non-FreqAI strategy.

## 8. Provenance block

```yaml
provenance:
  backtest_period: "2024-01-01..2025-12-31"
  exchange: "binance"
  pairs_sample: 20
  sharpe: 1.8
  sortino: 2.3
  calmar: 1.5
  max_dd: 0.12
  win_rate: 0.58
  trades: 412
  profit_factor: 1.6
  separation_index: 0.68      # proprietary
  last_validated: "2026-04-20"
  backtest_engine: "freqtrade-2026.3"
```

`separation_index` is optional but recommended. `last_validated` is compared against a staleness threshold by the linter.

## 9. Lineage block

```yaml
lineage:
  parent: heritage-rsi-ema@0.3.0            # parent strategy@version
  kata_iteration: 14                         # counter within kata loop
  graduation_status: simulation              # simulation | paper | live | retired
  derived_from: "luxalgo-smc-rsi-pine"       # optional external origin
```

## 10. Prose sections (recommended)

Ordered conventions — linter checks presence, not content:

- `## Thesis` — why this edge should exist
- `## When this works` — market conditions, regime, cohort
- `## When to disable` — explicit failure conditions (mirror `disable_when`)
- `## Kata lineage` — what changed from parent version and why
- `## Known failure modes` — documented failure cases
- `## Notes` — freeform

## 11. Structured disable conditions

Prose "When to disable" has a structured mirror the monitor reads at runtime:

```yaml
disable_when:
  - separation_index_below: 0.55
    lookback_trades: 100
  - max_drawdown_exceeds: 0.15
    lookback_days: 30
  - regime_shifts_to: ["crashing", "ranging"]
  - correlation_exceeds: 0.8
    window_days: 7
```

## 12. CLI reference implementation

```
trade-md lint TRADE.md                        # validate against spec + rule checks
trade-md compile --target freqtrade TRADE.md  # emit IStrategy Python file
trade-md simulate TRADE.md                    # run backtest, write back provenance
trade-md diff v0.3.0.TRADE.md v0.3.1.TRADE.md # token + performance regression
trade-md spec [--rules] [--format json]       # print spec (for agent context injection)
```

## 13. Linter rules (v0.1)

| ID | Severity | Rule |
|---|---|---|
| R001 | error | `name`, `version`, `market`, `signals`, `risk`, `sizing` present |
| R002 | error | `stoploss` is negative |
| R003 | error | First ROI step value > `|stoploss|` |
| R004 | error | Every informative TF used in conditions is declared |
| R005 | error | All `{token}` references resolve to declared indicators |
| R006 | error | Conditions parse as valid expressions |
| R007 | warning | `provenance.last_validated` within 90 days |
| R008 | warning | Trailing stop `offset > positive` |
| R009 | warning | Prose sections `Thesis`, `When to disable` present |
| R010 | info | `separation_index` present in provenance |

Linter output is structured JSON:
```json
{
  "findings": [...],
  "summary": { "errors": 0, "warnings": 1, "info": 1 },
  "strategy": { "name": "...", "version": "..." }
}
```

## 14. Versioning of this spec

The spec itself is versioned. TRADE.md files may declare the spec version they target:

```yaml
trade_md_spec: "0.1"
```

Absent means latest. Compilers refuse unknown major versions.

## 15. Non-goals (v0.1)

- **Not** a backtesting engine. TRADE.md is compiled *to* existing engines.
- **Not** an order-router. Execution gating lives in the runtime that consumes the compiled strategy.
- **Not** a replacement for engine-specific configuration (exchange keys, database URLs, etc.).

## 16. Future work

- Multi-engine compilers (hummingbot, jesse, custom runtime)
- Declarative ML feature pipelines beyond FreqAI
- Cross-strategy optimization hints (`optimizer:` block)
- Signed provenance (backtest reproducibility hashes)
- `trade-md explain` — natural-language strategy summary for agent context
