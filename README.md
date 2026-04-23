# trade-md

**A format specification for describing a trading strategy to coding agents and execution engines.**

TRADE.md gives agents a persistent, structured understanding of a strategy's behaviour, risk profile, and lineage. It combines machine-readable tokens (YAML front matter) with human-readable rationale (markdown prose) in a single file — just like DESIGN.md does for visual identity, but with one critical difference: the tokens are *executable semantics*. Compilers emit concrete strategy code directly from the file.

This is **v0.1 alpha**. Ships a freqtrade compiler as the first concrete target.

---

## Why this exists

Four problems this solves at once:

1. **Agents don't know what a strategy is.** They can write `populate_entry_trend` code but they can't tell you whether the strategy is a pullback trader or a breakout trader, or when it should be disabled. TRADE.md makes the thesis and the runtime guardrails first-class.
2. **Provenance is usually lost.** Backtest results live in a notebook somewhere; separation scores live in a spreadsheet; kata lineage lives in commit messages. TRADE.md puts all three in the file itself.
3. **Handoff between human, agent, and runtime is lossy.** Each layer re-interprets. TRADE.md becomes the single source of truth all three consume.
4. **Strategies are not portable across engines.** Today a freqtrade strategy is bound to freqtrade forever. Engine-agnostic semantics means the same TRADE.md can target multiple runtimes.

## Design decisions

**One-per-strategy, not one-per-cell.** A TRADE.md is a behavioural specification; cell assignment in the 560-grid is a portfolio-placement concern. Coupling them breaks portability and conflates two lifecycles. Cell preferences are expressible as soft hints (`portfolio.preferred_cells`), but placement is deployment-time metadata.

**Engine-agnostic semantics, engine-specific compilers.** The format talks about signals, risk, sizing, and gates in universal terms. v0.1 ships a freqtrade compiler only — nothing in the spec leaks freqtrade conventions, so Hummingbot / Jesse / custom-runtime compilers can be added later without spec changes.

## Layout

```
docs/SPEC.md                            Formal v0.1 specification
examples/heritage-rsi-ema/TRADE.md      Worked example (clean, lints OK)
tests/broken.TRADE.md                   Exercises every linter rule
tests/test_trade_md.py                  16-test suite
trade_md/
  parser.py                             Front matter + prose section parsing
  expr.py                               Condition DSL → pandas mask
  linter.py                             Rule-based validator (R001..R010)
  compiler_freqtrade.py                 Emits IStrategy Python
  explain.py                            Strategy summary for agent context
  cli.py                                `trade-md` command entry point
skills/trade-md-workflow/SKILL.md       Enforces the TRADE.md discipline
```

## Quick start

```bash
# validate
python -m trade_md.cli lint examples/heritage-rsi-ema/TRADE.md

# summarize a strategy for agent context (run this first on any task)
python -m trade_md.cli explain examples/heritage-rsi-ema/TRADE.md

# compile to a freqtrade strategy
python -m trade_md.cli compile --target freqtrade \
    examples/heritage-rsi-ema/TRADE.md \
    -o user_data/strategies/HeritageRsiEma.py

# diff two versions for token + performance regressions
python -m trade_md.cli diff v0.3.0.TRADE.md v0.3.1.TRADE.md

# dump the linter rules as JSON (for agent context injection)
python -m trade_md.cli spec --rules-only --format json
```

## The condition DSL in one example

```yaml
indicators:
  trend_filter:
    expr: "close > ema(200)"
  vol_surge:
    expr: "volume > volume.rolling(20).mean() * 1.5"

signals:
  entry_long:
    conditions:
      - "rsi(14) < 30"
      - "{trend_filter}"
      - "close@1h > ema(50)@1h"   # informative 1h timeframe
      - "{vol_surge}"
    tag: "rsi_oversold_uptrend"
```

Compiles to:

```python
dataframe['rsi_14']            = ta.RSI(dataframe, timeperiod=14)
dataframe['ema_200']           = ta.EMA(dataframe, timeperiod=200)
dataframe['volume_roll_20_mean'] = dataframe['volume'].rolling(20).mean()

informative_1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1h')
informative_1h['ema_50'] = ta.EMA(informative_1h, timeperiod=50)
dataframe = merge_informative_pair(dataframe, informative_1h, self.timeframe, '1h', ffill=True)

dataframe.loc[
    ((dataframe['rsi_14'] < 30)
     & (dataframe['close'] > dataframe['ema_200'])
     & (dataframe['close_1h'] > dataframe['ema_50_1h'])
     & (dataframe['volume'] > dataframe['volume_roll_20_mean'] * 1.5)),
    ['enter_long', 'enter_tag']
] = (1, 'rsi_oversold_uptrend')
```

## How this plugs into freqtrade-agents

The loop you already run becomes:

- **Scout** outputs a partial TRADE.md — thesis + provisional tokens, no provenance yet
- **Strategyzer** fills in risk / sizing / gates, runs first backtest, writes back `provenance`
- **Kata-harness** iterates on TRADE.md (not on `.py`); each kata loop = version bump + `trade-md diff` report
- **Monitor** reads `disable_when` as runtime guardrails, not just documentation
- **Portfolio orchestrator** reads `portfolio.preferred_cells` as soft placement hints

Paired with a `SKILL.md` that says *"for any freqtrade strategy task, edit TRADE.md then recompile — never touch the .py directly,"* the `.py` files become build artifacts. Source of truth is the markdown.

## The workflow skill

`skills/trade-md-workflow/SKILL.md` is a Claude skill that operationalizes this discipline. Drop it into your user skills directory (or a Claude Code project's `.claude/skills/` — wherever your agents look) and any agent picking up a freqtrade task will:

1. Run `trade-md explain TRADE.md` first to load strategy context
2. Edit the `.md` (never the `.py`)
3. Lint and fix errors before recompiling
4. Bump `version` and `kata_iteration` on behavioural changes
5. Run `trade-md diff` to catch performance regressions
6. Write backtest results back into `provenance`

The skill's description is intentionally broad — it triggers on "modify the strategy", "tune the stoploss", "port this Pine Script indicator", or any mention of the strategy at all, not only when TRADE.md is named explicitly. That's what turns "use the format" into "the format is unavoidable".

## Spec versioning

The spec is itself versioned. TRADE.md files declare which spec they target:

```yaml
trade_md_spec: "0.1"
```

Compilers refuse unknown major versions.

## What's next

- Hummingbot / Jesse / custom-runtime compilers
- `trade-md simulate` — round-trip backtest + provenance write-back
- Declarative FreqAI feature pipelines
- `trade-md explain` — natural-language strategy summary for agent context
- Signed provenance (reproducibility hashes)
