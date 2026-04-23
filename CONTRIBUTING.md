# Contributing to trade-md

## Development setup

```bash
git clone https://github.com/scaled-agents/TRADE-md.git
cd TRADE-md
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Verify everything works:

```bash
make lint        # ruff
make typecheck   # mypy
make test        # pytest + coverage
make example     # run CLI against the example strategy
```

## Project structure

```
src/trade_md/
  parser.py            Front matter + prose section parsing
  expr.py              Condition DSL -> AST -> pandas mask
  linter.py            Rule-based validator (R001..R010)
  explain.py           Strategy summary for agent context
  cli.py               `trade-md` CLI entry point
  compilers/
    freqtrade.py       Emits freqtrade IStrategy Python
docs/
  SPEC.md              Format specification v0.1
  DSL.md               Condition DSL reference with examples
  WORKFLOW.md          Canonical edit/lint/compile workflow
tests/
  conftest.py          Shared fixtures
  test_parser.py       Parser tests
  test_expr.py         Expression compiler tests
  test_linter.py       Linter rule tests (R001-R010)
  test_compiler_freqtrade.py  Compiler round-trip tests
  test_explain.py      Explain output tests
  test_cli.py          CLI integration tests
examples/
  heritage-rsi-ema/TRADE.md   Reference example strategy
```

## Adding a new compiler

Compilers are discovered via entry points. To add a new target (e.g. `jesse`):

1. Create `src/trade_md/compilers/jesse.py` with a function:
   ```python
   def compile_jesse(doc: TradeDoc) -> str:
       """Emit a Jesse strategy from a parsed TRADE.md."""
       ...
   ```

2. Register it in `pyproject.toml`:
   ```toml
   [project.entry-points."trade_md.compilers"]
   freqtrade = "trade_md.compilers.freqtrade:compile_freqtrade"
   jesse = "trade_md.compilers.jesse:compile_jesse"
   ```

3. Add tests in `tests/test_compiler_jesse.py`.

4. The CLI will automatically discover the new target -- no changes to `cli.py` needed.

The compiler receives a `TradeDoc` (see `parser.py`) and returns a string of generated source code. The core format, parser, and linter must never import anything engine-specific.

## Adding a new linter rule

1. Choose the next rule ID (after R010, use R011).
2. Add the check in `src/trade_md/linter.py` inside the `lint()` function.
3. Add the rule description to the `_RULES` list in `src/trade_md/cli.py`.
4. Add the rule to SPEC.md section 13.
5. Write tests in `tests/test_linter.py` covering both pass and fail cases.
6. Update `test_cli_spec_rules_json` expected count if needed.

## Proposing DSL extensions

The condition DSL (section 5 of the spec) is intentionally restricted. To propose a new built-in indicator or operator:

1. Open an issue describing the use case and proposed syntax.
2. Show how it would appear in a TRADE.md condition.
3. Show what the freqtrade compiler should emit.
4. Implementation goes in `src/trade_md/expr.py` (the AST rewriter).

## Code quality

- **Ruff** for linting and formatting (`ruff check`, `ruff format`)
- **Mypy** for type checking (strict on parser/linter/explain, relaxed on expr/compilers/cli)
- **Pytest** with 85% minimum coverage
- All three must pass before merge

## Commit conventions

Use conventional commits:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `test:` test additions or fixes
- `chore:` build, CI, packaging
- `refactor:` code restructuring without behaviour change
