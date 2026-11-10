"""CALI-122 (#137 item 1) — a part's own rules, measured on the version it is now, each with its one verdict.

Theo's bar stool v7 broke his locked ``shell_wall_thickness: min_wall >= 3.0 - 0.15`` (0.25 mm webs between the
cone's openings), and the part card listed *Rules on this part* with no mark at all while *Design checks* said "Nothing
to measure yet": only an old chat line and the history's "failing" showed it. Each rule is measured here on the part
as built now, through :mod:`verdicts` (no hand-made ✓), and says what it measured, in the design's units, and where
for a wall.

Measured once per version (and rule text, and where the part sits), in memory: a page load doesn't measure again or write to the design.
"""

from __future__ import annotations

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


def _plain(rule_id: str) -> str:
    return rule_id.replace("_", " ")


def _said(r: dict, where: Optional[list], inches: bool) -> str:
    """One rule's result in words: "shell_wall_thickness: its walls are 0.25 mm around z 16.1 in; it says at least
    2.85 mm"."""
    from .answers import _len, _wall

    if _is_wall(r["expr"]) and isinstance(r.get("actual"), (int, float)):
        need = _wall_needs(r["expr"])
        at = f" around z {_len(where[2], inches)}" if where else ""
        return (f"{_plain(r['id'])}: its thinnest walls are {_wall(float(r['actual']))}{at}"
                + (f"; it says at least {round(need, 2):g} mm" if need is not None else f" ({r['expr']})"))
    if r.get("status") in ("error", "deferred") and r.get("detail"):
        return f"{_plain(r['id'])}: {r['expr']}, not measured: {r['detail']}"
    act = r.get("actual")
    return f"{_plain(r['id'])}: {r['expr']}" + (f", measured {act:g}" if isinstance(act, float) else
                                        f", measured {act}" if act is not None and not isinstance(act, bool) else "")


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
        return [{**r, "status": "error", "verdict": verdicts.check("fail"), "said": f"{r['id']}: not measured ({e})"}
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
