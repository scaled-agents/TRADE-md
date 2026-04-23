# CLAUDE.md

## What is this?

trade-md is a toolchain that compiles trading strategies written in markdown (TRADE.md) into executable code for engines like freqtrade. TRADE.md is always the source of truth; compiled .py files are build artifacts.

## Project structure

```
src/trade_md/
  parser.py              # YAML front matter + prose extraction
  expr.py                # Condition DSL → AST → pandas expressions
  linter.py              # Rule-based validator (R001–R016)
  explain.py             # Strategy summarizer
  indicator.py           # @indicator decorator
  params.py              # Typed param descriptors
  cli.py                 # CLI entry point
  compilers/freqtrade.py # Freqtrade IStrategy code generator
tests/                   # pytest, ~125 tests, fixtures in tests/fixtures/
docs/                    # SPEC.md (format spec), DSL.md (expression ref), WORKFLOW.md
examples/                # Reference strategies (v0.1 and v0.2 layouts)
skills/                  # Claude skill for strategy editing workflow
```

## Commands

```bash
make install             # pip install -e ".[dev]"
make test                # pytest with coverage (85% minimum enforced)
make lint                # ruff check
make typecheck           # mypy
make format              # ruff format + ruff --fix

# CLI
trade-md lint TRADE.md
trade-md compile --target freqtrade TRADE.md -o Strategy.py
trade-md explain TRADE.md
trade-md new-indicator <name>
trade-md lint-indicator indicators/<name>.py
```

## Coding discipline

**Run commands directly** — don't tell the user to run them.

**Think first.** Before implementing, state assumptions explicitly. If multiple approaches exist, present them — don't pick silently. If something is unclear, ask.

**Simplicity first.** Minimum code that solves the problem. No features beyond what was asked. No abstractions for single-use code. No error handling for impossible scenarios. If 200 lines could be 50, rewrite.

**Surgical changes.** Touch only what you must. Don't "improve" adjacent code, comments, or formatting. Match existing style. Remove imports/functions YOUR changes made unused — don't clean up pre-existing dead code unless asked. Every changed line should trace directly to the request.

**Verify as you go.** Transform tasks into verifiable goals:
- "Fix the bug" → reproduce it first, then fix, then confirm
- "Add feature X" → implement, then `make lint typecheck test`
- Multi-step tasks: state a brief plan with verification at each step

## Strategy workflow

The canonical loop for strategy changes: **edit TRADE.md → lint → compile → diff**.
Never edit compiled .py files directly — they are overwritten on recompile.

For behavioral changes: bump `version:` PATCH, increment `lineage.kata_iteration`, update `lineage.parent`, add prose to `## Kata lineage`, backtest, write results into `provenance:`.

## Porting strategies / choosing indicator type

When porting Pine Script, LuxAlgo, or other strategies to TRADE.md, pick the simplest indicator type that works:

1. **Built-in** (default choice): RSI, EMA, SMA, ATR, ADX, MACD (line/signal/hist), Bollinger Bands (upper/lower/middle), Stochastic (%K/%D). Use these whenever TA-Lib covers the computation.
2. **User-defined** (`indicators:` block): simple expressions combining built-ins — e.g. `trend_filter: "ema(200)"`, `vol_surge: "volume > sma(20).rolling(20).mean() * 1.5"`. No Python code needed.
3. **Custom** (`custom_indicators:` + `indicators/` directory): only when the logic needs Python (stateful/rolling computations, numpy, loops). Requires `trade_md_spec: "0.2"`, an `@indicator`-decorated function, typed params, and keyword-only args in conditions.

**Never hand-inject indicator code into the compiled .py** — it will be silently overwritten. If the DSL can't express it yet, leave a TODO in TRADE.md prose.

## Standards enforced by tooling

- **ruff** handles linting + formatting (line length 100)
- **mypy** handles type checking (strict on parser/linter/explain; relaxed on expr/compilers/cli)
- **pytest** enforces 85% minimum coverage
- All three must pass before merge — CI runs them on Python 3.11/3.12/3.13

## Conventions

- Commits use conventional format: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`
- Only runtime dependency is PyYAML
- Linter rules use static IDs (R001–R016) for machine-readable output
- Dataclasses are frozen where possible
- New compiler targets are discovered via entry points (plugin architecture)
