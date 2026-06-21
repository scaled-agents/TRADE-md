"""Freqtrade compiler — emits an IStrategy Python file from a TradeDoc.

Supports:
- Primary + informative timeframes (via `merge_informative_pair`)
- Builtin indicators mapped to `talib.abstract`
- Custom indicators (v0.2) — imports from sibling package
- Pandas rolling / shift / pct_change
- Entry/exit long and short conditions
- Risk config (stoploss, minimal_roi, trailing)
- Custom stoploss (atr_wick) and custom exit (time_bailout) hooks
- Protections (StoplossGuard, MaxDrawdown, ...)
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from ..expr import (
    BUILTIN_INDICATORS,
    IndicatorUse,
    compile_conditions,
)
from ..parser import TradeDoc

# ---- Protection field name mapping ---------------------------------------

# Map TRADE.md short field names -> freqtrade protection keys.
_PROTECTION_FIELD_MAP = {
    "lookback": "lookback_period_candles",
    "stop_duration": "stop_duration_candles",
    "trade_limit": "trade_limit",
    "max_allowed_drawdown": "max_allowed_drawdown",
    "required_profit": "required_profit",
    "only_per_pair": "only_per_pair",
    "only_per_side": "only_per_side",
    "type": None,  # handled separately -> "method"
}


def _pascal_case(name: str) -> str:
    """'heritage-rsi-ema' -> 'HeritageRsiEma'."""
    return "".join(p.capitalize() for p in re.split(r"[-_\s]+", name) if p)


def _class_name(doc: TradeDoc) -> str:
    return _pascal_case(doc.name) or "CompiledStrategy"


# ---- Indicator line emission ---------------------------------------------


def _emit_builtin_line(use: IndicatorUse, df_var: str) -> str:
    spec = BUILTIN_INDICATORS[use.name]
    talib_name = spec["talib"]
    args = list(use.args)
    if use.name in ("rsi", "ema", "sma", "atr", "adx"):
        period = args[0]
        call = f"ta.{talib_name}({df_var}, timeperiod={period})"
    elif use.name in ("macd", "macd_signal", "macd_hist"):
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
    if not tf:
        return col
    suffix = f"_{tf}"
    return col[: -len(suffix)] if col.endswith(suffix) else col


def _topo_sort_uses(uses: list[IndicatorUse]) -> list[IndicatorUse]:
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
    custom_imports: dict[str, str] | None = None,
    indent: str = "        ",
) -> list[str]:
    lines: list[str] = []
    tf_uses = [u for u in uses if u.timeframe == timeframe]
    tf_uses = _topo_sort_uses(tf_uses)

    for u in tf_uses:
        out_col = _strip_tf(u.col, timeframe) if timeframe else u.col

        if u.kind == "ohlcv":
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
        elif u.kind == "custom":
            # Custom indicator call.
            import_name = custom_imports.get(u.name, f"_{u.name}_compute") if custom_imports else f"_{u.name}_compute"
            # Reconstruct kwargs from args (which are sorted tuples of (key, value))
            kwargs_str = ", ".join(f"{k}={v!r}" for k, v in u.args)
            rhs = f"{import_name}({df_var}, {kwargs_str})"
        else:
            raise ValueError(f"Unknown use kind: {u.kind}")

        lines.append(f"{indent}{df_var}[{out_col!r}] = {rhs}")
    return lines


def _compute_startup(uses: list[IndicatorUse], custom_metas: dict[str, Any] | None = None) -> int:
    max_p = 0
    for u in uses:
        if u.kind == "custom" and custom_metas and u.name in custom_metas:
            max_p = max(max_p, custom_metas[u.name].startup_candles)
        elif u.args:
            for a in u.args:
                if isinstance(a, (int, float)):
                    max_p = max(max_p, int(a))
    return max_p + 50


def _emit_protections(protections: list[dict[str, Any]]) -> str:
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


def _check_version_pins(doc: TradeDoc, custom_metas: dict[str, Any], allow_drift: bool) -> None:
    """Enforce version_pin on custom indicators. Raises ValueError on mismatch."""
    for ref in doc.custom_indicators:
        if ref.version_pin is None:
            continue
        meta = custom_metas.get(ref.as_name)
        if meta is None:
            continue
        if not meta.version:
            continue
        # Pin format: "1.0" means >=1.0.0,<1.1.0; "1" means >=1.0.0,<2.0.0
        pin = ref.version_pin
        actual = meta.version
        if not _version_matches_pin(actual, pin):
            msg = (
                f"Custom indicator {ref.as_name!r} version {actual!r} "
                f"does not match pin {pin!r}"
            )
            if allow_drift:
                pass  # Silently allow.
            else:
                raise ValueError(msg)


def _version_matches_pin(version: str, pin: str) -> bool:
    """Check if a semver version matches a pin string.

    Pin "1.0" means >=1.0.0,<1.1.0. Pin "1" means >=1.0.0,<2.0.0.
    """
    v_parts = version.split(".")
    p_parts = pin.split(".")
    # Compare prefix.
    for i, pp in enumerate(p_parts):
        if i >= len(v_parts):
            return False
        if v_parts[i] != pp:
            return False
    return True


# ---- Main entry point ----------------------------------------------------


def _emit_custom_stoploss_atr_wick(cfg: dict[str, Any]) -> tuple[list[str], IndicatorUse]:
    """Emit a custom_stoploss method that trails just outside the entry candle's
    ATR-scaled wick. Returns the method body lines and the IndicatorUse for the
    ATR column the method depends on (so populate_indicators emits it)."""
    period = int(cfg.get("atr_period", 14))
    mult = float(cfg.get("atr_multiplier", 1.5))
    col = f"atr_{period}"
    atr_use = IndicatorUse(
        col=col, kind="builtin", name="atr", args=(period,), timeframe=None,
    )
    lines = [
        "    def custom_stoploss(self, pair: str, trade, current_time,",
        "                        current_rate: float, current_profit: float,",
        "                        **kwargs) -> float | None:",
        '        """ATR-wick stop: anchored at entry_price ± (atr * multiplier)."""',
        "        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)",
        "        if df is None or len(df) < 1:",
        "            return None",
        f"        atr = df[{col!r}].iat[-1]",
        "        if atr is None or atr == 0 or atr != atr:  # NaN check",
        "            return None",
        f"        offset = atr * {mult}",
        "        if trade.is_short:",
        "            sl_price = trade.open_rate + offset",
        "            return (current_rate / sl_price) - 1",
        "        sl_price = trade.open_rate - offset",
        "        return (sl_price / current_rate) - 1",
        "",
    ]
    return lines, atr_use


def _emit_custom_exit_time_bailout(cfg: dict[str, Any], timeframe: str) -> list[str]:
    """Emit a custom_exit method that exits the trade after max_candles bars,
    regardless of P/L."""
    max_candles = int(cfg.get("max_candles", 16))
    tag = str(cfg.get("tag", "time_bailout"))
    # Convert timeframe to minutes-per-candle.
    minutes = _timeframe_to_minutes(timeframe)
    threshold_seconds = max_candles * minutes * 60
    lines = [
        "    def custom_exit(self, pair: str, trade, current_time,",
        "                    current_rate: float, current_profit: float,",
        "                    **kwargs) -> str | None:",
        f'        """Time bailout: exit after {max_candles} candles."""',
        "        elapsed = (current_time - trade.open_date_utc).total_seconds()",
        f"        if elapsed >= {threshold_seconds}:",
        f"            return {tag!r}",
        "        return None",
        "",
    ]
    return lines


def _timeframe_to_minutes(tf: str) -> int:
    """Convert a freqtrade timeframe string (e.g. '15m', '1h', '4h', '1d') to minutes."""
    if not tf:
        raise ValueError("timeframe is required for time-based exits")
    unit = tf[-1]
    try:
        n = int(tf[:-1])
    except ValueError as e:
        raise ValueError(f"Unparseable timeframe: {tf!r}") from e
    if unit == "m":
        return n
    if unit == "h":
        return n * 60
    if unit == "d":
        return n * 60 * 24
    raise ValueError(f"Unsupported timeframe unit in {tf!r}")


_CUSTOM_STOPLOSS_EMITTERS = {
    "atr_wick": _emit_custom_stoploss_atr_wick,
}

_CUSTOM_EXIT_EMITTERS = {
    "time_bailout": _emit_custom_exit_time_bailout,
}


def compile_freqtrade(doc: TradeDoc, allow_version_drift: bool = False) -> str | dict[str, str]:
    """Compile a TradeDoc into freqtrade IStrategy source.

    Returns a string for single-file output (no custom indicators) or a
    dict of ``{relative_path: content}`` for directory output.
    """
    # Load custom indicators if present.
    custom_metas: dict[str, Any] = {}
    has_custom = bool(doc.custom_indicators)
    if has_custom:
        custom_metas = doc.load_custom_indicators()
        _check_version_pins(doc, custom_metas, allow_version_drift)

    # 1. Compile conditions
    signals = doc.signals
    indicators = doc.indicators

    entry_long = signals.get("entry_long") or {}
    exit_long = signals.get("exit_long") or {}
    entry_short = signals.get("entry_short") or {}
    exit_short = signals.get("exit_short") or {}

    def _compile_side(block: dict) -> Any:
        conds = block.get("conditions") or []
        if not conds:
            return None
        return compile_conditions(
            conds, indicators, custom_indicators=custom_metas or None,
        )

    entry_compiled = _compile_side(entry_long)
    exit_compiled = _compile_side(exit_long)
    entry_short_compiled = _compile_side(entry_short)
    exit_short_compiled = _compile_side(exit_short)

    has_shorts = bool(entry_short_compiled or exit_short_compiled)

    # 2. Aggregate all uses
    all_uses: list[IndicatorUse] = []
    seen = set()
    for c in (entry_compiled, exit_compiled, entry_short_compiled, exit_short_compiled):
        if c is None:
            continue
        for u in c.uses:
            if u.col not in seen:
                seen.add(u.col)
                all_uses.append(u)

    # 2b. Custom stoploss / custom exit blocks.
    # These may inject extra indicator uses (e.g. ATR for atr_wick) and emit
    # methods appended after populate_exit_trend.
    custom_stoploss_cfg = doc.risk.get("custom_stoploss") or None
    custom_exit_cfg = doc.risk.get("custom_exit") or None

    custom_stoploss_lines: list[str] = []
    if custom_stoploss_cfg:
        cs_type = custom_stoploss_cfg.get("type")
        emitter = _CUSTOM_STOPLOSS_EMITTERS.get(cs_type)
        if not emitter:
            raise ValueError(
                f"Unsupported custom_stoploss.type: {cs_type!r}. "
                f"Supported: {sorted(_CUSTOM_STOPLOSS_EMITTERS)}"
            )
        custom_stoploss_lines, extra_use = emitter(custom_stoploss_cfg)
        if extra_use is not None and extra_use.col not in seen:
            seen.add(extra_use.col)
            all_uses.append(extra_use)

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
    startup = _compute_startup(all_uses, custom_metas)

    # Build custom indicator import mapping: as_name -> private import name
    custom_imports: dict[str, str] = {}
    for ref in doc.custom_indicators:
        custom_imports[ref.as_name] = f"_{ref.as_name}_compute"

    # 5. Emit strategy source
    lines: list[str] = []
    lines.append('"""')
    lines.append(f"Auto-generated by trade-md from {doc.name}@{doc.version}.")
    lines.append("")
    lines.append("DO NOT EDIT BY HAND - modify TRADE.md and recompile.")
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

    # Custom indicator imports.
    if has_custom:
        lines.append("")
        for ref in doc.custom_indicators:
            import_name = custom_imports[ref.as_name]
            lines.append(f"from .indicators.{ref.module.split('.')[-1]} import compute as {import_name}")

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
    lines.append(f"    can_short = {has_shorts}")
    if custom_stoploss_cfg:
        lines.append("    use_custom_stoploss = True")
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
        lines.append("        out = []")
        for tf in informative_tfs:
            lines.append(f"        out.extend((p, {tf!r}) for p in pairs)")
        lines.append("        return out")
        lines.append("")

    # populate_indicators
    _pop_ind = "    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:"
    lines.append(_pop_ind)
    primary_lines = _emit_indicator_lines(primary_uses, "dataframe", None, custom_imports)
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
        tf_lines = _emit_indicator_lines(tf_uses, var, tf, custom_imports)
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
    emitted_entry = False
    if entry_compiled:
        tag = entry_long.get("tag", f"{doc.name}_entry")
        lines.append("        dataframe.loc[")
        lines.append(f"            ({entry_compiled.mask_expr}),")
        lines.append("            ['enter_long', 'enter_tag']")
        lines.append(f"        ] = (1, {tag!r})")
        emitted_entry = True
    if entry_short_compiled:
        tag = entry_short.get("tag", f"{doc.name}_entry_short")
        lines.append("        dataframe.loc[")
        lines.append(f"            ({entry_short_compiled.mask_expr}),")
        lines.append("            ['enter_short', 'enter_tag']")
        lines.append(f"        ] = (1, {tag!r})")
        emitted_entry = True
    if not emitted_entry:
        lines.append("        # (no entry conditions)")
        lines.append("        pass")
    lines.append("        return dataframe")
    lines.append("")

    # populate_exit_trend
    _pop_exit = "    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:"
    lines.append(_pop_exit)
    emitted_exit = False
    if exit_compiled:
        tag = exit_long.get("tag", f"{doc.name}_exit")
        lines.append("        dataframe.loc[")
        lines.append(f"            ({exit_compiled.mask_expr}),")
        lines.append("            ['exit_long', 'exit_tag']")
        lines.append(f"        ] = (1, {tag!r})")
        emitted_exit = True
    if exit_short_compiled:
        tag = exit_short.get("tag", f"{doc.name}_exit_short")
        lines.append("        dataframe.loc[")
        lines.append(f"            ({exit_short_compiled.mask_expr}),")
        lines.append("            ['exit_short', 'exit_tag']")
        lines.append(f"        ] = (1, {tag!r})")
        emitted_exit = True
    if not emitted_exit:
        lines.append("        # (no exit conditions)")
        lines.append("        pass")
    lines.append("        return dataframe")
    lines.append("")

    # custom_stoploss method (if configured)
    if custom_stoploss_lines:
        lines.extend(custom_stoploss_lines)

    # custom_exit method (if configured)
    if custom_exit_cfg:
        ce_type = custom_exit_cfg.get("type")
        emitter = _CUSTOM_EXIT_EMITTERS.get(ce_type)
        if not emitter:
            raise ValueError(
                f"Unsupported custom_exit.type: {ce_type!r}. "
                f"Supported: {sorted(_CUSTOM_EXIT_EMITTERS)}"
            )
        lines.extend(emitter(custom_exit_cfg, timeframe))

    strategy_src = "\n".join(lines)

    # 6. Return format depends on custom indicators.
    if not has_custom:
        return strategy_src

    # Directory output: dict of {relative_path: content}
    result: dict[str, str] = {}
    result["__init__.py"] = (
        f'"""Strategy package for {doc.name}."""\n'
        f"from .strategy import {class_name}\n\n"
        f'__all__ = ["{class_name}"]\n'
    )
    result["strategy.py"] = strategy_src
    result["indicators/__init__.py"] = ""

    # Copy indicator modules.
    strategy_dir = doc.strategy_dir
    for ref in doc.custom_indicators:
        mod_file = ref.module.split(".")[-1] + ".py"
        src_path = strategy_dir / ref.module.replace(".", "/")
        src_py = src_path.with_suffix(".py")
        if src_py.exists():
            result[f"indicators/{mod_file}"] = src_py.read_text(encoding="utf-8")

    return result


def write_compiled_output(
    output: str | dict[str, str],
    out_path: str | Path | None,
    class_name: str,
) -> str:
    """Write compiled output to disk. Returns a summary message.

    For single-file output, writes to out_path (or prints to stdout).
    For directory output, creates the directory and writes all files.
    """
    if isinstance(output, str):
        # Single file.
        if out_path:
            Path(out_path).write_text(output, encoding="utf-8")
            return f"wrote {out_path} ({len(output.splitlines())} lines)"
        else:
            print(output)
            return ""
    else:
        # Directory output.
        if not out_path:
            raise ValueError(
                "Strategies with custom indicators require -o <directory> "
                "for output (cannot emit a directory to stdout)"
            )
        out_dir = Path(out_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        total_lines = 0
        for relpath, content in output.items():
            fpath = out_dir / relpath
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content, encoding="utf-8")
            total_lines += len(content.splitlines())
        return f"wrote {out_dir}/ ({len(output)} files, {total_lines} lines)"
