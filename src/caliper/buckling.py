"""CALI-159 (#229) — a hand plate-buckling check for a sheet that carries a load in its own plane.

A wall standing in line with a load is in compression, and a thin one can fold sideways before it reaches its strength.
Neither the FEA (linear, so it never sees a fold) nor the plate check (a top, loaded across its face) checks that.

The critical stress of a flat plate in compression (Timoshenko & Gere, *Theory of Elastic Stability*, 2nd ed., §9.2)::

    σ_cr = k · π² E / (12 (1 − ν²)) · (t / b)²

``b`` is the length of the loaded edges, ``a`` the panel's height along the load, ``t`` its thickness. ``k`` comes from its
edges, each taken on the safe side:

- the loaded edges (top and bottom) are simply supported, never clamped;
- an unloaded edge is simply supported where a piece standing off the wall's plane meets it along its length (a sheet
  across it, or a stick), and free where nothing does. A sheet in the wall's own plane holds nothing: two butted halves
  fold together (#235 review);
- both unloaded edges held: ``k = min over m of (m b/a + a/(m b))²``, 4 for a long plate (Timoshenko eq. 9-7);
- one held, one free: ``k = 0.425 + (b/a)²`` (Timoshenko §9.4; Bulson);
- neither held: it's a wide column. Braced at its top, it's taken as pinned at both ends: Euler's ``π² E t² / (12 a²)``
  (#264). A wall is braced only by a piece found across its top edge (where the load comes in) that's across another
  wall's top too, as a step resting on a stool's two sides is: a top on one lone wall moves with it. That takes its top
  as held square by its joint to that piece, and the joint isn't checked (#265). If it gives, the walls under the piece
  RACK: they lean over together, a parallelogram, each swaying at its share of the load (``sway_safety`` on the row). So a
  pass that rests on a brace reads amber at most, "joints not checked" (:data:`verdicts.JOINT_CAP`). Unbraced, nothing
  stops its top moving sideways, so it sways: fixed at its foot and free at its top, a cantilever of twice its height, a
  quarter of Euler's (:data:`SWAY`; without 1 − ν², the lower).

``E`` is the panel's bending stiffness the weaker way, since which way the grain runs isn't known. For plywood that's
across its face grain, where the outer plies run the wrong way: :data:`PLY_BENDING_ACROSS` of along. Two parallel walls the loaded piece rests on share the case's
factored load by the lever rule, from their mid-planes (#264); a wall under another piece (a divider stopping short of the step)
takes none of it (#265). A load beyond both walls levers: the near wall takes more than all of it (1.29 at a 150 mm overhang on a
400 mm stool), and the far one is lifted, pulled rather than pushed, so it isn't checked for folding. Any other wall in line, or a
load given with no place, takes the whole of it, the safe side. A panel this can't describe (not a rectangle, holes in it, loaded at a slant to its
edges) isn't checked, and says so. NEEDS ENGINEER CHECK (#42): the edge conditions, the sway, the braced top's joint (#222), and E across the grain for plywood.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

#: Poisson's ratio: plywood and most wood-based sheets are near it, and the result moves little with it.
NU = 0.3
#: An edge this close to square with the load is a loaded edge; this close to along it, an unloaded one (cos of the angle).
SQUARE = 0.1
#: A sheet carries a load in its own plane when the load is within this of the plane (as :func:`load_study.buckling_notes`).
IN_PLANE = 0.3
#: A wall held on neither side sways: a cantilever of twice its height buckles at a quarter of Euler's load (#235 review).
SWAY = 0.25
#: Plywood's bending stiffness across its face grain, as a share of along it. The foreman's call until Theo's coupons
#: measure it (#235 review): ply theory gives about 0.09 for a 3-ply sheet and 0.3 for a 5-ply, and buckling goes by
#: bending, so the strength ratio (0.5) isn't it; 0.1 is safe for the thin sheets that buckle.
PLY_BENDING_ACROSS = 0.1
#: Another sheet's plane this far from square to the wall's (|n·n′|) is standing off it, and can hold an edge.
OFF_PLANE = 0.5


def k_factor(a: float, b: float, held: int, braced: bool = False) -> float:
    """The buckling coefficient for loaded edges simply supported, and ``held`` (0, 1 or 2) unloaded edges simply supported, the
    rest free. For ``held == 0`` it's a wide column's, written as a plate's: swaying, ``SWAY (b/a)² (1 − ν²)``, a quarter of
    Euler's; ``braced`` at its top (#264), pinned at both ends, ``(b/a)² (1 − ν²)``, Euler's."""
    r = a / b
    if held >= 2:
        return min((m / r + r / m) ** 2 for m in range(1, max(2, int(r) + 3)))
    if held == 1:
        return 0.425 + (1 / r) ** 2
    return (1.0 if braced else SWAY) * (1 / r) ** 2 * (1 - NU ** 2)


def critical_stress(E: float, t: float, a: float, b: float, held: int, braced: bool = False) -> float:
    """σ_cr in MPa (``E`` in MPa, lengths in mm)."""
    return k_factor(a, b, held, braced) * math.pi ** 2 * E / (12 * (1 - NU ** 2)) * (t / b) ** 2


def weak_E(mat: dict) -> float:
    """The sheet's bending stiffness the weaker way: its own across the face grain where it's given; plywood's (a sheet
    weaker across its grain) :data:`PLY_BENDING_ACROSS` of along; anything else, the same both ways."""
    if mat.get("E_across"):
        across = mat["E_across"] / mat["E"]
    elif mat.get("key") == "plywood" or float(mat.get("across", 1.0)) < 1.0:
        across = PLY_BENDING_ACROSS
    else:
        across = 1.0
    return float(mat["E"]) * min(float(across), 1.0)


def _held(pc: dict, k: int, e: int, pieces: list[dict], tol: float) -> bool:
    """Whether a piece standing off the sheet's plane meets edge ``e`` of its polygon ``k`` along it: probed beside the edge
    and just under it, at its quarter points (as :func:`fasteners.joints` probes a joint), all of them touching. A sheet in
    the same plane (the other half of a butted wall) doesn't count."""
    from .consistency import _frame, segment_distance, slab_distance

    poly, side, t = pc["polys"][k], pc["sides"][k], pc["thickness"]
    n = _frame(poly)[3]
    p, q = poly[e], poly[(e + 1) % len(poly)]
    inward = poly.mean(axis=0) - (p + q) / 2
    inward -= (inward @ n) * n
    inward /= np.linalg.norm(inward) or 1.0
    for s in (0.25, 0.5, 0.75):
        mid = p + s * (q - p)
        probes = np.array([mid - inward * 2 * tol + side * n * t / 2, mid + inward * t / 2 + side * n * (t + 2 * tol)])
        near = np.inf
        for other in pieces:
            if other is pc:
                continue
            if other["kind"] == "sheet":
                near = min([near] + [float(slab_distance(probes, op, other["thickness"], os_).min())
                                     for op, os_ in zip(other["polys"], other["sides"])
                                     if abs(float(_frame(op)[3] @ n)) < OFF_PLANE])
            elif "a" in other:
                near = min(near, float((segment_distance(probes, other["a"], other["b"]) - other.get("half", 0)).min()))
        if near > tol:
            return False
    return True


def check(pieces: list[dict], load: dict, mat: dict, tol: float) -> list[dict]:
    """Each sheet in line with ``load`` (its force within :data:`IN_PLANE` of the sheet's plane): its buckling check, or why it
    isn't checked. ``load["force"]`` is in N, before its factor. A row says what its wall was taken as: ``braced_by`` (the piece
    whose unchecked joint is taken to hold its top square, or None), ``share`` (of the load, by the lever rule), and for a braced
    wall ``sway_safety``, what it reads if that joint gives and it racks (#264, #265)."""
    from .consistency import _frame

    f = np.asarray(load["force"], float) * float(load.get("factor", 1.0))
    size = float(np.linalg.norm(f))
    out, walls = [], []
    if size <= 0:
        return out
    for pc in pieces:
        if pc["kind"] != "sheet":
            continue
        for k, poly in enumerate(pc["polys"]):
            n = _frame(poly)[3]
            if abs(float(n @ f)) >= IN_PLANE * size:
                continue                                   # across its face: the plate check's, not this one's
            d = f - (f @ n) * n
            push = float(np.linalg.norm(d))
            d /= push
            # whether it runs down the sheet: a shove in its plane is taken as a squeeze too, the safe side (#235 review)
            row = {"piece": pc["name"], "load_n": round(push, 1), "down": bool(d[2] < -(1 - SQUARE))}
            why = None
            if len(poly) != 4 or len(pc["polys"]) != 1:
                why = "it isn't a plain rectangle"
            elif pc.get("holes"):
                why = "it has holes in it, and a cut-out changes how it folds"
            if why is None:
                edges = [poly[(e + 1) % 4] - poly[e] for e in range(4)]
                cos = [abs(float(v @ d)) / float(np.linalg.norm(v)) for v in edges]
                if not all(c < SQUARE or c > 1 - SQUARE for c in cos) or sum(c > 1 - SQUARE for c in cos) != 2:
                    why = "the load runs at a slant to its edges"
            if why is not None:
                out.append({**row, "done": False, "why": why})
                continue
            along = [e for e in range(4) if cos[e] > 1 - SQUARE]       # the unloaded edges, along the load
            loaded = [e for e in range(4) if e not in along]
            a = float(np.mean([np.linalg.norm(edges[e]) for e in along]))
            b = float(np.mean([np.linalg.norm(edges[e]) for e in loaded]))
            held = sum(_held(pc, k, e, pieces, tol) for e in along)
            # where the load comes in: the loaded edge furthest up the push. What's across it, piece by piece (#264)
            top = min(loaded, key=lambda e: float((poly[e] + poly[(e + 1) % 4]) @ d))
            across = [o for o in pieces if o is not pc and _held(pc, k, top, [o], tol)]   # what it bears under (#265)
            mid = poly.mean(axis=0) + pc["sides"][k] * n * float(pc["thickness"]) / 2.0     # its mid-plane: where it bears
            walls.append({"row": len(out), "pc": pc, "n": n, "mid": mid, "across": across, "push": push,
                          "a": a, "b": b, "held": held})
            out.append({**row, "done": True, "height_mm": round(a, 1), "width_mm": round(b, 1),
                        "thickness_mm": float(pc["thickness"]), "edges_held": held})
    for w in walls:
        # held square at its top only by a piece found across it that's across another wall's top too: a top on one lone wall
        # turns with it (#235's); a step across two sides can hold them square through its joints to them, which aren't checked
        # (#265: they can rack, leaning together). Found, never assumed (Rule 6)
        w["by"] = (next((o["name"] for o in w["across"] if any(o in v["across"] for v in walls if v is not w)), None)
                   if w["held"] == 0 else None)
    shares, lifted = _shares(walls, load)
    for i, (w, share) in enumerate(zip(walls, shares)):
        r = out[w["row"]]
        if i in lifted:                                   # beyond the load the other way: pulled, not pushed (#265)
            out[w["row"]] = {k_: r[k_] for k_ in ("piece", "load_n", "down")} | {
                "done": False, "why": "the load lifts it here: it's pulled, not pushed, so this load can't fold it"}
            continue
        E, t = weak_E(mat), float(w["pc"]["thickness"])
        braced = w["by"] is not None
        sigma = critical_stress(E, t, w["a"], w["b"], w["held"], braced)
        p_cr = sigma * w["b"] * t
        push = w["push"] * share
        r.update({"braced_by": w["by"], "share": round(share, 3), "load_n": round(push, 1),
                  "k": round(k_factor(w["a"], w["b"], w["held"], braced), 3), "E_mpa": round(E, 1),
                  "sigma_cr_mpa": round(sigma, 3), "p_cr_n": round(p_cr, 1), "safety": p_cr / push})
        if braced:                                        # if its joint gives, it racks: what it reads swaying, the same share
            r["sway_safety"] = critical_stress(E, t, w["a"], w["b"], w["held"]) * w["b"] * t / push
    return out


def _shares(walls: list[dict], load: dict) -> tuple[list[float], set]:
    """Each wall's share of the load (#264, #265), and the walls it lifts. Only between two parallel walls the same piece rests on
    (the one loaded: a step across both): between them, by the lever rule from their mid-planes; beyond both, the near one takes
    the lever rule's share, over 1, and the far one is lifted. Any other wall, or a load with no place, takes the whole of it."""
    out, lifted = [1.0] * len(walls), set()
    if load.get("lo") is None or load.get("hi") is None:
        return out, lifted
    at = (np.asarray(load["lo"], float) + np.asarray(load["hi"], float)) / 2.0
    for i, w in enumerate(walls):
        for j in range(i + 1, len(walls)):
            v = walls[j]
            if abs(float(v["n"] @ w["n"])) < 1 - 1e-3 or not any(o in v["across"] for o in w["across"]):
                continue                                  # not parallel, or not under one piece
            n = w["n"]
            si, sj, s_at = float(w["mid"] @ n), float(v["mid"] @ n), float(at @ n)
            if abs(sj - si) < 1e-9:
                continue
            between = [x for x in range(len(walls)) if x not in (i, j) and abs(float(walls[x]["n"] @ n)) > 1 - 1e-3
                       and any(o in walls[x]["across"] for o in w["across"])
                       and min(si, sj) < float(walls[x]["mid"] @ n) < max(si, sj)]
            if between:                                   # a nearer pair under the same piece decides it
                continue
            fi = (sj - s_at) / (sj - si)                  # the lever rule: each the other's distance from the load
            fj = (s_at - si) / (sj - si)
            for x, f in ((i, fi), (j, fj)):
                if f < 0:
                    lifted.add(x)
                elif out[x] == 1.0 or f > out[x]:
                    out[x] = f
    return out, lifted


def governing(rows: list[dict]) -> Optional[dict]:
    """The weakest wall checked, if any."""
    done = [r for r in rows if r.get("done")]
    return min(done, key=lambda r: r["safety"]) if done else None
