"""Tests for trade_md.params."""
from __future__ import annotations

import pytest

from trade_md.params import BoolParam, FloatParam, IntParam, StrParam


class TestIntParam:
    def test_valid(self):
        p = IntParam(default=10, min=1, max=100)
        p.validate(50)

    def test_type_error(self):
        p = IntParam(default=10)
        with pytest.raises(TypeError, match="Expected int"):
            p.validate("not an int")

    def test_bool_rejected(self):
        p = IntParam(default=0)
        with pytest.raises(TypeError, match="Expected int"):
            p.validate(True)

    def test_below_min(self):
        p = IntParam(default=10, min=5)
        with pytest.raises(ValueError, match="below minimum"):
            p.validate(2)

    def test_above_max(self):
        p = IntParam(default=10, max=20)
        with pytest.raises(ValueError, match="above maximum"):
            p.validate(30)

    def test_no_bounds(self):
        p = IntParam(default=0)
        p.validate(-999)
        p.validate(999)


class TestFloatParam:
    def test_valid(self):
        p = FloatParam(default=0.5, min=0.0, max=1.0)
        p.validate(0.5)

    def test_int_accepted(self):
        p = FloatParam(default=0.5, min=0.0, max=1.0)
        p.validate(1)  # int is acceptable as float

    def test_type_error(self):
        p = FloatParam(default=0.5)
        with pytest.raises(TypeError, match="Expected float"):
            p.validate("nope")

    def test_below_min(self):
        p = FloatParam(default=0.5, min=0.0)
        with pytest.raises(ValueError, match="below minimum"):
            p.validate(-0.1)

    def test_above_max(self):
        p = FloatParam(default=0.5, max=1.0)
        with pytest.raises(ValueError, match="above maximum"):
            p.validate(1.5)


class TestStrParam:
    def test_valid(self):
        p = StrParam(default="a", choices=["a", "b", "c"])
        p.validate("b")

    def test_type_error(self):
        p = StrParam(default="a")
        with pytest.raises(TypeError, match="Expected str"):
            p.validate(42)

    def test_invalid_choice(self):
        p = StrParam(default="a", choices=["a", "b"])
        with pytest.raises(ValueError, match="not in allowed choices"):
            p.validate("z")

    def test_no_choices(self):
        p = StrParam(default="x")
        p.validate("anything")


class TestBoolParam:
    def test_valid(self):
        p = BoolParam(default=False)
        p.validate(True)
        p.validate(False)

    def test_type_error(self):
        p = BoolParam(default=False)
        with pytest.raises(TypeError, match="Expected bool"):
            p.validate(1)
