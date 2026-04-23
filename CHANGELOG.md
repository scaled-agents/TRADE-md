# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-22

### Added
- **Custom indicators**: `@indicator` decorator and typed param descriptors
  (`IntParam`, `FloatParam`, `StrParam`, `BoolParam`)
- **Strategy-as-directory**: parser accepts directory paths with `TRADE.md`
  at root and `indicators/` subdirectory
- **`custom_indicators:` front matter block**: register custom indicator modules
  with module path, alias, and optional version pin
- **Linter rules R011-R016**: custom indicator module resolution, input validation,
  output collision detection, signature matching, forbidden imports, directory contents
- **`trade-md new-indicator <name>`**: scaffold a new indicator module with decorator template
- **`trade-md lint-indicator <path>`**: standalone indicator module linting
- **`--allow-version-drift`**: compile flag to suppress version pin mismatch errors
- **Directory output from compiler**: strategies with custom indicators emit a
  Python package (strategy.py + indicators/) instead of a single file
- **Custom indicators in explain**: `trade-md explain` now shows custom indicator details
- Version pin enforcement at compile time (prefix-based semver matching)
- `write_compiled_output()` helper for handling single-file and directory output
- Worked example: `heritage-rsi-ema-v02` demonstrating custom indicators
- 125 tests (up from 54)

### Fixed
- Token substitution (`{token}`) now handles indicators defined as strings
  (e.g., `trend_filter: "ema(200)"`) in addition to dicts

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

[0.2.0]: https://github.com/scaled-agents/TRADE-md/releases/tag/v0.2.0
[0.1.0]: https://github.com/scaled-agents/TRADE-md/releases/tag/v0.1.0
