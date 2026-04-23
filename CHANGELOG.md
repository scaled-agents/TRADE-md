# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-22

### Added
- TRADE.md format specification v0.1 (`docs/SPEC.md`)
- YAML front matter parser with prose section extraction
- Condition DSL compiler (AST-based, maps to pandas masks)
  - Built-in indicators: RSI, EMA, SMA, ATR, MACD, Bollinger Bands, Stochastic
  - Informative timeframe support (`@1h`, `@4h`)
  - User-defined indicators with `{token}` references
  - Crossover functions: `crosses_above()`, `crosses_below()`
  - Pandas methods: `.rolling()`, `.shift()`, `.pct_change()`
- Linter with 10 rules (R001-R010) covering required fields, risk validation,
  expression parsing, timeframe declarations, and provenance freshness
- Freqtrade compiler emitting complete `IStrategy` classes
- `trade-md explain` for natural-language strategy summaries
- CLI with subcommands: `lint`, `compile`, `explain`, `diff`, `spec`
- Plugin-based compiler discovery via entry points
- 54 tests with 87% code coverage
- CI workflow for Python 3.11/3.12/3.13
- Example strategy: `heritage-rsi-ema` (lints clean, compiles, round-trips)

[0.1.0]: https://github.com/scaled-agents/TRADE-md/releases/tag/v0.1.0
