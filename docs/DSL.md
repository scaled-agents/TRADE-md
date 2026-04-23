# Condition DSL Reference

The TRADE.md condition DSL is a restricted Python-like syntax for expressing trading signals. The reference compiler parses expressions with Python's `ast` module and rewrites them into engine-specific implementations.

This document extracts and expands on SPEC.md section 5.

---

## OHLCV references

These bare names refer to the current candle on the primary timeframe:

```
open, high, low, close, volume, hl2, hlc3, ohlc4
```

## Built-in indicators

| Call | Description |
|---|---|
| `rsi(N)` | Relative Strength Index, period N |
| `ema(N)` | Exponential Moving Average, period N |
| `sma(N)` | Simple Moving Average, period N |
| `atr(N)` | Average True Range, period N |
| `macd()` | MACD line (default 12, 26, 9) |
| `macd_signal()` | MACD signal line |
| `macd_hist()` | MACD histogram |
| `bb_upper(N, std)` | Bollinger upper band |
| `bb_lower(N, std)` | Bollinger lower band |
| `bb_middle(N)` | Bollinger middle band |
| `stoch_k(N)` | Stochastic %K |
| `stoch_d(N)` | Stochastic %D |

## Operators

- **Comparison:** `<`, `>`, `<=`, `>=`, `==`, `!=`
- **Logical:** `and`, `or`, `not`
- **Arithmetic:** `+`, `-`, `*`, `/`
- **Crossovers:** `crosses_above(a, b)`, `crosses_below(a, b)`

## Pandas-style methods

`.rolling(N).mean()`, `.rolling(N).std()`, `.rolling(N).max()`, `.rolling(N).min()`, `.shift(N)`, `.pct_change(N)`

## Informative timeframes

Suffix any expression with `@<timeframe>` to read from a higher timeframe:

```
rsi(14)@1h < 30
close@4h > ema(50)@4h
```

Every timeframe referenced must be declared in `market.informative_timeframes`.

## User-defined indicators

Define reusable indicators in the `indicators:` block:

```yaml
indicators:
  trend_filter:
    expr: "close > ema(200)"
  vol_surge:
    expr: "volume > volume.rolling(20).mean() * 1.5"
```

Reference them by name in conditions: `"{trend_filter}"`, `"{vol_surge}"`.

---

## Worked examples

### Example 1: Simple RSI oversold

```yaml
signals:
  entry_long:
    conditions:
      - "rsi(14) < 30"
```

Compiles to:
```python
dataframe['rsi_14'] = ta.RSI(dataframe, timeperiod=14)
dataframe.loc[(dataframe['rsi_14'] < 30), 'enter_long'] = 1
```

### Example 2: RSI with EMA trend filter

```yaml
signals:
  entry_long:
    conditions:
      - "rsi(14) < 30"
      - "close > ema(200)"
```

Multiple conditions within a signal are ANDed:
```python
dataframe.loc[
    ((dataframe['rsi_14'] < 30)
     & (dataframe['close'] > dataframe['ema_200'])),
    'enter_long'
] = 1
```

### Example 3: OR within a single condition

```yaml
signals:
  exit_long:
    conditions:
      - "rsi(14) > 70 or close < ema(50)"
```

`and`/`or` within a single condition string are converted to pandas `&`/`|`:
```python
dataframe.loc[
    ((dataframe['rsi_14'] > 70) | (dataframe['close'] < dataframe['ema_50'])),
    'exit_long'
] = 1
```

### Example 4: Higher timeframe confirmation

```yaml
market:
  informative_timeframes: [1h]

signals:
  entry_long:
    conditions:
      - "rsi(14) < 30"
      - "close@1h > ema(50)@1h"
```

The compiler fetches the 1h dataframe, computes indicators on it, and merges it back:
```python
informative_1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1h')
informative_1h['ema_50'] = ta.EMA(informative_1h, timeperiod=50)
dataframe = merge_informative_pair(dataframe, informative_1h, self.timeframe, '1h', ffill=True)

dataframe.loc[
    ((dataframe['rsi_14'] < 30)
     & (dataframe['close_1h'] > dataframe['ema_50_1h'])),
    'enter_long'
] = 1
```

### Example 5: Named indicators with rolling statistics

```yaml
indicators:
  vol_surge:
    expr: "volume > volume.rolling(20).mean() * 1.5"
  momentum:
    expr: "close.pct_change(5) > 0.02"

signals:
  entry_long:
    conditions:
      - "rsi(14) < 30"
      - "{vol_surge}"
      - "{momentum}"
```

Named indicators keep conditions readable. The compiler inlines the expressions:
```python
dataframe['rsi_14'] = ta.RSI(dataframe, timeperiod=14)
dataframe['volume_roll_20_mean'] = dataframe['volume'].rolling(20).mean()

dataframe.loc[
    ((dataframe['rsi_14'] < 30)
     & (dataframe['volume'] > dataframe['volume_roll_20_mean'] * 1.5)
     & (dataframe['close'].pct_change(5) > 0.02)),
    'enter_long'
] = 1
```

### Example 6: Bollinger Band squeeze with crossover

```yaml
indicators:
  bb_squeeze:
    expr: "(bb_upper(20, 2) - bb_lower(20, 2)) < atr(14) * 1.5"

signals:
  entry_long:
    conditions:
      - "{bb_squeeze}"
      - "crosses_above(close, bb_upper(20, 2))"
```

Crossover functions compile to shift-based comparisons:
```python
dataframe.loc[
    ((bb_squeeze_mask)
     & ((dataframe['close'] > dataframe['bb_upper_20_2'])
        & (dataframe['close'].shift(1) <= dataframe['bb_upper_20_2'].shift(1)))),
    'enter_long'
] = 1
```

### Example 7: Stochastic divergence exit

```yaml
signals:
  exit_long:
    conditions:
      - "stoch_k(14) > 80 and stoch_d(14) > 80"
      - "crosses_below(stoch_k(14), stoch_d(14))"
    tag: "stoch_overbought_cross"
```

Tags are emitted as `exit_tag` values in freqtrade for trade analysis.
