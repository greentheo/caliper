"""CALI-122 (#137 item 1) — a part's own rules, measured on the version it is now, each with its one verdict.

Theo's bar stool v7 broke his locked ``shell_wall_thickness: min_wall >= 3.0 - 0.15`` (0.25 mm webs between the
cone's openings), and the part card listed *Rules on this part* with no mark at all while *Design checks* said "Nothing
to measure yet": only an old chat line and the history's "failing" showed it. Each rule is measured here on the part
as built now, through :mod:`verdicts` (no hand-made ✓), and says what it measured, in the design's units, and where
for a wall.

Measured once per version (and rule text, and where the part sits), in memory: a page load doesn't measure again or write to the design.
"""

from __future__ import annotations

from .errors import scrubbed

import math
import re
from typing import Optional

from . import verdicts
from .design import DesignStore

_SEEN: dict = {}


_WALL = re.compile(r"\s*min_wall\s*>=?\s*(.+)$")


def _is_wall(expr: str) -> bool:
    return bool(_WALL.match(expr))


def _wall_needs(expr: str) -> Optional[float]:
    """The mm a ``min_wall >= …`` rule asks for; None where it can't be worked out (said without it, never guessed)."""
    from .evaluate import DEFAULT_MACHINE, safe_eval

    try:
        return float(safe_eval(_WALL.match(expr).group(1), {"machine": DEFAULT_MACHINE}))
    except Exception:  # noqa: BLE001
        return None


#: A number as a rule writes it: its decimal places are the precision its result is said to (CALI-227, #385).
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.(\d+))?(?![\w.])")


def _const(node) -> Optional[float]:
    """A side of a rule that's only numbers (``3.0 - 0.15``), its value; None where it names anything."""
    import ast

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _const(node.operand)
        return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        a, b = _const(node.left), _const(node.right)
        if a is None or b is None or (isinstance(node.op, ast.Div) and b == 0):
            return None
        return {ast.Add: a + b, ast.Sub: a - b, ast.Mult: a * b, ast.Div: a / b if b else 0.0}[type(node.op)]
    return None


def _bounds(expr: str) -> list[tuple[str, Optional[float]]]:
    """What a rule holds its measure to: ``[("lo" | "hi" | "eq", value)]``, a value None where that side names something
    (``seat_mm >= leg_gap_mm``). [] where it isn't a comparison."""
    import ast

    try:
        node = ast.parse(expr or "", mode="eval").body
    except SyntaxError:
        return []
    if not isinstance(node, ast.Compare):
        return []
    lower = (ast.Gt, ast.GtE)            # measure on the left: x >= lo
    upper = (ast.Lt, ast.LtE)
    if len(node.ops) == 1:
        op, left, right = node.ops[0], node.left, node.comparators[0]
        lv, rv = _const(left), _const(right)
        limit, measure_left = (rv, True) if lv is None else (lv, False)
        if isinstance(op, ast.Eq):
            return [("eq", limit)]
        if isinstance(op, lower):
            return [("lo" if measure_left else "hi", limit)]
        if isinstance(op, upper):
            return [("hi" if measure_left else "lo", limit)]
        return []
    if len(node.ops) == 2:              # a band: lo <= x <= hi, or hi >= x >= lo
        a, b = _const(node.left), _const(node.comparators[1])
        if all(isinstance(o, upper) for o in node.ops):
            return [("lo", a), ("hi", b)]
        if all(isinstance(o, lower) for o in node.ops):
            return [("hi", a), ("lo", b)]
    return []


def cut(actual: float, expr: str, failing: bool = False) -> str:
    """A rule's measured number, to the rule's own precision (the most decimal places among its numbers, at most 3; three
    significant figures where it has none), cut toward safe (CALI-227, #385: "actual=0.22303847515793196").
    - Failing: cut away from the bound it misses, down under a lower one, up over an upper one or an ``==``'s target on
      that side, and never said as one of the rule's own numbers or limits: a place is added until it isn't (#392 review:
      a failing ``== 400`` at 400.4 read "400").
    - Otherwise: down for an "at least", up for an "at most", rounded where it's neither."""
    nums = [m for m in _NUMBER.finditer(expr or "")]
    bounds = _bounds(expr)
    if nums:
        places = min(3, max(len(m.group(1) or "") for m in nums))
    else:                                    # no number in the rule: three significant figures (#392 review)
        places = 0 if actual == 0 else max(0, min(6, 2 - math.floor(math.log10(abs(actual)))))
    down = up = False
    if failing:
        missed = next((k for k, v in bounds if v is not None and ((k == "lo" and actual < v) or (k == "hi" and actual > v)
                                                                  or (k == "eq" and actual != v))), None)
        if missed is not None:
            v = next(v for k, v in bounds if k == missed and v is not None and
                     ((k == "lo" and actual < v) or (k == "hi" and actual > v) or (k == "eq" and actual != v)))
            down, up = (actual < v), (actual > v)
        else:                                # a side that names something: by the comparison's own way round
            down, up = any(k == "lo" for k, _ in bounds), any(k == "hi" for k, _ in bounds)
            down, up = (down and not up), (up and not down)
    else:
        least, most = ">" in (expr or ""), "<" in (expr or "")
        down, up = least and not most, most and not least
    limits = {float(m.group(0)) for m in nums}     # a computed limit is cut away from already, never landed on
    while True:
        f = 10 ** places
        v = math.floor(actual * f + 1e-9) / f if down else math.ceil(actual * f - 1e-9) / f if up else round(actual, places)
        said = f"{v:.{places}f}"
        if not failing or places >= 6 or not any(said == f"{lim:.{places}f}" for lim in limits):
            return said
        places += 1


def _plain(rule_id: str) -> str:
    return rule_id.replace("_", " ")


def _said(r: dict, where: Optional[list], inches: bool) -> str:
    """One rule's result in words: "shell_wall_thickness: its walls are 0.25 mm around z 16.1 in; it says at least
    2.85 mm"."""
    from .answers import _len, _wall

    if _is_wall(r["expr"]) and isinstance(r.get("actual"), (int, float)):
        need = _wall_needs(r["expr"])
        at = f" around z {_len(where[2], inches)}" if where else ""
        return (f"{_plain(r['id'])}: its thinnest walls are {cut(float(r['actual']), r['expr'], r.get('status') == 'fail')} mm{at}"
                + (f"; it says at least {round(need, 2):g} mm" if need is not None else f" ({r['expr']})"))
    if r.get("status") in ("error", "deferred") and r.get("detail"):
        return f"{_plain(r['id'])}: {r['expr']}, not measured: {r['detail']}"
    act = r.get("actual")
    if isinstance(act, (int, float)) and not isinstance(act, bool):   # in words, to its precision (CALI-227)
        return f"{_plain(r['id'])}: it measures {cut(float(act), r['expr'], r.get('status') == 'fail')} ({r['expr']})"
    return f"{_plain(r['id'])}: {r['expr']}" + (f", measured {act}" if act is not None and not isinstance(act, bool) else "")


def measured(store: DesignStore, pid: str, geometry=None) -> list[dict]:
    """``[{id, expr, status, actual, said, verdict}]`` for the part's own rules on its current version; the rules
    unmeasured (``{id, expr}``) where it isn't built or won't build, with why. ``geometry``: the part as built,
    when the caller already has it."""
    from . import evaluate as E
    from . import measure

    spec, entry = store.read_spec(pid), store.design.part(pid)
    rules = list(spec.assertions) if spec else []
    plain = [{"id": a.id, "expr": a.expr} for a in rules]
    if not rules or entry is None or not entry.version:
        return plain
    placed = next((repr((p.position, p.rotation)) for p in store.assembly.parts if p.id == pid), "")   # moved, not new
    key = (store.root, pid, entry.version, tuple(a.expr for a in rules), store.design.display_units, placed)
    if key in _SEEN:
        return _SEEN[key]
    try:
        g = geometry if geometry is not None else store.part_geometry(pid)
        rep = E.evaluate(spec, g, references=E.load_references(spec, store.root))
    except Exception as e:  # noqa: BLE001 — a part that won't build: its rules aren't measured, and say why
        return [{**r, "status": "error", "verdict": verdicts.check("fail"), "said": f"{r['id']}: not measured ({scrubbed(e)})"}
                for r in plain]
    inches = store.design.display_units == "in"
    where = None
    out = []
    for res in rep.results:
        r = res.to_dict()
        if "min_wall" in r["expr"] and r["status"] == "fail" and where is None:
            where = measure.thinnest_wall(g)[1]          # where to thicken it (the same rays, the same seed)
        out.append({**{k: r[k] for k in ("id", "expr", "status", "actual", "detail")},
                    "where": where if "min_wall" in r["expr"] else None,
                    "said": _said(r, where if "min_wall" in r["expr"] else None, inches),
                    # an error is a fail, as verdicts.report reads one (rule 6: never greener than its check)
                    "verdict": verdicts.check("fail" if r["status"] == "error" else r["status"])})
    _SEEN[key] = out
    return out


def failing(rules: list[dict]) -> list[dict]:
    """The measured rules whose verdict is a fail."""
    return [r for r in rules if (r.get("verdict") or {}).get("kind") == "fails"]


def _in_script(store: DesignStore, pid: str, at: list) -> list:
    """A point measured where the part sits in the design, in the coordinates its own script draws in."""
    import numpy as np

    from . import measure

    part = next((p for p in store.assembly.parts if p.id == pid), None)
    if part is None:
        return at
    back = np.linalg.inv(measure.pose_matrix(part.position, part.rotation))
    return [round(float(v), 1) for v in (back @ np.array([*at, 1.0]))[:3]]


def to_fix(store: DesignStore, pid: str, rule_id: str) -> str:
    """What the designer is told about a failing rule it's asked to fix (#158), measured on the version it is now: how
    far off, and for a wall where, in the script's own mm (a design's units and its placing are the person's). "" for a
    rule that's gone or isn't failing. Told to the designer's first round only: it's true of this version, not the part."""
    from .answers import _wall

    r = next((x for x in measured(store, pid) if x["id"] == rule_id), None)
    if r is None or r.get("status") == "pass" or "status" not in r:
        return ""
    if r["status"] != "fail":
        return f" It couldn't be measured just now: {r.get('detail') or r['said']}."
    act = r.get("actual")
    if not _is_wall(r["expr"]):
        return f" Measured on it now: {act:g}." if isinstance(act, float) else f" Measured on it now: {act}."
    if not isinstance(act, (int, float)):
        return f" Measured on it now: {act}."
    need = _wall_needs(r["expr"])
    at = r.get("where")
    return (f" Measured on it now: the thinnest wall is {_wall(float(act))}"
            + (" at x {:g}, y {:g}, z {:g} mm in this script's coordinates".format(*_in_script(store, pid, at))
               if at else "")
            + (f"; the rule needs at least {round(need, 2):g} mm" if need is not None else "")
            + ". min_wall is the thinnest material anywhere in the part, webs between openings included: change what"
              " makes it thin there, and leave walls that are already thick enough.")
