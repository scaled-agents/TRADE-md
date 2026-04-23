"""Typed parameter descriptors for custom indicators.

Each Param subclass is frozen and carries constraints that the linter validates
at compile time against literal DSL arguments.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class Param:
    """Base class for indicator parameter descriptors."""

    default: Any = None
    description: str = ""

    def validate(self, value: Any) -> None:  # noqa: ANN401
        """Validate *value* against this param's constraints.

        Raises TypeError for wrong type, ValueError for out-of-range.
        """
        raise NotImplementedError


@dataclass(frozen=True)
class IntParam(Param):
    """Integer parameter with optional min/max bounds."""

    default: int = 0
    min: int | None = None
    max: int | None = None

    def validate(self, value: Any) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Expected int, got {type(value).__name__}: {value!r}")
        if self.min is not None and value < self.min:
            raise ValueError(f"Value {value} is below minimum {self.min}")
        if self.max is not None and value > self.max:
            raise ValueError(f"Value {value} is above maximum {self.max}")


@dataclass(frozen=True)
class FloatParam(Param):
    """Float parameter with optional min/max bounds."""

    default: float = 0.0
    min: float | None = None
    max: float | None = None

    def validate(self, value: Any) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"Expected float, got {type(value).__name__}: {value!r}")
        val = float(value)
        if self.min is not None and val < self.min:
            raise ValueError(f"Value {val} is below minimum {self.min}")
        if self.max is not None and val > self.max:
            raise ValueError(f"Value {val} is above maximum {self.max}")


@dataclass(frozen=True)
class StrParam(Param):
    """String parameter with optional choices constraint."""

    default: str = ""
    choices: Sequence[str] | None = None

    def validate(self, value: Any) -> None:
        if not isinstance(value, str):
            raise TypeError(f"Expected str, got {type(value).__name__}: {value!r}")
        if self.choices is not None and value not in self.choices:
            raise ValueError(
                f"Value {value!r} not in allowed choices: {list(self.choices)}"
            )


@dataclass(frozen=True)
class BoolParam(Param):
    """Boolean parameter."""

    default: bool = False

    def validate(self, value: Any) -> None:
        if not isinstance(value, bool):
            raise TypeError(f"Expected bool, got {type(value).__name__}: {value!r}")
