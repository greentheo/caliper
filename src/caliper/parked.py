"""CALI-53 — parked: the frame on its jacks with someone inside, and the floor under a knee.

Driving, the hitch carries everything. Parked, a frame's ``jacks(params)`` hold the back up too, and the
load is a person — lying down (their weight and their gear spread over the floor, with a factor for moving
about) or kneeling (each knee a point load, tried at spots across the floor). For each, the frame is solved
with the box's walls carrying load as when driving (CALI-44), and the report says what holds it back:

- the frame's weakest member, and the walls';
- what each jack and the hitch carry — to choose jacks by, and to check the hitch while it's parked;
- **the floor under a knee**: a strip of the floor panel spanning the widest clear gap between what holds
  it up (a tube or a wall), with the knee's load spread over a patch — a mattress spreads a knee to roughly
  10 in; bare plywood takes it on ~3 in.
"""

from __future__ import annotations

import math
from typing import Optional

from . import construction as C
from . import materials as M
from .design import DesignStore

KG_LB = 2.20462262
LB = 4.4482216152605                 # N per lbf
IN = 25.4


def floor_knee(material: str, t: float, span: float, load_n: float, patch: float) -> dict:
    """A floor strip, simply supported over ``span`` (mm), under a load spread over ``patch`` (mm) in its
    middle. The strip that carries it is the patch plus half the span wide — a napkin rule, on the safe
    side for plywood."""
    mech = M.sheet(material)["mech"]
    b = patch + span / 2.0
    m = load_n * (span / 4.0 - patch / 8.0)
    stress = m / (b * t * t / 6.0)
    sag = load_n * span ** 3 / (48 * mech["E"] * b * t ** 3 / 12.0)
    return {"span_mm": round(span, 1), "patch_mm": round(patch, 1), "stress_mpa": round(stress, 2),
            "safety": round(mech["strength"] / stress, 2) if stress > 0 else 99.0, "sag_mm": round(sag, 2)}


def _floor(store: DesignStore, skip) -> Optional[dict]:
    for p in store.design.parts:
        if p.id in skip:
            continue
        d = C.declared(store, p.id)
        for it in d.get("construction") or []:
            if it.get("kind") == "sheet" and it.get("group") == "floor" and it.get("outline"):
                return {"part": p.id, "material": it["material"], "thickness": float(it["thickness"]),
                        "outline": it["outline"]}
    return None


def run(store: DesignStore, frame_id: str, *, person_lb: float = 200.0, gear_lb: float = 50.0,
        knee_lb: float = 150.0, factor: float = 1.5, mattress_in: float = 10.0, bare_in: float = 3.0,
        walls: bool = True) -> dict:
    """The parked cases, worst first, with the floor check."""
    from whittle import FrameStudy

    from . import frame_study as F

    fd = F.frame_def(store, frame_id)
    if not fd.get("jacks"):
        raise ValueError(f"'{frame_id}' has no jacks(params) — where does it stand when parked?")
    n_hitch = len(fd["supports"])
    floor = _floor(store, (frame_id,))
    if floor is None:
        raise ValueError("no part has a floor (a sheet in group 'floor') to stand on")
    zf = max(v[2] for v in floor["outline"]) + floor["thickness"]
    xs, ys = [v[0] for v in floor["outline"]], [v[1] for v in floor["outline"]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    carried_by = {}

    def solve(label, payload_lb, extra, fac):
        """A jack only pushes: one that would have to pull lifts off, and the case is solved without it."""
        if payload_lb not in carried_by:
            carried_by[payload_lb] = C.design_loads(store, skip=(frame_id,), payload_lb=payload_lb, walls=walls)
        carried = carried_by[payload_lb]
        on = list(range(len(fd["jacks"])))
        while True:
            held = {**fd, "supports": list(fd["supports"]) + [
                {"at": fd["jacks"][i]["at"], "fix": fd["jacks"][i].get("fix", ["uz"])} for i in on]}
            built = F.build_spec(held, factor=fac, points=carried["points"] + extra, walls=carried["shell"])
            r = FrameStudy.from_dict(built["spec"]).analyze()
            stand = r.cases["standing"].reactions
            nodes = [s["node"] for s in built["spec"]["supports"]]
            pushes = {i: float(stand[n, 2]) / LB for i, n in zip(on, nodes[n_hitch:])}
            lifting = [i for i, f in pushes.items() if f < -1.0]
            if not lifting:
                break
            on = [i for i in on if i not in lifting]
        summ = F._summary(r, built)
        hitch = sum(float(stand[n, 2]) for n in nodes[:n_hitch]) / LB
        jacks = [round(pushes.get(i, 0.0), 1) for i in range(len(fd["jacks"]))]
        walls_ = min((w["safety"] for w in summ.get("walls") or []), default=None)
        lifted = [fd["jacks"][i].get("name", f"jack {i + 1}") for i in range(len(fd["jacks"])) if i not in on]
        return {"case": label, "safety": summ["safety"], "governing": summ["governing"]["member"],
                "sag_in": summ["deflection_in"], "hitch_lb": round(hitch, 1), "jacks_lb": jacks,
                "lifted": lifted, "walls_safety": walls_, "reach_mm": built["applied"]["reach_mm"]}

    cases = [solve(f"lying down ({person_lb:g} lb + {gear_lb:g} lb of gear), ×{factor:g} for moving about",
                   person_lb + gear_lb, [], factor)]
    kg = knee_lb / KG_LB
    inset = 6 * IN
    spots = [(x, y, name) for x, xn in ((x1 - inset, "front"), ((x0 + x1) / 2, "middle"), (x0 + inset, "back"))
             for y, yn in ((y1 - inset, "left"), ((y0 + y1) / 2, "centre"), (y0 + inset, "right"))
             for name in [f"{xn} {yn}"]]
    for x, y, name in spots:
        knees = [((x, y + 6 * IN, zf), kg, None), ((x, y - 6 * IN, zf), kg, None)]
        cases.append(solve(f"kneeling at the {name} ({knee_lb:g} lb a knee)", gear_lb, knees, 1.0))
    worst = min(cases, key=lambda c: c["safety"])
    span = 2.0 * max(c["reach_mm"] for c in cases[:1])          # the floor's widest clear gap
    knee_n = knee_lb * LB
    on_mattress = floor_knee(floor["material"], floor["thickness"], span, knee_n, mattress_in * IN)
    bare = floor_knee(floor["material"], floor["thickness"], span, knee_n, bare_in * IN)
    return {"frame": frame_id, "person_lb": person_lb, "gear_lb": gear_lb, "knee_lb": knee_lb, "factor": factor,
            "cases": cases, "worst": worst,
            "jacks_max_lb": max(max(c["jacks_lb"]) for c in cases),
            "hitch_max_lb": max(c["hitch_lb"] for c in cases),
            "walls_min": min((c["walls_safety"] for c in cases if c["walls_safety"] is not None), default=None),
            "floor": {"part": floor["part"], "material": floor["material"], "thickness_mm": floor["thickness"],
                      "clear_span_in": round(span / IN, 1), "on_mattress": on_mattress, "bare": bare,
                      "mattress_in": mattress_in, "bare_in": bare_in}}
