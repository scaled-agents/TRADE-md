"""TRADE.md reference implementation — parser, linter, compiler.

Spec: docs/SPEC.md
"""

__version__ = "0.2.1"
SPEC_VERSION = "0.2"

from .compilers.freqtrade import compile_freqtrade  # noqa: E402
from .indicator import IndicatorMetadata, indicator  # noqa: E402
from .linter import Finding, lint  # noqa: E402
from .params import BoolParam, FloatParam, IntParam, Param, StrParam  # noqa: E402
from .parser import TradeDoc, parse_file, parse_string  # noqa: E402

__all__ = [
    "BoolParam",
    "FloatParam",
    "Finding",
    "IndicatorMetadata",
    "IntParam",
    "Param",
    "SPEC_VERSION",
    "StrParam",
    "TradeDoc",
    "__version__",
    "compile_freqtrade",
    "indicator",
    "lint",
    "parse_file",
    "parse_string",
]
