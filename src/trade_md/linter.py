"""TRADE.md linter — validates against spec v0.1 rules.

Returns structured findings (severity, rule id, path, message) suitable for
both CLI display and agent consumption.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal

from .expr import compile_expression
from .parser import TradeDoc

Severity = Literal["error", "warning", "info"]


@dataclass
class Finding:
    rule: str
    severity: Severity
    path: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


REQUIRED_TOP_LEVEL = ["name", "version", "market", "signals", "risk", "sizing"]
RECOMMENDED_PROSE = ["Thesis", "When to disable"]
STALENESS_DAYS = 90


def lint(doc: TradeDoc) -> dict[str, Any]:
    """Run all v0.1 linter rules over a parsed TRADE.md.

    Returns a dict with keys `findings`, `summary`, and `strategy`.
    """
    findings: list[Finding] = []

    # R001 — required top-level fields
    for k in REQUIRED_TOP_LEVEL:
        if k not in doc.front_matter:
            findings.append(Finding(
                rule="R001", severity="error", path=k,
                message=f"Required field `{k}` is missing from front matter",
            ))

    # R002 — stoploss is negative
    stop = doc.risk.get("stoploss")
    if stop is None:
        findings.append(Finding(
            rule="R001", severity="error", path="risk.stoploss",
            message="`risk.stoploss` is required",
        ))
    elif not isinstance(stop, (int, float)) or stop >= 0:
        findings.append(Finding(
            rule="R002", severity="error", path="risk.stoploss",
            message=f"`risk.stoploss` must be a negative number, got {stop!r}",
        ))

    # R003 — first ROI step >= |stoploss| would mean stop before any take-profit
    roi = doc.risk.get("roi") or {}
    if isinstance(stop, (int, float)) and roi:
        first_key = sorted(roi.keys(), key=lambda k: int(k))[0]
        first_val = roi[first_key]
        if isinstance(first_val, (int, float)) and first_val <= abs(stop):
            findings.append(Finding(
                rule="R003", severity="error", path=f"risk.roi.{first_key}",
                message=(
                    f"First ROI step ({first_val}) is <= |stoploss| ({abs(stop)}). "
                    "Stop would trigger before any take-profit is reachable."
                ),
            ))

    # R006 — conditions parse; R004 — informative TFs declared; R005 — tokens resolve
    declared_tfs = set(doc.market.get("informative_timeframes") or [])
    declared_indicators = set((doc.indicators or {}).keys())
    used_tfs: set[str] = set()
    used_tokens: set[str] = set()

    # collect token refs and parse conditions
    for sig_name, sig_body in (doc.signals or {}).items():
        conds = (sig_body or {}).get("conditions") or []
        for i, cond in enumerate(conds):
            # token refs
            for m in re.finditer(r"\{(\w+)\}", cond):
                used_tokens.add(m.group(1))
            # parse
            try:
                c = compile_expression(cond, doc.indicators or {})
                used_tfs |= c.timeframes
            except Exception as e:
                findings.append(Finding(
                    rule="R006", severity="error",
                    path=f"signals.{sig_name}.conditions[{i}]",
                    message=f"Invalid expression: {cond!r} — {e}",
                ))

    # also parse indicator expressions
    for ind_name, ind_body in (doc.indicators or {}).items():
        expr = (ind_body or {}).get("expr", "")
        if expr:
            try:
                c = compile_expression(expr, doc.indicators or {})
                used_tfs |= c.timeframes
            except Exception as e:
                findings.append(Finding(
                    rule="R006", severity="error",
                    path=f"indicators.{ind_name}.expr",
                    message=f"Invalid expression: {expr!r} — {e}",
                ))

    # R004 — declared vs used timeframes
    for tf in used_tfs - declared_tfs:
        findings.append(Finding(
            rule="R004", severity="error", path="market.informative_timeframes",
            message=(
                f"Informative timeframe `{tf}` is used in conditions but not "
                f"declared in `market.informative_timeframes`"
            ),
        ))

    # R005 — tokens resolve
    for tok in used_tokens - declared_indicators:
        findings.append(Finding(
            rule="R005", severity="error", path="signals",
            message=f"Token `{{{tok}}}` referenced in conditions but not declared in `indicators`",
        ))

    # R007 — provenance freshness
    prov = doc.front_matter.get("provenance") or {}
    lv = prov.get("last_validated")
    if lv:
        try:
            d = lv if isinstance(lv, date) else datetime.fromisoformat(str(lv)).date()
            age = (datetime.utcnow().date() - d).days
            if age > STALENESS_DAYS:
                findings.append(Finding(
                    rule="R007", severity="warning", path="provenance.last_validated",
                    message=f"Backtest is {age} days old (threshold: {STALENESS_DAYS})",
                ))
        except Exception:
            findings.append(Finding(
                rule="R007", severity="warning", path="provenance.last_validated",
                message=f"Could not parse `last_validated` as ISO date: {lv!r}",
            ))

    # R008 — trailing offset > positive is typically a misconfiguration
    trailing = doc.risk.get("trailing") or {}
    if trailing.get("enabled"):
        pos = trailing.get("positive")
        off = trailing.get("offset")
        if isinstance(pos, (int, float)) and isinstance(off, (int, float)):
            if off < pos:
                findings.append(Finding(
                    rule="R008", severity="warning", path="risk.trailing",
                    message=(
                        f"Trailing `offset` ({off}) is less than `positive` ({pos}); "
                        "trailing stop may activate before the offset is reached."
                    ),
                ))

    # R009 — prose sections present
    for section in RECOMMENDED_PROSE:
        if section not in doc.prose_sections:
            findings.append(Finding(
                rule="R009", severity="warning", path=f"prose.{section}",
                message=f"Recommended prose section `## {section}` is missing",
            ))

    # R010 — separation index present
    if "separation_index" not in prov:
        findings.append(Finding(
            rule="R010", severity="info", path="provenance.separation_index",
            message="`provenance.separation_index` not present",
        ))

    # summary
    summary = {
        "errors": sum(1 for f in findings if f.severity == "error"),
        "warnings": sum(1 for f in findings if f.severity == "warning"),
        "info": sum(1 for f in findings if f.severity == "info"),
    }

    return {
        "findings": [f.to_dict() for f in findings],
        "summary": summary,
        "strategy": {
            "name": doc.name,
            "version": doc.version,
        },
    }
