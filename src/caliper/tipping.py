"""CALI-98 (#86) — will it tip over? Statics, not FEA.

A bar stool that holds can still go over. For each stability case a part declares (a load with ``"tip": True``,
which the FEA leaves out), take moments about the edge of its footprint it would tip over:

- **restoring:** the part's own weight at its centre of gravity, and the case's downward push where it acts, each
  times its distance inside that edge;
- **overturning:** the case's sideways push times its height above the floor (and a downward push outside the edge).

It holds when the restoring moment beats the overturning one by the case's factor, as :func:`verdicts.meets` says
(one verdict, #132): a case that can't be checked is waiting, never a pass. The footprint is the convex hull
of where the part meets the floor; the edge is the hull's side the push points across.

The cases to declare, and their values, are in the designer's guide (``part_scripts.md``): EN 1022:2005/2018 and
BIFMA X5.1's seating stability (600 N placed 60 mm in from the seat's edge, plus 20 N sideways at seat height), as the
engineering brief on #42 (section 2) cites them. NEEDS ENGINEER CHECK: the values and the factor (#42).
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from . import construction as C
from . import verdicts
from .design import DesignStore

LB = 4.4482216152605          # N in a pound-force
GRAVITY = 9.80665
#: What each tipping line says of its push, on the line itself (#141 review): where the guide's pushes come from,
#: and that nobody has checked them.
CAVEAT = "EN 1022's push as our brief cites it; not yet checked by an engineer"
#: What the card said under the tipping lines, before the caveat went on each line.
NOTE = ("The guide's tipping pushes are EN 1022 / BIFMA X5.1's, as Caliper's engineering brief cites them: not yet "
        "checked by an engineer.")


def footprint(mesh, tol: float = 1.0) -> np.ndarray:
    """Where the part meets the floor, as a convex polygon (x, y), counter-clockwise: the hull of every vertex within
    ``tol`` mm of its lowest point."""
    from scipy.spatial import ConvexHull

    v = np.asarray(mesh.vertices, float)
    low = v[v[:, 2] <= v[:, 2].min() + tol][:, :2]
    if len(np.unique(low.round(3), axis=0)) < 3:
        raise ValueError("it doesn't stand on the floor on more than a line, so it has no base to tip about")
    hull = ConvexHull(low)
    return low[hull.vertices]


def moments(polygon: np.ndarray, weights: list[tuple[float, np.ndarray]], push: float, push_dir: np.ndarray,
            push_z: float, floor_z: float = 0.0) -> dict:
    """Moments about the footprint's edge a horizontal ``push`` (N, along unit ``push_dir``) at ``push_z`` tips it
    over. ``weights``: (N downward, (x, y)) each. Returns restoring and overturning moments (N·mm), their ratio, and
    the push it would take to tip it (N)."""
    d = np.asarray(push_dir, float)[:2]
    d = d / np.linalg.norm(d)
    edge = float(np.max(polygon @ d))                       # the support line it tips about
    restoring = overturning = 0.0
    for w, at in weights:
        arm = edge - float(np.asarray(at, float)[:2] @ d)    # inside the edge: restoring; outside: overturning
        if arm >= 0:
            restoring += w * arm
        else:
            overturning += w * -arm
    lever = max(push_z - floor_z, 0.0)
    overturning_push = push * lever
    total = overturning + overturning_push
    return {"restoring_nmm": round(restoring, 1), "overturning_nmm": round(total, 1),
            "safety": round(restoring / total, 2) if total > 0 else None,
            # the sideways push that would tip it: none at all when the downward loads alone already do
            "tips_at_n": max(round((restoring - overturning) / lever, 1), 0.0) if lever > 0 else None,
            "edge_mm": round(edge, 1)}


def check(store: DesignStore, part_id: str) -> list[dict]:
    """Each declared stability case, checked: ``[{name, safety, factor, verdict, tips_at_lb, why}]``. [] when the
    part declares none. A case that can't be checked (no weight, no base) says why, and is waiting: never a pass."""
    from .load_study import parse_loads

    d = C.declared(store, part_id)
    cases = [ld for ld in (d.get("loads") or []) if isinstance(ld, dict) and ld.get("tip")]
    if not cases:
        return []
    out = []
    try:
        mesh = store.part_geometry(part_id).require_mesh()
        poly = footprint(mesh)
        rep = C.report(store, part_id)
        if rep.get("mass_kg") is None or rep.get("cog") is None:
            raise ValueError(rep.get("unweighed") or "its weight isn't known")
        own = (float(rep["mass_kg"]) * GRAVITY, np.asarray(rep["cog"], float))
        floor = float(mesh.bounds[0][2])
    except Exception as e:  # noqa: BLE001 — every case says it wasn't checked, and why; none holds
        return [{"name": c.get("name", "a tipping case"), "safety": None, "checked": False,
                 "factor": float(c.get("factor", 1.0)), "verdict": verdicts.meets(None, None),
                 "why": f"not checked: {e}"} for c in cases]
    for case, ld in zip(cases, parse_loads(cases)):
        f = np.asarray(ld["force"], float)
        at = (np.asarray(ld["lo"], float) + np.asarray(ld["hi"], float)) / 2
        side = f[:2]
        if not np.linalg.norm(side):
            out.append({"name": ld["name"], "safety": None, "checked": False, "factor": ld["factor"],
                        "verdict": verdicts.meets(None, None), "why": "not checked: a tipping case pushes sideways (a force with x or y), and this one doesn't"})
            continue
        m = moments(poly, [own, (max(-float(f[2]), 0.0), at)], float(np.linalg.norm(side)), side, float(at[2]), floor)
        # pushed only straight down inside its base, nothing overturns it: safety None, said as no number to hold
        out.append({"name": ld["name"], "factor": ld["factor"], "checked": True, **m,
                    "verdict": verdicts.meets(m["safety"], ld["factor"], close=False),
                    "tips_at_lb": round(m["tips_at_n"] / LB) if m["tips_at_n"] is not None else None,
                    "own_lb": round(own[0] / LB, 1)})
    return out


def line(case: dict) -> tuple[str, str]:
    """The card's words for one case, and its status, as its verdict says: "Won't tip when someone leans back, 1.6
    times over"."""
    name, v = case["name"][:1].lower() + case["name"][1:], case["verdict"]
    if v["kind"] == "waiting":
        return f"Tipping {name}: {case.get('why') or 'not checked'}.", v["status"]
    if v["kind"] in ("holds", "close"):
        return f"Won't tip {name}, {case['safety']:g} times over ({CAVEAT}).", v["status"]
    return (f"Tips {name}: only {case['safety']:g} times over, and it needs {case['factor']:g} ({CAVEAT})"
            + (f"; it goes over at about {case['tips_at_lb']} lb sideways." if case.get("tips_at_lb")
               else "; the load alone tips it, before any push." if case.get("tips_at_lb") == 0 else "."), v["status"])


def undeclared_ways(store: DesignStore, part_id: str) -> list[str]:
    """The ways it could tip that no declared case pushes, where its base is as narrow or narrower that way (#141
    review): a bar stool on a square base, pushed only forward, isn't checked sideways. "tipping sideways" (across x),
    "tipping front to back" (across y); [] when it declares none, or every way that matters."""
    d = C.declared(store, part_id)
    cases = [ld for ld in (d.get("loads") or []) if isinstance(ld, dict) and ld.get("tip")]
    if not cases:
        return []
    try:
        poly = footprint(store.part_geometry(part_id).require_mesh())
    except Exception:  # noqa: BLE001 — no base: each case already says it wasn't checked
        return []
    wide = np.ptp(poly, axis=0)                                    # the base's width across x, and across y
    ways = []
    for ld in cases:
        side = np.asarray(ld.get("force") or (0, 0, 0), float)[:2]
        if np.linalg.norm(side):
            ways.append(side / np.linalg.norm(side))
    on_x = any(abs(w[0]) >= 0.7 for w in ways)
    on_y = any(abs(w[1]) >= 0.7 for w in ways)
    out = []
    if on_y and not on_x and wide[0] <= wide[1] + 1.0:
        out.append("tipping sideways")
    if on_x and not on_y and wide[1] <= wide[0] + 1.0:
        out.append("tipping front to back")
    return out


def unchecked(declared: dict, intent: str, cases: Optional[list] = None) -> list[str]:
    """For a seat (stool, chair, bench), the cases it doesn't declare, in words (#86 item 3): what nobody checked."""
    words = f"{intent} " + " ".join(str(ld.get("name", "")) for ld in declared.get("loads") or [] if isinstance(ld, dict))
    # a step stool is stood on, not sat on: its cases are a step's (the guide's table), not a seat's
    words = words.lower().replace("step stool", "step").replace("step-stool", "step")
    if not any(k in words for k in ("stool", "chair", "bench", "seat", "sit")):
        return []
    loads = [ld for ld in declared.get("loads") or [] if isinstance(ld, dict)]
    side = [ld for ld in loads if not ld.get("tip") and isinstance(ld.get("force"), (list, tuple))
            and len(ld["force"]) == 3 and any(abs(float(v)) > 0 for v in ld["force"][:2])]
    out = []
    if not side:
        out.append("leaning back (a sideways push at seat height)")
    # a strength case on the front edge: a tipping case that sits on it checks it doesn't tip, not that it holds
    if not any("edge" in str(ld.get("name", "")).lower() for ld in loads if not ld.get("tip")):
        out.append("sitting on the front edge")
    if not any(ld.get("tip") for ld in loads):
        out.append("tipping over")
    out.append("buckling of the legs")            # nothing checks it yet (#70 #5)
    return out
