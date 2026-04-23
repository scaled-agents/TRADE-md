"""TRADE.md linter — validates against spec v0.2 rules.

Returns structured findings (severity, rule id, path, message) suitable for
both CLI display and agent consumption.
"""
from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from .expr import BUILTIN_INDICATORS, OHLCV_NAMES, compile_expression
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

# Modules that are forbidden in custom indicator code (R015).
_FORBIDDEN_MODULES = {
    "socket", "urllib", "requests", "httpx", "aiohttp",
    "subprocess", "threading", "multiprocessing", "asyncio",
}
_FORBIDDEN_CALLS = {"eval", "exec"}

# Allowed contents in a strategy directory (R016).
_ALLOWED_DIR_ENTRIES = {
    "TRADE.md", "indicators", "backtest_results", "README.md",
    "__pycache__",
}


def lint(doc: TradeDoc) -> dict[str, Any]:
    """Run all linter rules over a parsed TRADE.md.

    Returns a dict with keys ``findings``, ``summary``, and ``strategy``.
    """
    findings: list[Finding] = []

    # Try to load custom indicators if present.
    custom_metas: dict[str, Any] = {}
    if doc.custom_indicators:
        try:
            custom_metas = doc.load_custom_indicators()
        except Exception:
            # R011 will surface the individual errors below.
            pass

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
                c = compile_expression(
                    cond, doc.indicators or {},
                    custom_indicators=custom_metas or None,
                )
                used_tfs |= c.timeframes
            except Exception as e:
                findings.append(Finding(
                    rule="R006", severity="error",
                    path=f"signals.{sig_name}.conditions[{i}]",
                    message=f"Invalid expression: {cond!r} — {e}",
                ))

    # also parse indicator expressions
    for ind_name, ind_body in (doc.indicators or {}).items():
        if isinstance(ind_body, str):
            expr = ind_body
        else:
            expr = (ind_body or {}).get("expr", "")
        if expr:
            try:
                c = compile_expression(
                    expr, doc.indicators or {},
                    custom_indicators=custom_metas or None,
                )
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

    # ----- v0.2 custom indicator rules -----
    if doc.custom_indicators:
        _lint_custom_indicators(doc, findings, custom_metas)

    # R016 — directory contents
    if doc.strategy_dir and doc.strategy_dir.is_dir():
        _lint_directory_contents(doc.strategy_dir, findings)

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


def _lint_custom_indicators(
    doc: TradeDoc,
    findings: list[Finding],
    custom_metas: dict[str, Any],
) -> None:
    """Run R011-R015 against custom indicator registrations."""
    from .indicator import IndicatorMetadata

    # Collect all known column names for collision detection (R013).
    known_cols: set[str] = set(OHLCV_NAMES)
    for bname in BUILTIN_INDICATORS:
        known_cols.add(bname)
        for out in BUILTIN_INDICATORS[bname]["outputs"]:
            known_cols.add(out)
    custom_output_cols: dict[str, str] = {}  # output_col -> as_name that declared it

    for ref in doc.custom_indicators:
        # R011 — module resolves and has exactly one @indicator function
        meta: IndicatorMetadata | None = custom_metas.get(ref.as_name)
        if meta is None:
            # The load failed; try to produce a specific error.
            try:
                doc.load_custom_indicators()
            except ImportError as e:
                findings.append(Finding(
                    rule="R011", severity="error",
                    path=f"custom_indicators.{ref.as_name}",
                    message=f"Cannot import module {ref.module!r}: {e}",
                ))
            except ValueError as e:
                findings.append(Finding(
                    rule="R011", severity="error",
                    path=f"custom_indicators.{ref.as_name}",
                    message=str(e),
                ))
            except Exception as e:
                findings.append(Finding(
                    rule="R011", severity="error",
                    path=f"custom_indicators.{ref.as_name}",
                    message=f"Failed to load {ref.module!r}: {e}",
                ))
            continue

        # R012 — declared inputs resolve to OHLCV or built-in indicator columns
        for inp in meta.inputs:
            if inp not in OHLCV_NAMES and inp not in BUILTIN_INDICATORS:
                # Also check if it matches a builtin's output name.
                builtin_outputs = set()
                for spec in BUILTIN_INDICATORS.values():
                    builtin_outputs.update(spec["outputs"])
                if inp not in builtin_outputs:
                    findings.append(Finding(
                        rule="R012", severity="error",
                        path=f"custom_indicators.{ref.as_name}.inputs",
                        message=(
                            f"Input {inp!r} does not resolve to an OHLCV name or "
                            f"built-in indicator column"
                        ),
                    ))

        # R013 — output column names don't collide
        for out in meta.outputs:
            if out in known_cols:
                findings.append(Finding(
                    rule="R013", severity="error",
                    path=f"custom_indicators.{ref.as_name}.outputs",
                    message=f"Output {out!r} collides with a built-in name",
                ))
            elif out in custom_output_cols:
                findings.append(Finding(
                    rule="R013", severity="error",
                    path=f"custom_indicators.{ref.as_name}.outputs",
                    message=(
                        f"Output {out!r} collides with output from "
                        f"custom indicator {custom_output_cols[out]!r}"
                    ),
                ))
            custom_output_cols[out] = ref.as_name

        # R013 — as_name must not collide with built-in indicator names
        if ref.as_name in BUILTIN_INDICATORS:
            findings.append(Finding(
                rule="R013", severity="error",
                path=f"custom_indicators.{ref.as_name}",
                message=f"Custom indicator alias {ref.as_name!r} collides with a built-in indicator",
            ))

        # R014 — compute signature matches declared params
        import inspect
        # Find the actual compute function from the module.
        try:
            import importlib
            import sys
            strategy_dir = doc.strategy_dir
            str_dir = str(strategy_dir) if strategy_dir else ""
            added = False
            if str_dir and str_dir not in sys.path:
                sys.path.insert(0, str_dir)
                added = True
            try:
                mod = importlib.import_module(ref.module)
                # Find decorated function.
                for attr_name in dir(mod):
                    obj = getattr(mod, attr_name)
                    if callable(obj) and hasattr(obj, "_trade_md_metadata"):
                        obj_meta = obj._trade_md_metadata
                        if isinstance(obj_meta, IndicatorMetadata):
                            sig = inspect.signature(obj)
                            sig_params = list(sig.parameters.keys())[1:]  # skip df
                            declared = set(meta.params.keys())
                            actual = set(sig_params)
                            if declared != actual:
                                findings.append(Finding(
                                    rule="R014", severity="error",
                                    path=f"custom_indicators.{ref.as_name}.params",
                                    message=(
                                        f"Signature mismatch: declared params "
                                        f"{sorted(declared)}, actual params {sorted(actual)}"
                                    ),
                                ))
                            break
            finally:
                if added and str_dir in sys.path:
                    sys.path.remove(str_dir)
        except Exception:
            pass  # R011 already caught this.

        # R015 — forbidden imports and constructs
        _lint_indicator_module_ast(ref, findings, doc.strategy_dir)


def _lint_indicator_module_ast(
    ref: Any,
    findings: list[Finding],
    strategy_dir: Path | None,
) -> None:
    """R015: AST-scan a custom indicator module for forbidden patterns."""
    if not strategy_dir:
        return
    module_path = strategy_dir / ref.module.replace(".", "/")
    # Try as a file, then as a package.
    py_path = module_path.with_suffix(".py")
    if not py_path.exists():
        return

    try:
        source = py_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_path))
    except Exception:
        return

    for node in ast.walk(tree):
        # Check imports.
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _FORBIDDEN_MODULES:
                    findings.append(Finding(
                        rule="R015", severity="warning",
                        path=f"custom_indicators.{ref.as_name}",
                        message=f"Forbidden import: {alias.name!r}",
                    ))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top in _FORBIDDEN_MODULES:
                    findings.append(Finding(
                        rule="R015", severity="warning",
                        path=f"custom_indicators.{ref.as_name}",
                        message=f"Forbidden import: {node.module!r}",
                    ))
        # Check calls to eval/exec.
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
                findings.append(Finding(
                    rule="R015", severity="warning",
                    path=f"custom_indicators.{ref.as_name}",
                    message=f"Forbidden call: {node.func.id}()",
                ))


def _lint_directory_contents(strategy_dir: Path, findings: list[Finding]) -> None:
    """R016: Flag unexpected files or directories in the strategy directory."""
    for entry in strategy_dir.iterdir():
        if entry.name.startswith("."):
            continue  # Skip hidden files.
        if entry.name not in _ALLOWED_DIR_ENTRIES:
            findings.append(Finding(
                rule="R016", severity="warning",
                path=f"directory.{entry.name}",
                message=f"Unexpected entry {entry.name!r} in strategy directory",
            ))


def lint_indicator_standalone(path: str | Path) -> dict[str, Any]:
    """Run R011, R014, R015 against a single indicator module file.

    Used by ``trade-md lint-indicator`` for checking indicators without a
    TRADE.md context.
    """
    import importlib.util
    import sys

    from .indicator import IndicatorMetadata

    p = Path(path)
    findings: list[Finding] = []

    if not p.exists():
        findings.append(Finding(
            rule="R011", severity="error",
            path=str(p),
            message=f"File not found: {p}",
        ))
        return _make_indicator_report(findings, str(p))

    # R011 — try to load the module.
    module_name = p.stem
    spec = importlib.util.spec_from_file_location(module_name, str(p))
    if spec is None or spec.loader is None:
        findings.append(Finding(
            rule="R011", severity="error",
            path=str(p),
            message=f"Cannot create module spec from {p}",
        ))
        return _make_indicator_report(findings, str(p))

    # Add parent to sys.path so relative imports work.
    parent_dir = str(p.parent.parent)
    added = parent_dir not in sys.path
    if added:
        sys.path.insert(0, parent_dir)

    try:
        import types
        mod = types.ModuleType(module_name)
        mod.__file__ = str(p)
        mod.__loader__ = spec.loader
        sys.modules[module_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            findings.append(Finding(
                rule="R011", severity="error",
                path=str(p),
                message=f"Failed to import module: {e}",
            ))
            return _make_indicator_report(findings, str(p))
        finally:
            sys.modules.pop(module_name, None)

        # Find the decorated function.
        decorated = []
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if callable(obj) and hasattr(obj, "_trade_md_metadata"):
                meta = obj._trade_md_metadata
                if isinstance(meta, IndicatorMetadata):
                    decorated.append((obj, meta))

        if len(decorated) == 0:
            findings.append(Finding(
                rule="R011", severity="error",
                path=str(p),
                message="No @indicator-decorated function found",
            ))
        elif len(decorated) > 1:
            findings.append(Finding(
                rule="R011", severity="error",
                path=str(p),
                message=f"Found {len(decorated)} @indicator-decorated functions; expected 1",
            ))
        else:
            fn, meta = decorated[0]
            # R014 — signature matches params.
            import inspect
            sig = inspect.signature(fn)
            sig_params = list(sig.parameters.keys())[1:]
            declared = set(meta.params.keys())
            actual = set(sig_params)
            if declared != actual:
                findings.append(Finding(
                    rule="R014", severity="error",
                    path=str(p),
                    message=(
                        f"Signature mismatch: declared params {sorted(declared)}, "
                        f"actual params {sorted(actual)}"
                    ),
                ))
    finally:
        if added and parent_dir in sys.path:
            sys.path.remove(parent_dir)

    # R015 — AST scan for forbidden patterns.
    try:
        source = p.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in _FORBIDDEN_MODULES:
                        findings.append(Finding(
                            rule="R015", severity="warning",
                            path=str(p),
                            message=f"Forbidden import: {alias.name!r}",
                        ))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top in _FORBIDDEN_MODULES:
                        findings.append(Finding(
                            rule="R015", severity="warning",
                            path=str(p),
                            message=f"Forbidden import: {node.module!r}",
                        ))
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
                    findings.append(Finding(
                        rule="R015", severity="warning",
                        path=str(p),
                        message=f"Forbidden call: {node.func.id}()",
                    ))
    except Exception:
        pass

    return _make_indicator_report(findings, str(p))


def _make_indicator_report(findings: list[Finding], path: str) -> dict[str, Any]:
    summary = {
        "errors": sum(1 for f in findings if f.severity == "error"),
        "warnings": sum(1 for f in findings if f.severity == "warning"),
        "info": sum(1 for f in findings if f.severity == "info"),
    }
    return {
        "findings": [f.to_dict() for f in findings],
        "summary": summary,
        "indicator": path,
    }
