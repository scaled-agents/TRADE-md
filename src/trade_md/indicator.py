"""The ``@indicator(...)`` decorator for custom indicator modules.

Attaches an ``IndicatorMetadata`` to the wrapped function as
``fn._trade_md_metadata``.  The function itself is returned unchanged --
no wrapping, no runtime overhead.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from .params import IntParam, Param


@dataclass(frozen=True)
class IndicatorMetadata:
    """Decoded metadata attached to a decorated indicator function."""

    inputs: list[str]
    params: dict[str, Param]
    outputs: list[str]
    startup_candles: int
    description: str
    version: str
    func_name: str


def indicator(
    *,
    inputs: Sequence[str],
    params: dict[str, Param] | None = None,
    outputs: Sequence[str],
    startup_candles: int | None = None,
    description: str = "",
    version: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that attaches :class:`IndicatorMetadata` to a compute function.

    Validates the wrapped function's signature against *params* at decoration
    time and raises ``TypeError`` on mismatch.
    """
    resolved_params: dict[str, Param] = dict(params) if params else {}

    # Infer startup_candles from the max IntParam.min if not explicitly set.
    if startup_candles is None:
        candidates = [
            p.min for p in resolved_params.values()
            if isinstance(p, IntParam) and p.min is not None
        ]
        startup_candles = max(candidates) if candidates else 0

    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(fn)
        sig_params = list(sig.parameters.keys())

        # First param is the dataframe — skip it for matching.
        if not sig_params:
            raise TypeError(
                f"@indicator-decorated function {fn.__name__!r} must accept "
                "at least one positional argument (the dataframe)"
            )
        fn_param_names = sig_params[1:]  # skip df

        # Check declared params match function signature.
        declared = set(resolved_params.keys())
        actual = set(fn_param_names)
        if declared != actual:
            missing = declared - actual
            extra = actual - declared
            parts = []
            if missing:
                parts.append(f"declared but not in signature: {sorted(missing)}")
            if extra:
                parts.append(f"in signature but not declared: {sorted(extra)}")
            raise TypeError(
                f"@indicator params mismatch on {fn.__name__!r}: "
                + "; ".join(parts)
            )

        meta = IndicatorMetadata(
            inputs=list(inputs),
            params=resolved_params,
            outputs=list(outputs),
            startup_candles=startup_candles,
            description=description,
            version=version,
            func_name=fn.__name__,
        )
        fn._trade_md_metadata = meta  # type: ignore[attr-defined]
        return fn

    return _decorator
