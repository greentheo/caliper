"""The glue and screws a wooden part needs: its joints found from its pieces, then sized for a shopping list.

A plywood box is held together by what's between its panels, and a shopping list without it sends someone
back to the store. Joints come from the pieces themselves: wherever one wood panel's edge sits against
another's face or edge (the same probes the strength check uses to see what holds a panel), each pair of
pieces counted once, along the longer of the two contacts. Then:

- **screws** one every 6 in along each joint, at least two a joint, #8, about 1.6× the panel thickness long,
  to the next 1/4 in;
- **wood glue** about 1/2 ml an inch of joint (an 8 oz bottle does about 40 ft).

It's an estimate for buying, said as one; the build book says where they go.
"""

from __future__ import annotations

import math

import numpy as np

IN = 25.4
SCREW_EVERY_IN = 6.0
GLUE_ML_PER_IN = 0.5
WOOD = ("plywood", "lumber")


def joints(pieces: list[dict], tol: float) -> dict:
    """``{(a, b): mm}``: the length of contact between each pair of wood pieces that touch."""
    from .consistency import _frame, segment_distance, slab_distance

    wood = [pc for pc in pieces if pc.get("material") in WOOD]
    contact: dict = {}
    for i, pc in enumerate(wood):
        if pc["kind"] != "sheet":
            continue
        for k, poly in enumerate(pc["polys"]):
            side, t = pc["sides"][k], pc["thickness"]
            o, u, v, n, flat = _frame(poly)
            centre = poly.mean(axis=0)
            for e in range(len(poly)):
                p, q = poly[e], poly[(e + 1) % len(poly)]
                mid, length = (p + q) / 2, float(np.linalg.norm(q - p))
                inward = centre - mid
                inward -= (inward @ n) * n
                inward /= np.linalg.norm(inward) or 1.0
                probes = np.array([mid - inward * 2 * tol + side * n * t / 2,          # beside the edge
                                   mid + inward * t / 2 + side * n * (t + 2 * tol)])   # just under it
                for j, other in enumerate(wood):
                    if j == i:
                        continue
                    if other["kind"] == "sheet":
                        d = min(slab_distance(probes, op, other["thickness"], s).min()
                                for op, s in zip(other["polys"], other["sides"]))
                    else:
                        d = float((segment_distance(probes, other["a"], other["b"]) - other["half"]).min())
                    if d <= tol:
                        key = tuple(sorted((pc["name"], other["name"])))
                        mine = contact.setdefault(key, {})
                        mine[pc["name"]] = mine.get(pc["name"], 0.0) + length
    return {key: max(by.values()) for key, by in contact.items()}


def estimate(pieces: list[dict], tol: float) -> dict:
    """What holds the wood together, for the shopping list: ``{}`` if nothing wooden touches."""
    found = joints(pieces, tol)
    if not found:
        return {}
    total_in = sum(found.values()) / IN
    screws = sum(max(2, math.ceil(mm / IN / SCREW_EVERY_IN)) for mm in found.values())
    thick = max((pc["thickness"] for pc in pieces if pc.get("kind") == "sheet" and pc.get("material") in WOOD),
                default=19.05)
    length_in = math.ceil(thick / IN * 1.6 * 4) / 4
    from .materials import nominal

    glue_ml = total_in * GLUE_ML_PER_IN
    return {"joints": len(found), "joint_in": round(total_in, 1), "screws": screws,
            "screw": f"#8 × {nominal(length_in * IN)} wood screws", "glue_ml": round(glue_ml),
            "glue": "an 8 oz bottle of wood glue" if glue_ml <= 236 else f"{math.ceil(glue_ml / 473)} × 16 oz wood glue",
            "basis": f"a screw every {SCREW_EVERY_IN:g} in along {len(found)} joints ({total_in:.0f} in), glue "
                     f"~{GLUE_ML_PER_IN} ml an inch"}
