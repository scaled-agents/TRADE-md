"""`trade-md explain` — synthesize a TRADE.md into a compact, agent-readable summary.

The intent is that an agent picking up a strategy task runs
`trade-md explain TRADE.md` first to load the strategy's identity, risk
profile, and disable conditions into its working context — without having
to re-parse the full file.

Two output modes:
  - text (default): human-readable, ~30 lines
  - json:           structured, for programmatic injection into agent prompts
"""
from __future__ import annotations

import json
from typing import Any

from .parser import TradeDoc

# ---- Protection humanizer ------------------------------------------------

def _humanize_protection(p: dict[str, Any]) -> str:
    t = p.get("type", "?")
    if t == "StoplossGuard":
        return (
            f"StoplossGuard ({p.get('lookback', '?')}c lookback, "
            f"{p.get('trade_limit', '?')} trades, "
            f"{p.get('stop_duration', '?')}c stop)"
        )
    if t == "MaxDrawdown":
        return (
            f"MaxDrawdown ({p.get('lookback', '?')}c lookback, "
            f"{int(float(p.get('max_allowed_drawdown', 0)) * 100)}% max)"
        )
    if t == "CooldownPeriod":
        return f"CooldownPeriod ({p.get('stop_duration', '?')}c)"
    if t == "LowProfitPairs":
        return (
            f"LowProfitPairs ({p.get('lookback', '?')}c lookback, "
            f"required profit {p.get('required_profit', '?')})"
        )
    # Fallback: dump remaining fields
    rest = ", ".join(f"{k}={v}" for k, v in p.items() if k != "type")
    return f"{t} ({rest})"


def _humanize_disable_when(d: dict[str, Any]) -> str:
    if "separation_index_below" in d:
        return (
            f"separation_index < {d['separation_index_below']} "
            f"over trailing {d.get('lookback_trades', '?')} trades"
        )
    if "max_drawdown_exceeds" in d:
        pct = int(float(d["max_drawdown_exceeds"]) * 100)
        return f"max drawdown > {pct}% over {d.get('lookback_days', '?')} days"
    if "regime_shifts_to" in d:
        regimes = ", ".join(d["regime_shifts_to"])
        return f"regime shifts to {regimes}"
    if "correlation_exceeds" in d:
        return (
            f"correlation with active strategies > {d['correlation_exceeds']} "
            f"over {d.get('window_days', '?')} days"
        )
    return json.dumps(d, default=str)


def _format_roi(roi: dict[str, Any]) -> str:
    pairs = sorted(roi.items(), key=lambda kv: int(kv[0]))
    parts = []
    for mins, val in pairs:
        pct = float(val) * 100
        parts.append(f"{mins}m→{pct:.1f}%")
    return "ROI [" + ", ".join(parts) + "]"


def _format_trailing(t: dict[str, Any]) -> str:
    if not t.get("enabled"):
        return "no trailing"
    pos = float(t.get("positive", 0)) * 100
    off = float(t.get("offset", 0)) * 100
    base = f"trailing +{pos:.1f}%"
    if off:
        base += f" after {off:.1f}% offset"
    return base


def _format_conditions(conds: list[str]) -> str:
    """Render condition list as 'A AND B AND C'. Keep `{tokens}` literal — they
    carry meaning the reader defined, and resolving them can make the result
    harder to read, not easier."""
    if not conds:
        return "(none)"
    # Strip outer quotes / whitespace
    parts = [c.strip() for c in conds]
    return "\n              AND ".join(parts)


def _first_sentence(text: str, max_chars: int = 240) -> str:
    """Grab the opening of a prose block, up to a sentence boundary."""
    clean = " ".join(text.split())
    if not clean:
        return ""
    if len(clean) <= max_chars:
        return clean
    # try to cut at a sentence boundary
    cut = clean[:max_chars]
    for stop in (". ", "! ", "? "):
        i = cut.rfind(stop)
        if i > max_chars * 0.5:
            return cut[: i + 1].strip()
    return cut.rstrip() + "…"


# ---- Main formatters -----------------------------------------------------


def explain_text(doc: TradeDoc) -> str:
    """Human-readable summary, ~30 lines."""
    fm = doc.front_matter
    market = doc.market
    signals = doc.signals
    risk = doc.risk
    sizing = doc.sizing
    prov = fm.get("provenance") or {}
    lineage = fm.get("lineage") or {}
    disable = fm.get("disable_when") or []
    pair_u = market.get("pair_universe") or {}

    lines: list[str] = []

    # Header
    status = lineage.get("graduation_status", "?")
    iteration = lineage.get("kata_iteration")
    iter_part = f", kata iteration {iteration}" if iteration is not None else ""
    lines.append(f"{doc.name} @ {doc.version}  ({status}{iter_part})")
    lines.append("")

    # Thesis
    thesis = _first_sentence(doc.prose_sections.get("Thesis", ""))
    if thesis:
        lines.append(f"Thesis: {thesis}")
        lines.append("")

    # Market
    tfs = market.get("informative_timeframes") or []
    tf_part = (
        f"{market.get('timeframe', '?')} primary"
        + (f", {'/'.join(tfs)} informative" if tfs else "")
    )
    market_parts = [
        pair_u.get("exchange", "?"),
        pair_u.get("quote", "?"),
        pair_u.get("filter", "?"),
    ]
    lines.append(f"Market:     {' '.join(market_parts)} · {tf_part}")
    regime = ", ".join(market.get("regime") or [])
    if regime:
        lines.append(f"Regime:     {regime}")

    # Signals
    entry_long = signals.get("entry_long") or {}
    exit_long = signals.get("exit_long") or {}
    if entry_long.get("conditions"):
        conds = _format_conditions(entry_long["conditions"])
        tag = entry_long.get("tag", "")
        tag_part = f"\n              → tag \"{tag}\"" if tag else ""
        lines.append(f"Entry long: {conds}{tag_part}")
    if exit_long.get("conditions"):
        conds = _format_conditions(exit_long["conditions"])
        lines.append(f"Exit long:  {conds}")

    # Risk
    stop = risk.get("stoploss")
    if stop is not None:
        stop_pct = float(stop) * 100
        roi_str = _format_roi(risk.get("roi") or {})
        trail_str = _format_trailing(risk.get("trailing") or {})
        lines.append(f"Risk:       {stop_pct:.1f}% stop, {roi_str}, {trail_str}")

    # Sizing
    method = sizing.get("method", "?")
    sizing_extras = []
    if "fraction" in sizing:
        sizing_extras.append(f"@ {sizing['fraction']}")
    if "target_vol" in sizing:
        sizing_extras.append(f"target_vol={sizing['target_vol']}")
    moc = sizing.get("max_open_trades")
    if moc is not None:
        sizing_extras.append(f"max {moc} concurrent")
    sizing_line = f"{method} {' '.join(sizing_extras)}".strip()
    lines.append(f"Sizing:     {sizing_line}")

    # Protections
    prots = risk.get("protections") or []
    if prots:
        phrases = [_humanize_protection(p) for p in prots]
        lines.append(f"Protections: {', '.join(phrases)}")

    # Disable
    if disable:
        lines.append("")
        lines.append("Disable when:")
        for d in disable:
            lines.append(f"  • {_humanize_disable_when(d)}")

    # Provenance
    if prov:
        lines.append("")
        parts = []
        if "sharpe" in prov:
            parts.append(f"Sharpe {prov['sharpe']}")
        if "max_dd" in prov:
            parts.append(f"max_dd {int(float(prov['max_dd']) * 100)}%")
        if "win_rate" in prov:
            parts.append(f"win_rate {int(float(prov['win_rate']) * 100)}%")
        if "trades" in prov:
            parts.append(f"{prov['trades']} trades")
        if "separation_index" in prov:
            parts.append(f"SI {prov['separation_index']}")
        if parts:
            lines.append(f"Provenance: {', '.join(parts)}")
        lv = prov.get("last_validated")
        if lv:
            be = prov.get("backtest_engine", "")
            be_part = f" against {be}" if be else ""
            lines.append(f"            Last validated {lv}{be_part}")

    # Lineage
    if lineage:
        lines.append("")
        parts = []
        parent = lineage.get("parent")
        if parent:
            parts.append(f"{parent} → this")
        derived = lineage.get("derived_from")
        if derived:
            parts.append(f"derived from {derived}")
        if parts:
            lines.append(f"Lineage:    {'; '.join(parts)}")

    return "\n".join(lines)


def explain_json(doc: TradeDoc) -> dict[str, Any]:
    """Structured summary for programmatic injection into agent prompts."""
    fm = doc.front_matter
    signals = doc.signals
    risk = doc.risk
    prov = fm.get("provenance") or {}
    lineage = fm.get("lineage") or {}

    entry_long = signals.get("entry_long") or {}
    exit_long = signals.get("exit_long") or {}

    return {
        "strategy": {
            "name": doc.name,
            "version": doc.version,
            "graduation_status": lineage.get("graduation_status"),
            "kata_iteration": lineage.get("kata_iteration"),
        },
        "thesis": _first_sentence(doc.prose_sections.get("Thesis", ""), max_chars=500),
        "market": doc.market,
        "logic": {
            "entry_long_conditions": entry_long.get("conditions") or [],
            "entry_long_tag": entry_long.get("tag"),
            "exit_long_conditions": exit_long.get("conditions") or [],
            "exit_long_tag": exit_long.get("tag"),
        },
        "risk_profile": {
            "stoploss": risk.get("stoploss"),
            "roi": risk.get("roi"),
            "trailing": risk.get("trailing"),
            "protections_count": len(risk.get("protections") or []),
        },
        "sizing": doc.sizing,
        "disable_when": fm.get("disable_when") or [],
        "disable_when_humanized": [
            _humanize_disable_when(d) for d in (fm.get("disable_when") or [])
        ],
        "provenance": prov,
        "lineage": lineage,
        "prose_sections": list(doc.prose_sections.keys()),
    }
