# TRADE.md Workflow

This document describes the canonical workflow for editing, validating, and iterating on strategies defined in TRADE.md format. It is extracted from the `trade-md-workflow` skill.

---

## Core principle

**TRADE.md is the source of truth. The `.py` file is a build artifact.**

Editing the compiled `.py` directly means your changes will be silently overwritten the next time anyone recompiles. Always edit the `.md`.

## Step 1: Orient before you edit

Before proposing any change, load the strategy's identity:

```bash
trade-md explain path/to/TRADE.md
```

The output gives you thesis, market, entry/exit logic, risk profile, disable conditions, and provenance in about 25 lines. Important details that live in prose (kata lineage notes, known failure modes, thesis reasoning) may require scanning the full TRADE.md.

Why this matters: most bad strategy edits come from not understanding why a parameter is the value it is. A stoploss of `-0.03` on a 5m mean-reversion strategy isn't arbitrary -- it's tuned to sit below the first ROI step of 4% so the take-profit is reachable.

## Step 2: The canonical edit loop

Every change follows the same four steps:

```bash
# 1. Edit TRADE.md (never the .py)

# 2. Lint
trade-md lint path/to/TRADE.md

# 3. Recompile
trade-md compile --target freqtrade path/to/TRADE.md \
    -o user_data/strategies/<ClassName>.py

# 4. If the change is material, diff against the previous version
trade-md diff path/to/TRADE.md.prev path/to/TRADE.md
```

If lint returns errors, fix them before recompiling. Warnings are for things that are usually bugs but occasionally intentional.

## Step 3: Quick edit vs. kata iteration

**Quick edit** (typo, comment, prose fix, equivalent indicator expression): bump the patch version and run the canonical loop. No backtest required.

**Kata iteration** (any behavioural change -- new condition, different indicator period, changed stoploss, new protection):

1. Bump `version:` PATCH (e.g. `0.3.1` -> `0.3.2`)
2. Bump `lineage.kata_iteration` by 1
3. Update `lineage.parent` to the version you're iterating from
4. Make the behavioural change in the front matter
5. Update the `## Kata lineage` prose section with what changed and why
6. Run the canonical edit loop (edit -> lint -> compile -> diff)
7. Run a backtest with the compiled `.py`
8. Write results back into `provenance:` and update `last_validated`
9. Run `trade-md diff` -- exit code 1 means regression
10. If regression, either revert or document why it's acceptable

## Common edit patterns

### Adjusting risk parameters

The linter catches the most common foot-gun (first ROI step <= |stoploss|), but watch for:
- Trailing `offset` must be `>= positive`
- Changing `stoploss` usually means re-tuning the ROI table
- A `MaxDrawdown` protection threshold below the strategy's historical max drawdown will cause immediate permanent disabling

### Adding a new indicator

Define it in `indicators:` with a descriptive name, then reference it as `{name}` in conditions. Named indicators make diffs meaningful.

### Extending entry/exit conditions

Conditions within a signal block are ANDed. For OR, use `or` within a single condition string. For higher timeframe confirmations, declare the timeframe in `market.informative_timeframes`.

### Porting a Pine Script indicator

1. Identify the computation and translate to the DSL
2. If the DSL doesn't have it, express it in terms of available primitives (rolling, shift, pct_change, arithmetic) and declare in `indicators:`
3. If truly exotic, leave a TODO in prose -- don't hand-inject into the compiled `.py`

### Debugging a losing strategy

Run `trade-md explain` first. If disable conditions would have tripped, the question is why the monitor isn't disabling it (runtime bug, not strategy bug). Otherwise, create a new kata iteration.

## Rules

- Never edit the compiled `.py` directly
- Never bump MAJOR or MINOR without a kata lineage note
- Never skip the lint step
- Never touch a strategy whose `graduation_status` is `live` without a ticket

## Commands reference

```bash
trade-md explain TRADE.md                          # summarize for context
trade-md explain TRADE.md --format json            # structured output
trade-md lint TRADE.md                             # validate
trade-md lint my-strategy/                         # validate a strategy directory
trade-md lint TRADE.md --format json               # machine-readable
trade-md compile --target freqtrade TRADE.md -o X  # emit strategy
trade-md compile --allow-version-drift ...         # suppress version pin errors
trade-md diff old.TRADE.md new.TRADE.md            # regression check
trade-md spec --rules-only --format json           # linter rules
trade-md new-indicator sep_score                   # scaffold new indicator
trade-md lint-indicator indicators/my_ind.py       # lint indicator standalone
```
