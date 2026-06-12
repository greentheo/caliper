"""CALI-3 — the evaluator.

Each assertion ``expr`` is a predicate over measurement outputs (design spec §3/§5). The evaluator
turns it into a structured ``{id, pass, actual, margin}`` result — the agent's input — not a blind
boolean and certainly not a render.

Two design points:
- **Safety.** Expressions are evaluated by a small AST interpreter with a restricted namespace, not
  by Python ``eval``. Only the measurement names/helpers we bind are reachable.
- **Margin.** Where an assertion is a comparison (``a <= b``), we report the signed distance to the
  threshold (``b - a`` for ``<=``): positive = passing slack, negative = how far short. Compound
  ``and`` reports the binding (minimum) margin. This is what makes failure reports actionable.

Deferred measurements (e.g. ``interference`` until M3) raise ``NotImplementedError``; the evaluator
records those assertions as ``deferred`` and excludes them from ``all_pass`` rather than failing.
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Optional

from . import measure
from .measure import Geometry
from .spec import Spec

# Default machine stub (design spec §7 — profiles are deferred; nozzle is all the MVP needs).
DEFAULT_MACHINE = SimpleNamespace(name="generic", nozzle=0.4, bed=[220, 220, 250])


# ---------------------------------------------------------------------------
# Safe AST interpreter
# ---------------------------------------------------------------------------
_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_CMPOPS = {
    ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
    ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne,
}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}


class SafeEvalError(Exception):
    pass


def _eval(node: ast.AST, ctx: dict) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, ctx)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in ctx:
            raise SafeEvalError(f"unknown name {node.id!r}")
        return ctx[node.id]
    if isinstance(node, ast.Attribute):
        return getattr(_eval(node.value, ctx), node.attr)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left, ctx), _eval(node.right, ctx))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand, ctx))
    if isinstance(node, ast.BoolOp):
        vals = [_eval(v, ctx) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(vals)
        return any(vals)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, ctx)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval(comp, ctx)
            if type(op) not in _CMPOPS or not _CMPOPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        func = _eval(node.func, ctx)
        args = [_eval(a, ctx) for a in node.args]
        kwargs = {kw.arg: _eval(kw.value, ctx) for kw in node.keywords}
        return func(*args, **kwargs)
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval(e, ctx) for e in node.elts]
    raise SafeEvalError(f"unsupported expression node: {type(node).__name__}")


def safe_eval(expr: str, ctx: dict) -> Any:
    return _eval(ast.parse(expr, mode="eval"), ctx)


# ---------------------------------------------------------------------------
# Margin extraction
# ---------------------------------------------------------------------------
def _margin(node: ast.AST, ctx: dict) -> tuple[Optional[float], Any]:
    """Return (signed_margin, actual) for an assertion AST, or (None, value) if not a comparison."""
    if isinstance(node, ast.Expression):
        return _margin(node.body, ctx)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        margins, actuals = [], []
        for v in node.values:
            mg, act = _margin(v, ctx)
            margins.append(mg)
            actuals.append(act)
        present = [m for m in margins if m is not None]
        return (min(present) if present else None), actuals
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        lhs = _eval(node.left, ctx)
        rhs = _eval(node.comparators[0], ctx)
        op = type(node.ops[0])
        if op in (ast.LtE, ast.Lt):
            return float(rhs - lhs), lhs
        if op in (ast.GtE, ast.Gt):
            return float(lhs - rhs), lhs
        if op is ast.Eq:
            return -abs(float(lhs - rhs)), lhs
        if op is ast.NotEq:
            return abs(float(lhs - rhs)), lhs
    # bare bool / call / non-comparison
    return None, _eval(node, ctx)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
@dataclass
class AssertionResult:
    id: str
    expr: str
    status: str  # "pass" | "fail" | "deferred" | "error"
    passed: Optional[bool]
    actual: Any = None
    margin: Optional[float] = None
    detail: str = ""

    @property
    def symbol(self) -> str:
        return {"pass": "✓", "fail": "✗", "deferred": "·", "error": "!"}[self.status]

    def to_dict(self) -> dict:
        def _j(v):
            if isinstance(v, float):
                return round(v, 4)
            if isinstance(v, list):
                return [_j(x) for x in v]
            return v

        return {
            "id": self.id, "expr": self.expr, "status": self.status, "passed": self.passed,
            "actual": _j(self.actual), "margin": _j(self.margin), "detail": self.detail,
            "symbol": self.symbol,
        }


@dataclass
class Report:
    results: list[AssertionResult] = field(default_factory=list)

    @property
    def all_pass(self) -> bool:
        considered = [r for r in self.results if r.status in ("pass", "fail", "error")]
        return bool(considered) and all(r.status == "pass" for r in considered)

    @property
    def failures(self) -> list[AssertionResult]:
        return [r for r in self.results if r.status in ("fail", "error")]

    def to_dict(self) -> dict:
        return {"all_pass": self.all_pass, "results": [r.to_dict() for r in self.results]}

    def to_text(self) -> str:
        lines = []
        for r in self.results:
            m = "" if r.margin is None else f"  (margin {r.margin:+.3g})"
            act = "" if r.actual is None else f"  actual={_fmt(r.actual)}"
            extra = f"  {r.detail}" if r.detail else ""
            lines.append(f"  {r.symbol} {r.id:<16} {r.expr}{act}{m}{extra}")
        verdict = "ALL PASS" if self.all_pass else "FAILURES"
        return f"Measurement report — {verdict}\n" + "\n".join(lines)


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.3g}"
    if isinstance(v, list):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    return str(v)


# ---------------------------------------------------------------------------
# Context + evaluation
# ---------------------------------------------------------------------------
def load_references(spec: Spec, base_dir: str = ".") -> dict[str, Geometry]:
    """Load every reference STL named in ``spec`` into a :class:`Geometry` keyed by reference id.

    Relative ``file`` paths resolve against ``base_dir``. These geometries are what bind the
    ``interference`` / ``min_clearance`` probes to real imported parts (CALI-10).
    """
    import os

    refs: dict[str, Geometry] = {}
    for ref in spec.references:
        path = ref.file if os.path.isabs(ref.file) else os.path.join(base_dir, ref.file)
        refs[ref.id] = Geometry.from_stl(path)
    return refs


def build_context(
    spec: Spec,
    g: Geometry,
    machine: SimpleNamespace = DEFAULT_MACHINE,
    references: Optional[dict] = None,
) -> dict:
    """Bind the measurement names/helpers an assertion can reference, against this geometry.

    Scalars are computed lazily via attribute access on a namespace object so we don't measure what
    nothing asserts (design spec §5). Callables (mass, holes_matching, interference…) defer the
    actual measurement until the expression calls them. ``references`` maps reference id → loaded
    :class:`Geometry`; a referenced id without a loaded geometry resolves to an opaque handle (so
    ``interference``/``min_clearance`` over it surface as an actionable error, not a silent pass).
    """
    references = references or {}
    ctx: dict[str, Any] = {
        "bbox": measure.bounding_box(g),
        "machine": machine,
        # callables — measured on demand
        "mass": lambda density: measure.mass(g, density),
        "holes_matching": lambda diameter, on=None, count=None, tol=0.3: measure.holes_matching(
            g, diameter, on=on, count=count, tol=tol
        ),
        "circle": measure.circle,
        "interference": lambda ref: measure.interference(g, ref),
        "min_clearance": lambda ref: measure.min_clearance(g, ref),
        "mates": lambda ref, tol=0.2: measure.mates(g, ref, tol=tol),
    }
    # scalar measurements bound as values (cheap enough for the MVP subset)
    ctx["body_count"] = measure.body_count(g)
    ctx["is_watertight"] = measure.is_watertight(g)
    ctx["is_manifold"] = measure.is_manifold(g)
    ctx["volume"] = measure.volume(g)
    ctx["min_wall"] = measure.min_wall_thickness(g)
    ctx["largest_through_bore"] = measure.largest_through_bore(g)
    # reference parts resolve to loaded geometry (for interference/min_clearance); opaque otherwise.
    for ref in spec.references:
        ctx[ref.id] = references.get(ref.id) or SimpleNamespace(
            id=ref.id, file=ref.file, role=ref.role
        )
    return ctx


def evaluate_assertion(assertion, ctx: dict) -> AssertionResult:
    try:
        tree = ast.parse(assertion.expr, mode="eval")
        passed = bool(_eval(tree, ctx))
        margin, actual = _margin(tree, ctx)
        return AssertionResult(
            id=assertion.id, expr=assertion.expr,
            status="pass" if passed else "fail",
            passed=passed, actual=actual, margin=margin,
        )
    except NotImplementedError as e:
        return AssertionResult(assertion.id, assertion.expr, "deferred", None, detail=str(e))
    except Exception as e:  # noqa: BLE001 — surface any eval/measure failure as a structured error
        return AssertionResult(
            assertion.id, assertion.expr, "error", None,
            detail=f"{type(e).__name__}: {e}",
        )


def evaluate(
    spec: Spec,
    g: Geometry,
    machine: SimpleNamespace = DEFAULT_MACHINE,
    references: Optional[dict] = None,
) -> Report:
    """Evaluate every assertion in ``spec`` against geometry ``g`` → a :class:`Report`."""
    ctx = build_context(spec, g, machine, references=references)
    return Report([evaluate_assertion(a, ctx) for a in spec.assertions])
