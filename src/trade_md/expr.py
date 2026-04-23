"""TRADE.md expression DSL.

Parses condition expressions like `rsi(14) < 30 and close > ema(200)` and
compiles them into (a) a pandas boolean mask expression using dataframe
columns, and (b) a set of indicator computations that must be precomputed
in `populate_indicators`.

Pipeline
--------
1. Substitute `{token}` references with their declared expression.
2. Preprocess `@<tf>` informative syntax into `_htf(expr, "tf")` calls.
3. `ast.parse` in eval mode.
4. Walk the tree, collecting indicator uses and rewriting the tree to
   reference precomputed dataframe columns.
5. Unparse back to a Python string suitable for use inside a
   `dataframe.loc[<mask>]` boolean mask.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .indicator import IndicatorMetadata

# ---------- Built-in indicator registry ----------------------------------

# Maps DSL indicator name -> TA-Lib function name (used by talib.abstract).
# Each entry also notes whether it's a "scalar" indicator (single output
# column) or a named output (needs .column_name).
BUILTIN_INDICATORS: dict[str, dict[str, Any]] = {
    "rsi": {"talib": "RSI", "outputs": ["rsi"]},
    "ema": {"talib": "EMA", "outputs": ["ema"]},
    "sma": {"talib": "SMA", "outputs": ["sma"]},
    "atr": {"talib": "ATR", "outputs": ["atr"]},
    "adx": {"talib": "ADX", "outputs": ["adx"]},
    "macd": {"talib": "MACD", "outputs": ["macd"], "output_key": "macd"},
    "macd_signal": {"talib": "MACD", "outputs": ["macd_signal"], "output_key": "macdsignal"},
    "macd_hist": {"talib": "MACD", "outputs": ["macd_hist"], "output_key": "macdhist"},
    "bb_upper": {"talib": "BBANDS", "outputs": ["bb_upper"], "output_key": "upperband"},
    "bb_lower": {"talib": "BBANDS", "outputs": ["bb_lower"], "output_key": "lowerband"},
    "bb_middle": {"talib": "BBANDS", "outputs": ["bb_middle"], "output_key": "middleband"},
    "stoch_k": {"talib": "STOCH", "outputs": ["stoch_k"], "output_key": "slowk"},
    "stoch_d": {"talib": "STOCH", "outputs": ["stoch_d"], "output_key": "slowd"},
}

OHLCV_NAMES = {"open", "high", "low", "close", "volume", "hl2", "hlc3", "ohlc4"}

ROLLING_AGGS = {"mean": "mean", "std": "std", "max": "max", "min": "min", "sum": "sum"}

# ---------- Data classes --------------------------------------------------


@dataclass(frozen=True)
class IndicatorUse:
    """A single indicator computation that must be precomputed.

    `col` is the dataframe column name assigned. `timeframe` is None for the
    primary timeframe, or a string like "1h" for informative.
    """
    col: str
    kind: str           # "builtin", "rolling", "shift", "pct_change", "ohlcv"
    name: str           # indicator name, e.g. "rsi"
    args: tuple[Any, ...]
    timeframe: str | None
    # For rolling/shift, this is the base column it operates on.
    base_col: str | None = None
    base_use: IndicatorUse | None = None


@dataclass
class CompiledExpr:
    """Result of compiling one condition expression."""
    mask_expr: str                        # Python expression string for the mask
    uses: list[IndicatorUse] = field(default_factory=list)
    timeframes: set[str] = field(default_factory=set)  # informative TFs touched


# ---------- Preprocessing -------------------------------------------------

# Match `<func-or-name>@<tf>` and rewrite to `_htf(<func-or-name>, "<tf>")`.
# <tf> is a simple minutes/hours/days token like 5m, 1h, 4h, 1d.
_HTF_RE = re.compile(r"(\w+(?:\([^()]*\))?)@(\d+[mhd])")
_TOKEN_REF_RE = re.compile(r"\{(\w+)\}")


def substitute_tokens(expr: str, indicators: dict[str, Any]) -> str:
    """Recursively substitute `{token}` references with their expressions.

    Raises on unknown tokens; cycle detection prevents infinite recursion.
    """
    seen: set[str] = set()

    def _sub(s: str) -> str:
        def replace(m: re.Match) -> str:
            name = m.group(1)
            if name in seen:
                raise ValueError(f"Circular token reference: {name}")
            if name not in indicators:
                raise ValueError(f"Unknown indicator token: {{{name}}}")
            seen.add(name)
            ind_val = indicators[name]
            inner = ind_val if isinstance(ind_val, str) else (ind_val or {}).get("expr", "")
            result = _sub(inner)
            seen.discard(name)
            return f"({result})"

        return _TOKEN_REF_RE.sub(replace, s)

    return _sub(expr)


def preprocess_htf(expr: str) -> str:
    """Rewrite `rsi(14)@1h` → `_htf(rsi(14), "1h")`."""
    prev = None
    cur = expr
    # Iterate until stable — nested @tf uses are rare but keep this safe.
    while cur != prev:
        prev = cur
        cur = _HTF_RE.sub(r'_htf(\1, "\2")', cur)
    return cur


# ---------- Compiler ------------------------------------------------------


class _ExprCompiler(ast.NodeTransformer):
    """Walks an expression AST, collecting IndicatorUses and rewriting nodes
    to reference precomputed dataframe columns.

    After transformation, every surviving node is either:
      - a `Subscript` on `dataframe['col']`
      - a constant / comparison / BoolOp / BinOp / UnaryOp
    """

    def __init__(
        self,
        df_name: str = "dataframe",
        custom_indicators: dict[str, IndicatorMetadata] | None = None,
    ):
        self.df_name = df_name
        self.uses: list[IndicatorUse] = []
        self._seen_cols: set[str] = set()
        self.timeframes: set[str] = set()
        self._custom_indicators = custom_indicators or {}

    # ---- helpers ----

    def _df_col(self, col: str) -> ast.Subscript:
        """Build `dataframe['col']`."""
        return ast.Subscript(
            value=ast.Name(id=self.df_name, ctx=ast.Load()),
            slice=ast.Constant(value=col),
            ctx=ast.Load(),
        )

    def _register_use(self, use: IndicatorUse) -> None:
        if use.col not in self._seen_cols:
            self._seen_cols.add(use.col)
            self.uses.append(use)

    @staticmethod
    def _col_suffix_for_tf(tf: str | None) -> str:
        return f"_{tf}" if tf else ""

    # ---- node handlers ----

    def _handle_htf(self, node: ast.Call) -> ast.AST:
        """Handle `_htf(inner_expr, "tf")` — the informative-timeframe wrapper."""
        if len(node.args) != 2 or not isinstance(node.args[1], ast.Constant):
            raise ValueError("_htf expects (expr, tf_literal)")
        inner = node.args[0]
        tf = node.args[1].value
        if not isinstance(tf, str):
            raise ValueError("_htf tf argument must be a string literal")
        self.timeframes.add(tf)

        # Process the inner expression with the given timeframe tag.
        return self._lower(inner, timeframe=tf)

    def _lower_ohlcv(self, name: str, timeframe: str | None) -> ast.AST:
        """Lower an OHLCV name reference."""
        col = name + self._col_suffix_for_tf(timeframe)
        if timeframe:
            self._register_use(IndicatorUse(
                col=col, kind="ohlcv", name=name, args=(), timeframe=timeframe,
            ))
        # Primary timeframe OHLCV are already in the dataframe.
        return self._df_col(col)

    def _lower_builtin(self, name: str, call: ast.Call, timeframe: str | None) -> ast.AST:
        """Lower a builtin indicator call, e.g. rsi(14)."""
        spec = BUILTIN_INDICATORS[name]
        args = tuple(_const_value(a) for a in call.args)
        arg_part = "_".join(str(a) for a in args) if args else ""
        base_col = f"{spec['outputs'][0]}" + (f"_{arg_part}" if arg_part else "")
        col = base_col + self._col_suffix_for_tf(timeframe)
        self._register_use(IndicatorUse(
            col=col, kind="builtin", name=name, args=args, timeframe=timeframe,
        ))
        return self._df_col(col)

    def _lower_rolling(self, node: ast.Call, timeframe: str | None) -> ast.AST:
        """Lower `X.rolling(N).AGG()` chains."""
        # Expect structure:  <Call: (<Attribute: (<Call: (<Attribute: X.rolling>(N))>.AGG)> ())>
        agg_attr = node.func
        if not isinstance(agg_attr, ast.Attribute):
            raise ValueError("rolling chain malformed")
        agg_name = agg_attr.attr
        if agg_name not in ROLLING_AGGS:
            raise ValueError(f"Unsupported rolling aggregation: {agg_name}")
        rolling_call = agg_attr.value
        if not (isinstance(rolling_call, ast.Call)
                and isinstance(rolling_call.func, ast.Attribute)
                and rolling_call.func.attr == "rolling"):
            raise ValueError("rolling chain malformed")
        base_node = rolling_call.func.value
        window = _const_value(rolling_call.args[0])

        # Recursively lower the base so we get its column.
        base_lowered = self._lower(base_node, timeframe=timeframe)
        if not (isinstance(base_lowered, ast.Subscript)
                and isinstance(base_lowered.slice, ast.Constant)):
            raise ValueError("rolling() must operate on a column reference")
        base_col = base_lowered.slice.value

        col = f"{base_col}_roll_{window}_{agg_name}"
        self._register_use(IndicatorUse(
            col=col,
            kind="rolling",
            name=agg_name,
            args=(window,),
            timeframe=timeframe,
            base_col=base_col,
        ))
        return self._df_col(col)

    def _lower_shift(self, node: ast.Call, timeframe: str | None) -> ast.AST:
        agg_attr = node.func
        if not isinstance(agg_attr, ast.Attribute):
            raise ValueError("shift chain malformed")
        base_node = agg_attr.value
        n = _const_value(node.args[0]) if node.args else 1
        base_lowered = self._lower(base_node, timeframe=timeframe)
        if not (isinstance(base_lowered, ast.Subscript)
                and isinstance(base_lowered.slice, ast.Constant)):
            raise ValueError("shift() must operate on a column reference")
        base_col = base_lowered.slice.value
        col = f"{base_col}_shift_{n}"
        self._register_use(IndicatorUse(
            col=col, kind="shift", name="shift", args=(n,),
            timeframe=timeframe, base_col=base_col,
        ))
        return self._df_col(col)

    def _lower_pct_change(self, node: ast.Call, timeframe: str | None) -> ast.AST:
        agg_attr = node.func
        if not isinstance(agg_attr, ast.Attribute):
            raise ValueError("pct_change chain malformed")
        base_node = agg_attr.value
        n = _const_value(node.args[0]) if node.args else 1
        base_lowered = self._lower(base_node, timeframe=timeframe)
        if not (isinstance(base_lowered, ast.Subscript)
                and isinstance(base_lowered.slice, ast.Constant)):
            raise ValueError("pct_change() must operate on a column reference")
        base_col = base_lowered.slice.value
        col = f"{base_col}_pctchg_{n}"
        self._register_use(IndicatorUse(
            col=col, kind="pct_change", name="pct_change", args=(n,),
            timeframe=timeframe, base_col=base_col,
        ))
        return self._df_col(col)

    def _lower(self, node: ast.AST, timeframe: str | None = None) -> ast.AST:
        """Recursive lowering with an optional informative timeframe context."""
        # Names → OHLCV or error.
        if isinstance(node, ast.Name):
            if node.id in OHLCV_NAMES:
                return self._lower_ohlcv(node.id, timeframe)
            raise ValueError(f"Unknown identifier in expression: {node.id}")

        # Constants pass through.
        if isinstance(node, ast.Constant):
            return node

        # Comparisons, BoolOps, BinOps, UnaryOps: recurse on children.
        if isinstance(node, ast.Compare):
            node.left = self._lower(node.left, timeframe)
            node.comparators = [self._lower(c, timeframe) for c in node.comparators]
            return node
        if isinstance(node, ast.BoolOp):
            node.values = [self._lower(v, timeframe) for v in node.values]
            # Rewrite BoolOp → bitwise & / | because pandas masks don't support `and`/`or`.
            op_map = {ast.And: ast.BitAnd(), ast.Or: ast.BitOr()}
            new_op = op_map[type(node.op)]
            result = node.values[0]
            for v in node.values[1:]:
                result = ast.BinOp(
                    left=_wrap_parens(result),
                    op=new_op,
                    right=_wrap_parens(v),
                )
            return result
        if isinstance(node, ast.BinOp):
            node.left = self._lower(node.left, timeframe)
            node.right = self._lower(node.right, timeframe)
            return node
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                inner = self._lower(node.operand, timeframe)
                return ast.UnaryOp(op=ast.Invert(), operand=_wrap_parens(inner))
            node.operand = self._lower(node.operand, timeframe)
            return node

        # Calls: _htf wrapper, builtin indicators, rolling/shift/pct_change chains,
        # and sugar functions (crosses_above/below).
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                fname = node.func.id
                if fname == "_htf":
                    return self._handle_htf(node)
                if fname in BUILTIN_INDICATORS:
                    return self._lower_builtin(fname, node, timeframe)
                if fname in self._custom_indicators:
                    return self._lower_custom(fname, node, timeframe)
                if fname == "crosses_above":
                    return self._lower_crosses(node, direction="above", timeframe=timeframe)
                if fname == "crosses_below":
                    return self._lower_crosses(node, direction="below", timeframe=timeframe)
                raise ValueError(f"Unknown function in expression: {fname}")
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ROLLING_AGGS:
                    return self._lower_rolling(node, timeframe)
                if node.func.attr == "shift":
                    return self._lower_shift(node, timeframe)
                if node.func.attr == "pct_change":
                    return self._lower_pct_change(node, timeframe)
                raise ValueError(f"Unsupported method call: .{node.func.attr}()")
            raise ValueError("Unsupported call form")

        raise ValueError(f"Unsupported node type: {type(node).__name__}")

    def _lower_custom(self, name: str, call: ast.Call, timeframe: str | None) -> ast.AST:
        """Lower a custom indicator call, e.g. sep_score(lookback=100)."""
        meta = self._custom_indicators[name]

        # Custom indicators use keyword-only arguments.
        if call.args:
            raise ValueError(
                f"Custom indicator {name!r} requires keyword arguments, "
                f"got {len(call.args)} positional argument(s)"
            )

        # Extract keyword values and validate against declared params.
        kwargs: dict[str, Any] = {}
        for kw in call.keywords:
            if kw.arg is None:
                raise ValueError(f"**kwargs not allowed in custom indicator {name!r}")
            val = _const_value(kw.value)
            kwargs[kw.arg] = val

        # Fill defaults for missing kwargs.
        for pname, param in meta.params.items():
            if pname not in kwargs:
                kwargs[pname] = param.default

        # Validate each value against param constraints.
        for pname, val in kwargs.items():
            if pname not in meta.params:
                raise ValueError(
                    f"Unknown parameter {pname!r} for custom indicator {name!r}. "
                    f"Declared params: {sorted(meta.params.keys())}"
                )
            meta.params[pname].validate(val)

        # Build deterministic column name: <as_name>_<param_short_suffix>[_<tf>]
        col = _custom_col_name(name, kwargs, timeframe)

        self._register_use(IndicatorUse(
            col=col,
            kind="custom",
            name=name,
            args=tuple(sorted(kwargs.items())),
            timeframe=timeframe,
        ))
        return self._df_col(col)

    def _lower_crosses(self, call: ast.Call, direction: str, timeframe: str | None) -> ast.AST:
        """Sugar: crosses_above(a, b) → (a > b) & (a.shift(1) <= b.shift(1)).

        Implemented by emitting a shifted column use and building the compound
        comparison inline.
        """
        if len(call.args) != 2:
            raise ValueError(f"crosses_{direction} expects 2 arguments")
        a = self._lower(call.args[0], timeframe)
        b = self._lower(call.args[1], timeframe)
        # shift(1) of each side
        a_prev = self._shift_lowered(a, 1, timeframe)
        b_prev = self._shift_lowered(b, 1, timeframe)

        if direction == "above":
            cur = ast.Compare(left=a, ops=[ast.Gt()], comparators=[b])
            prev = ast.Compare(left=a_prev, ops=[ast.LtE()], comparators=[b_prev])
        else:
            cur = ast.Compare(left=a, ops=[ast.Lt()], comparators=[b])
            prev = ast.Compare(left=a_prev, ops=[ast.GtE()], comparators=[b_prev])
        return ast.BinOp(
            left=_wrap_parens(cur),
            op=ast.BitAnd(),
            right=_wrap_parens(prev),
        )

    def _shift_lowered(self, lowered: ast.AST, n: int, timeframe: str | None) -> ast.AST:
        """Create a shifted column use from an already-lowered column reference."""
        if not (isinstance(lowered, ast.Subscript) and isinstance(lowered.slice, ast.Constant)):
            raise ValueError("crosses_* arguments must be column references")
        base_col = lowered.slice.value
        col = f"{base_col}_shift_{n}"
        self._register_use(IndicatorUse(
            col=col, kind="shift", name="shift", args=(n,),
            timeframe=timeframe, base_col=base_col,
        ))
        return self._df_col(col)


def _custom_col_name(
    as_name: str, kwargs: dict[str, Any], timeframe: str | None,
) -> str:
    """Build a deterministic column name for a custom indicator call.

    Convention: ``<as_name>_<p1_abbrev><val1>[_<p2_abbrev><val2>][_<tf>]``
    where the abbreviation is the first letter of each param name and
    decimal points are replaced with ``p`` to keep names identifier-safe.
    """
    parts = [as_name]
    for pname in sorted(kwargs.keys()):
        val = kwargs[pname]
        abbrev = pname[0]
        val_str = str(val).replace(".", "p").replace("-", "m")
        parts.append(f"{abbrev}{val_str}")
    if timeframe:
        parts.append(timeframe)
    return "_".join(parts)


def _const_value(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_const_value(node.operand)
    raise ValueError(f"Expected a constant, got {ast.dump(node)}")


def _wrap_parens(node: ast.AST) -> ast.AST:
    """Add a no-op wrapper so unparse emits parentheses for precedence safety."""
    # ast.unparse handles precedence correctly already; this is a hook for
    # future use if we need explicit parenthesization.
    return node


def compile_expression(
    expr: str,
    indicators: dict[str, Any] | None = None,
    df_name: str = "dataframe",
    custom_indicators: dict[str, IndicatorMetadata] | None = None,
) -> CompiledExpr:
    """Compile a single TRADE.md condition into a pandas mask + indicator uses.

    Args:
        expr: The raw condition string from TRADE.md.
        indicators: The ``indicators:`` block for token substitution.
        df_name: Name of the pandas DataFrame variable in the emitted code.
        custom_indicators: ``{as_name: IndicatorMetadata}`` for custom indicator
            resolution (from :meth:`TradeDoc.load_custom_indicators`).
    """
    if indicators is None:
        indicators = {}
    substituted = substitute_tokens(expr, indicators)
    preprocessed = preprocess_htf(substituted)
    try:
        tree = ast.parse(preprocessed, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {expr!r}: {e}") from e

    compiler = _ExprCompiler(df_name=df_name, custom_indicators=custom_indicators)
    lowered = compiler._lower(tree.body)
    mask_expr = ast.unparse(lowered)
    return CompiledExpr(
        mask_expr=mask_expr,
        uses=compiler.uses,
        timeframes=compiler.timeframes,
    )


def compile_conditions(
    conditions: list[str],
    indicators: dict[str, Any] | None = None,
    df_name: str = "dataframe",
    custom_indicators: dict[str, IndicatorMetadata] | None = None,
) -> CompiledExpr:
    """Compile a list of conditions (ANDed together) into a single mask."""
    if not conditions:
        raise ValueError("At least one condition required")
    compiled = [
        compile_expression(c, indicators, df_name, custom_indicators)
        for c in conditions
    ]
    # AND all masks together
    if len(compiled) == 1:
        return compiled[0]
    mask = " & ".join(f"({c.mask_expr})" for c in compiled)
    uses: list[IndicatorUse] = []
    seen: set[str] = set()
    tfs: set[str] = set()
    for c in compiled:
        tfs |= c.timeframes
        for u in c.uses:
            if u.col not in seen:
                seen.add(u.col)
                uses.append(u)
    return CompiledExpr(mask_expr=mask, uses=uses, timeframes=tfs)
