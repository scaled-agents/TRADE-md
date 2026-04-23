"""TRADE.md CLI — `trade-md lint|compile|diff|spec|explain`.

Usage examples:
    trade-md lint examples/heritage-rsi-ema/TRADE.md
    trade-md compile --target freqtrade examples/heritage-rsi-ema/TRADE.md
    trade-md diff v0.3.0.TRADE.md v0.3.1.TRADE.md
    trade-md spec [--rules] [--format json]
"""
from __future__ import annotations

import argparse
import json
import sys
from importlib.metadata import entry_points
from pathlib import Path

from . import SPEC_VERSION, __version__
from .compilers.freqtrade import compile_freqtrade, write_compiled_output, _class_name
from .explain import explain_json, explain_text
from .linter import RECOMMENDED_PROSE, STALENESS_DAYS, lint
from .parser import parse_file

_REGRESS_DOWN = ("sharpe", "sortino", "win_rate", "profit_factor", "separation_index")
_REGRESS_UP = ("max_dd",)


def _resolve_compiler(target: str):
    """Resolve a compiler by name.

    Tries importlib.metadata entry points first (installed plugins),
    falls back to built-in compilers for in-repo dev.
    """
    try:
        eps = entry_points(group="trade_md.compilers")
        for ep in eps:
            if ep.name == target:
                return ep.load()
    except Exception:
        pass

    # Fallback: built-in compilers
    builtins = {
        "freqtrade": compile_freqtrade,
    }
    return builtins.get(target)


def _cmd_lint(args: argparse.Namespace) -> int:
    doc = parse_file(args.file)
    report = lint(doc)
    if args.format == "json":
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_human_lint(report)
    return 1 if report["summary"]["errors"] else 0


def _print_human_lint(report: dict) -> None:
    s = report["strategy"]
    summary = report["summary"]
    print(f"trade-md lint - {s['name']}@{s['version']}")
    print(f"  errors:   {summary['errors']}")
    print(f"  warnings: {summary['warnings']}")
    print(f"  info:     {summary['info']}")
    if not report["findings"]:
        print("  clean (ok)")
        return
    print()
    for f in report["findings"]:
        sigil = {"error": "X", "warning": "!", "info": "."}[f["severity"]]
        print(f"  {sigil} [{f['rule']}] {f['path']}")
        print(f"      {f['message']}")


def _cmd_compile(args: argparse.Namespace) -> int:
    doc = parse_file(args.file)
    compiler = _resolve_compiler(args.target)
    if compiler is None:
        print(f"error: unknown target {args.target!r}", file=sys.stderr)
        return 2
    try:
        output = compiler(doc, allow_version_drift=args.allow_version_drift)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    msg = write_compiled_output(output, args.out, _class_name(doc))
    if msg:
        print(msg)
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    a = parse_file(args.before)
    b = parse_file(args.after)
    report = _diff_docs(a, b)
    print(json.dumps(report, indent=2, default=str))
    # Exit 1 if perf regression detected
    return 1 if report.get("regression") else 0


def _diff_docs(a, b) -> dict:
    """Minimal v0.1 diff: compare top-level tokens and provenance metrics."""
    out: dict = {"tokens": {}, "provenance": {}, "regression": False}

    def section_diff(k: str):
        av = a.front_matter.get(k) or {}
        bv = b.front_matter.get(k) or {}
        added = sorted(set(bv) - set(av))
        removed = sorted(set(av) - set(bv))
        modified = sorted(k2 for k2 in set(av) & set(bv) if av[k2] != bv[k2])
        return {"added": added, "removed": removed, "modified": modified}

    for section in ("market", "signals", "indicators", "risk", "sizing"):
        out["tokens"][section] = section_diff(section)

    av = a.front_matter.get("provenance") or {}
    bv = b.front_matter.get("provenance") or {}
    for m in _REGRESS_DOWN + _REGRESS_UP:
        if m in av and m in bv:
            out["provenance"][m] = {"before": av[m], "after": bv[m]}
            if m in _REGRESS_DOWN and bv[m] < av[m]:
                out["regression"] = True
            if m in _REGRESS_UP and bv[m] > av[m]:
                out["regression"] = True
    return out


def _cmd_explain(args: argparse.Namespace) -> int:
    doc = parse_file(args.file)
    if args.format == "json":
        print(json.dumps(explain_json(doc), indent=2, default=str))
    else:
        print(explain_text(doc))
    return 0


_RULES = [
    {"id": "R001", "severity": "error", "summary": "required top-level fields present"},
    {"id": "R002", "severity": "error", "summary": "stoploss is negative"},
    {"id": "R003", "severity": "error", "summary": "first ROI step > |stoploss|"},
    {"id": "R004", "severity": "error", "summary": "informative TFs declared"},
    {"id": "R005", "severity": "error", "summary": "token refs resolve"},
    {"id": "R006", "severity": "error", "summary": "conditions parse"},
    {
        "id": "R007", "severity": "warning",
        "summary": f"last_validated within {STALENESS_DAYS}d",
    },
    {"id": "R008", "severity": "warning", "summary": "trailing offset >= positive"},
    {
        "id": "R009", "severity": "warning",
        "summary": f"prose sections present ({', '.join(RECOMMENDED_PROSE)})",
    },
    {"id": "R010", "severity": "info", "summary": "separation_index present"},
    {"id": "R011", "severity": "error", "summary": "custom indicator modules resolve"},
    {"id": "R012", "severity": "error", "summary": "declared inputs resolve"},
    {"id": "R013", "severity": "error", "summary": "output column names unique"},
    {"id": "R014", "severity": "error", "summary": "compute signature matches params"},
    {"id": "R015", "severity": "error", "summary": "no forbidden imports or calls"},
    {"id": "R016", "severity": "warning", "summary": "strategy directory contents"},
]


def _cmd_spec(args: argparse.Namespace) -> int:
    """Print the spec or the rules table."""
    # In src layout: __file__ is src/trade_md/cli.py
    # Repo root is 3 levels up: src/trade_md/ -> src/ -> repo root
    spec_path = Path(__file__).resolve().parent.parent.parent / "docs" / "SPEC.md"
    if args.rules_only:
        if args.format == "json":
            print(json.dumps({"version": SPEC_VERSION, "rules": _RULES}, indent=2))
        else:
            print(f"TRADE.md spec v{SPEC_VERSION} - linter rules")
            for r in _RULES:
                print(f"  [{r['id']}] {r['severity']:7s} {r['summary']}")
        return 0
    if spec_path.exists():
        print(spec_path.read_text(encoding="utf-8"))
    else:
        print(f"error: SPEC.md not found at {spec_path}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="trade-md", description="TRADE.md toolkit")
    ver = f"trade-md {__version__} (spec v{SPEC_VERSION})"
    p.add_argument("--version", action="version", version=ver)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_lint = sub.add_parser("lint", help="validate a TRADE.md file")
    p_lint.add_argument("file")
    p_lint.add_argument("--format", choices=["human", "json"], default="human")
    p_lint.set_defaults(func=_cmd_lint)

    p_compile = sub.add_parser("compile", help="emit engine-specific code")
    p_compile.add_argument("file")
    p_compile.add_argument("--target", default="freqtrade")
    p_compile.add_argument("-o", "--out")
    p_compile.add_argument("--allow-version-drift", action="store_true",
                           help="suppress version pin mismatch errors")
    p_compile.set_defaults(func=_cmd_compile)

    p_diff = sub.add_parser("diff", help="diff two TRADE.md versions")
    p_diff.add_argument("before")
    p_diff.add_argument("after")
    p_diff.set_defaults(func=_cmd_diff)

    p_spec = sub.add_parser("spec", help="print the spec or linter rules")
    p_spec.add_argument("--rules-only", action="store_true")
    p_spec.add_argument("--format", choices=["text", "json"], default="text")
    p_spec.set_defaults(func=_cmd_spec)

    p_explain = sub.add_parser("explain", help="summarize a strategy for agent context")
    p_explain.add_argument("file")
    p_explain.add_argument("--format", choices=["text", "json"], default="text")
    p_explain.set_defaults(func=_cmd_explain)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
