"""The glue and screws a wooden part needs: its joints found from its pieces, then sized for a shopping list.

A plywood box is held together by what's between its panels, and a shopping list without it sends someone
back to the store. Joints come from the pieces themselves: wherever one wood panel's edge sits against
another's face or edge (the same probes the strength check uses to see what holds a panel), each pair of
pieces counted once, along the longer of the two contacts. Then:

- **screws** along each joint, 1 1/2 in from each end and then no more than 6 in apart, as the patterns mark them
  (:mod:`caliper.marks`: none in a glued through tenon), #8, about 1.6× the panel thickness long, to the next 1/4 in;
- **wood glue** about 1/2 ml an inch of joint (an 8 oz bottle does about 40 ft).

It's an estimate for buying, said as one; the build book says where they go.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

IN = 25.4
SCREW_EVERY_IN = 6.0
#: The pilot hole for a #8 wood screw in plywood or softwood: the shop rule of thumb (a hardwood wants 9/64 in).
#: Plywood splits near an edge without one (CALI-88, #64 item 8).
PILOT_BIT = "1/8 in"
GLUE_ML_PER_IN = 0.5
WOOD = ("plywood", "lumber")


def keys(pieces: list[dict]) -> None:
    """Give each piece a ``key`` of its own: its name, or its name and a number when another piece has the same
    name. Joints are between pieces, not names (CALI-87: two pieces both called "side" were one joint to the
    shopping list and two to the kids' book)."""
    seen: dict = {}
    for pc in pieces:
        n = pc.get("name") or pc.get("kind") or "piece"
        seen[n] = seen.get(n, 0) + 1
        pc["key"] = n if seen[n] == 1 else f"{n} #{seen[n]}"


def joints(pieces: list[dict], tol: float) -> dict:
    """``{(a, b): mm}``: the length of contact between each pair of wood pieces that touch, by each piece's ``key``
    (see :func:`keys`, which this sets): an edge on a face, and a piece through or set into another (CALI-156, #222: the
    edge probes alone missed step-stool-5's through-mortised stringer, so the shopping list had no fixings there)."""
    from . import joints as J

    keys(pieces)
    return {k: c["length_mm"] for k, c in J.contacts(pieces, tol).items()}


def edge_joints(pieces: list[dict], tol: float) -> dict:
    """``{(a, b): mm}``: where an edge of one wood sheet meets another piece."""
    from .consistency import _frame, segment_distance, slab_distance

    keys(pieces)
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
                        key = tuple(sorted((pc["key"], other["key"])))
                        mine = contact.setdefault(key, {})
                        mine[pc["key"]] = mine.get(pc["key"], 0.0) + length
    return {key: max(by.values()) for key, by in contact.items()}


def screw_length_mm(pieces: list[dict]) -> float:
    """The screw for a part: about 1.6x its thickest wood sheet, to the next 1/4 in."""
    thick = max((pc["thickness"] for pc in pieces if pc.get("kind") == "sheet" and pc.get("material") in WOOD),
                default=19.05)
    return math.ceil(thick / IN * 1.6 * 4) / 4 * IN


def estimate(pieces: list[dict], tol: float, said: Optional[list] = None) -> dict:
    """What holds the wood together, for the shopping list: ``{}`` if nothing wooden touches. The screws are the ones the
    patterns mark, joint by joint (CALI-177): ``said``, the part's ``JOINTS``, says which are held without them."""
    from . import marks

    found = joints(pieces, tol)
    if not found:
        return {}
    total_in = sum(found.values()) / IN
    screws = sum(c["n"] for c in marks.screws(pieces, tol, said).values())
    length_in = screw_length_mm(pieces) / IN
    from .materials import nominal

    glue_ml = total_in * GLUE_ML_PER_IN
    return {"joints": len(found), "joint_in": round(total_in, 1), "screws": screws,
            "screw": f"#8 × {nominal(length_in * IN)} wood screws", "glue_ml": round(glue_ml),
            "glue": "an 8 oz bottle of wood glue" if glue_ml <= 236 else f"{math.ceil(glue_ml / 473)} × 16 oz wood glue",
            "basis": f"screws 1 1/2 in from each end of {len(found)} joints ({total_in:.0f} in), then no more than "
                     f"{SCREW_EVERY_IN:g} in apart; glue ~{GLUE_ML_PER_IN} ml an inch"}
