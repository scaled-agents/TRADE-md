"""Freqtrade compiler — emits an IStrategy Python file from a TradeDoc.

Supports:
- Primary + informative timeframes (via `merge_informative_pair`)
- Builtin indicators mapped to `talib.abstract`
- Pandas rolling / shift / pct_change
- Entry/exit long conditions (short support is stubbed)
- Risk config (stoploss, minimal_roi, trailing)
- Protections (StoplossGuard, MaxDrawdown, …)

Non-goals for v0.1:
- Custom order types, leverage config
- Separation-weighted sizing (needs runtime hook)
- FreqAI emission (stubbed — flag handled but no feature expansion)
"""
from __future__ import annotations

import re
from typing import Any

from ..expr import (
    BUILTIN_INDICATORS,
    IndicatorUse,
    compile_conditions,
)
from ..parser import TradeDoc

# ---- Protection field name mapping ---------------------------------------

# Map TRADE.md short field names → freqtrade protection keys.
_PROTECTION_FIELD_MAP = {
    "lookback": "lookback_period_candles",
    "stop_duration": "stop_duration_candles",
    "trade_limit": "trade_limit",
    "max_allowed_drawdown": "max_allowed_drawdown",
    "required_profit": "required_profit",
    "only_per_pair": "only_per_pair",
    "only_per_side": "only_per_side",
    "type": None,  # handled separately → "method"
}


def _pascal_case(name: str) -> str:
    """'heritage-rsi-ema' → 'HeritageRsiEma'."""
    return "".join(p.capitalize() for p in re.split(r"[-_\s]+", name) if p)


def _class_name(doc: TradeDoc) -> str:
    return _pascal_case(doc.name) or "CompiledStrategy"


# ---- Indicator line emission ---------------------------------------------


def _emit_ohlcv_informative_line(use: IndicatorUse) -> str:
    """OHLCV used on informative timeframe. Nothing to compute on the primary
    df — the merge will produce `close_1h` from informative's `close`.
    This function is called for the *informative df computation*, where the
    OHLCV columns already exist natively; so it emits nothing.
    """
    return ""


def _emit_builtin_line(use: IndicatorUse, df_var: str) -> str:
    """Emit a TA-Lib call for a builtin indicator.

    The output column name on `df_var` is the indicator's base col *without*
    the timeframe suffix. The caller strips the suffix when emitting on an
    informative df.
    """
    spec = BUILTIN_INDICATORS[use.name]
    talib_name = spec["talib"]
    args = list(use.args)
    # Most TA-Lib functions take `timeperiod=<N>` as first param.
    # Known exceptions: MACD, BBANDS, STOCH need multiple args or output keys.
    if use.name in ("rsi", "ema", "sma", "atr"):
        period = args[0]
        call = f"ta.{talib_name}({df_var}, timeperiod={period})"
    elif use.name in ("macd", "macd_signal", "macd_hist"):
        # Default MACD params
        out_key = spec["output_key"]
        call = f"ta.{talib_name}({df_var})[{out_key!r}]"
    elif use.name in ("bb_upper", "bb_lower", "bb_middle"):
        period = args[0] if args else 20
        std = args[1] if len(args) > 1 else 2
        out_key = spec["output_key"]
        call = (
            f"ta.BBANDS({df_var}, timeperiod={period}, "
            f"nbdevup={std}, nbdevdn={std})[{out_key!r}]"
        )
    elif use.name in ("stoch_k", "stoch_d"):
        out_key = spec["output_key"]
        call = f"ta.STOCH({df_var})[{out_key!r}]"
    else:
        raise ValueError(f"No emitter for builtin {use.name!r}")

    # Output column: strip tf suffix if present (for informative df context).
    return call


def _emit_rolling_line(use: IndicatorUse, df_var: str, base_col: str) -> str:
    window = use.args[0]
    agg = use.name
    return f"{df_var}[{base_col!r}].rolling({window}).{agg}()"


def _emit_shift_line(use: IndicatorUse, df_var: str, base_col: str) -> str:
    n = use.args[0]
    return f"{df_var}[{base_col!r}].shift({n})"


def _emit_pct_change_line(use: IndicatorUse, df_var: str, base_col: str) -> str:
    n = use.args[0]
    return f"{df_var}[{base_col!r}].pct_change({n})"


def _strip_tf(col: str, tf: str | None) -> str:
    """Given 'rsi_14_1h' and tf='1h', return 'rsi_14'. If tf is None, return col."""
    if not tf:
        return col
    suffix = f"_{tf}"
    return col[: -len(suffix)] if col.endswith(suffix) else col


def _topo_sort_uses(uses: list[IndicatorUse]) -> list[IndicatorUse]:
    """Order uses so that base cols are computed before dependents."""
    by_col = {u.col: u for u in uses}
    ordered: list[IndicatorUse] = []
    visited: set[str] = set()

    def visit(u: IndicatorUse) -> None:
        if u.col in visited:
            return
        visited.add(u.col)
        if u.kind in ("rolling", "shift", "pct_change") and u.base_col:
            base_in_same_tf = f"{u.base_col}" + (f"_{u.timeframe}" if u.timeframe else "")
            if base_in_same_tf in by_col:
                visit(by_col[base_in_same_tf])
        ordered.append(u)

    for u in uses:
        visit(u)
    return ordered


def _emit_indicator_lines(
    uses: list[IndicatorUse],
    df_var: str,
    timeframe: str | None,
    indent: str = "        ",
) -> list[str]:
    """Emit computation lines for all uses belonging to a given timeframe.

    Column names are stripped of the tf suffix when writing to `df_var` on an
    informative df, because merge_informative_pair will re-add the suffix.
    """
    lines: list[str] = []
    tf_uses = [u for u in uses if u.timeframe == timeframe]
    tf_uses = _topo_sort_uses(tf_uses)

    for u in tf_uses:
        # Column name on the df we're writing to: strip the timeframe suffix
        # if we're writing to an informative df.
        out_col = _strip_tf(u.col, timeframe) if timeframe else u.col

        if u.kind == "ohlcv":
            # Informative OHLCV — nothing to compute, it's native on the df.
            continue
        elif u.kind == "builtin":
            rhs = _emit_builtin_line(u, df_var)
        elif u.kind == "rolling":
            base = _strip_tf(u.base_col, timeframe) if timeframe else u.base_col
            rhs = _emit_rolling_line(u, df_var, base)
        elif u.kind == "shift":
            base = _strip_tf(u.base_col, timeframe) if timeframe else u.base_col
            rhs = _emit_shift_line(u, df_var, base)
        elif u.kind == "pct_change":
            base = _strip_tf(u.base_col, timeframe) if timeframe else u.base_col
            rhs = _emit_pct_change_line(u, df_var, base)
        else:
            raise ValueError(f"Unknown use kind: {u.kind}")

        lines.append(f"{indent}{df_var}[{out_col!r}] = {rhs}")
    return lines


def _compute_startup(uses: list[IndicatorUse]) -> int:
    """Max period across all uses, with a safety buffer."""
    max_p = 0
    for u in uses:
        if u.args:
            for a in u.args:
                if isinstance(a, (int, float)):
                    max_p = max(max_p, int(a))
    return max_p + 50  # buffer


def _emit_protections(protections: list[dict[str, Any]]) -> str:
    """Emit a list-of-dicts literal for freqtrade protections."""
    if not protections:
        return "[]"
    out = ["["]
    for p in protections:
        out.append("            {")
        out.append(f"                \"method\": {p['type']!r},")
        for k, v in p.items():
            if k == "type":
                continue
            fq_key = _PROTECTION_FIELD_MAP.get(k, k)
            if fq_key is None:
                continue
            out.append(f"                {fq_key!r}: {v!r},")
        out.append("            },")
    out.append("        ]")
    return "\n".join(out)


def _emit_roi(roi: dict[str, Any]) -> str:
    pairs = sorted(roi.items(), key=lambda kv: int(kv[0]))
    body = ", ".join(f'"{k}": {v}' for k, v in pairs)
    return "{" + body + "}"


# ---- Main entry point ----------------------------------------------------


def compile_freqtrade(doc: TradeDoc) -> str:
    """Compile a TradeDoc into freqtrade IStrategy Python source."""
    # 1. Compile conditions
    signals = doc.signals
    indicators = doc.indicators

    entry_long = signals.get("entry_long") or {}
    exit_long = signals.get("exit_long") or {}

    entry_compiled = compile_conditions(
        entry_long.get("conditions") or [],
        indicators,
    ) if entry_long.get("conditions") else None
    exit_compiled = compile_conditions(
        exit_long.get("conditions") or [],
        indicators,
    ) if exit_long.get("conditions") else None

    # 2. Aggregate all uses
    all_uses: list[IndicatorUse] = []
    seen = set()
    for c in (entry_compiled, exit_compiled):
        if c is None:
            continue
        for u in c.uses:
            if u.col not in seen:
                seen.add(u.col)
                all_uses.append(u)

    # 3. Split uses by timeframe
    primary_uses = [u for u in all_uses if u.timeframe is None]
    informative_tfs: dict[str, list[IndicatorUse]] = {}
    for u in all_uses:
        if u.timeframe:
            informative_tfs.setdefault(u.timeframe, []).append(u)

    # 4. Gather config
    class_name = _class_name(doc)
    timeframe = doc.market.get("timeframe", "5m")
    risk = doc.risk
    stoploss = risk.get("stoploss", -0.10)
    roi = risk.get("roi") or {"0": 0.05}
    trailing = risk.get("trailing") or {}
    sizing = doc.sizing
    max_open_trades = sizing.get("max_open_trades", 3)
    startup = _compute_startup(all_uses)

    # 5. Emit
    lines: list[str] = []
    lines.append('"""')
    lines.append(f"Auto-generated by trade-md v0.1 from {doc.name}@{doc.version}.")
    lines.append("")
    lines.append("DO NOT EDIT BY HAND — modify TRADE.md and recompile.")
    lines.append(f"Source strategy: {doc.name}")
    lines.append(f"Version:         {doc.version}")
    thesis_raw = doc.prose_sections.get("Thesis", "")
    thesis_line = thesis_raw.splitlines()[0] if thesis_raw else "n/a"
    lines.append(f"Thesis:          {thesis_line}")
    lines.append('"""')
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from pandas import DataFrame")
    lines.append("import talib.abstract as ta")
    lines.append("from freqtrade.strategy import IStrategy, merge_informative_pair")
    lines.append("")
    lines.append("")
    lines.append(f"class {class_name}(IStrategy):")
    parent = (doc.front_matter.get("lineage") or {}).get("parent", "none")
    lines.append(f'    """Compiled from TRADE.md. Parent: {parent}"""')
    lines.append("")
    lines.append("    INTERFACE_VERSION = 3")
    lines.append(f"    timeframe = {timeframe!r}")
    lines.append(f"    stoploss = {stoploss}")
    lines.append(f"    minimal_roi = {_emit_roi(roi)}")

    if trailing.get("enabled"):
        lines.append("    trailing_stop = True")
        if "positive" in trailing:
            lines.append(f"    trailing_stop_positive = {trailing['positive']}")
        if "offset" in trailing:
            lines.append(f"    trailing_stop_positive_offset = {trailing['offset']}")
        if trailing.get("only_offset_is_reached"):
            lines.append("    trailing_only_offset_is_reached = True")
    else:
        lines.append("    trailing_stop = False")

    lines.append(f"    startup_candle_count = {startup}")
    lines.append(f"    max_open_trades = {max_open_trades}")
    lines.append("    process_only_new_candles = True")
    lines.append("    can_short = False")
    lines.append("")

    # protections
    protections_cfg = risk.get("protections") or []
    lines.append("    @property")
    lines.append("    def protections(self):")
    lines.append(f"        return {_emit_protections(protections_cfg)}")
    lines.append("")

    # informative_pairs
    if informative_tfs:
        lines.append("    def informative_pairs(self):")
        lines.append("        pairs = self.dp.current_whitelist()")
        # Extend with all informative timeframes
        lines.append("        out = []")
        for tf in informative_tfs:
            lines.append(f"        out.extend((p, {tf!r}) for p in pairs)")
        lines.append("        return out")
        lines.append("")

    # populate_indicators
    _pop_ind = "    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:"
    lines.append(_pop_ind)
    primary_lines = _emit_indicator_lines(primary_uses, "dataframe", None)
    if primary_lines:
        lines.extend(primary_lines)
    else:
        lines.append("        # (no primary-timeframe indicators)")
        lines.append("        pass")

    # informative merges
    for tf, tf_uses in informative_tfs.items():
        var = f"informative_{tf}"
        lines.append("")
        lines.append(f"        # --- informative {tf} ---")
        lines.append(
            f"        {var} = self.dp.get_pair_dataframe("
            f"pair=metadata['pair'], timeframe={tf!r})"
        )
        tf_lines = _emit_indicator_lines(tf_uses, var, tf)
        lines.extend(tf_lines)
        lines.append(
            f"        dataframe = merge_informative_pair("
            f"dataframe, {var}, self.timeframe, {tf!r}, ffill=True)"
        )
    lines.append("")
    lines.append("        return dataframe")
    lines.append("")

    # populate_entry_trend
    _pop_entry = "    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:"
    lines.append(_pop_entry)
    if entry_compiled:
        tag = entry_long.get("tag", f"{doc.name}_entry")
        lines.append("        dataframe.loc[")
        lines.append(f"            ({entry_compiled.mask_expr}),")
        lines.append("            ['enter_long', 'enter_tag']")
        lines.append(f"        ] = (1, {tag!r})")
    else:
        lines.append("        # (no entry_long conditions)")
        lines.append("        pass")
    lines.append("        return dataframe")
    lines.append("")

    # populate_exit_trend
    _pop_exit = "    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:"
    lines.append(_pop_exit)
    if exit_compiled:
        tag = exit_long.get("tag", f"{doc.name}_exit")
        lines.append("        dataframe.loc[")
        lines.append(f"            ({exit_compiled.mask_expr}),")
        lines.append("            ['exit_long', 'exit_tag']")
        lines.append(f"        ] = (1, {tag!r})")
    else:
        lines.append("        # (no exit_long conditions)")
        lines.append("        pass")
    lines.append("        return dataframe")
    lines.append("")

    return "\n".join(lines)
