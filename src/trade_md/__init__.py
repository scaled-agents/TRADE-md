"""TRADE.md reference implementation — parser, linter, compiler.

Spec: docs/SPEC.md
"""

__version__ = "0.1.0"
SPEC_VERSION = "0.1"

from .compilers.freqtrade import compile_freqtrade  # noqa: E402
from .linter import Finding, lint  # noqa: E402
from .parser import TradeDoc, parse_file, parse_string  # noqa: E402

__all__ = [
    "SPEC_VERSION",
    "Finding",
    "TradeDoc",
    "__version__",
    "compile_freqtrade",
    "lint",
    "parse_file",
    "parse_string",
]
