"""CALI-52 — a roof under snow, and the skeleton that holds it up: checked by hand-book mechanics, searched.

A part that has a roof says how it's built with ``roof(params, build)``: its plan size inside the walls,
its skins and core, the beams under it (how many, which way, what size) and the rails at its front and
back that carry them down the posts (the "box inside the box"). Snow is a uniform pressure on the roof's
plan; the checks are the ones a builder would do on a napkin, each on the safe side:

- **the roof panel** between its supports, as a one-way strip on its shorter span (a sandwich: the skins
  carry the bending — compression held to the skin's wrinkling stress on the foam, or the foam's crush
  strength if there's no skin there; tension to the skin's strength, or bare foam's — and the foam the
  shear);
- **each beam**, simply supported, carrying its strip of roof;
- **the front and back rails**, carrying the beams' ends (or the roof's edge) between the posts.

``search()`` tries every combination of the skeleton choices it's given and returns them with weight,
cost and the snow check — the first job of the make loop (``specs/caliper-make-loop-spec.md``).
"""

from __future__ import annotations

import itertools
import json
import os
import time
from typing import Callable, Optional

from . import construction as C
from . import materials as M
from .design import DesignStore

PSF = 4.788026e-5                      # N/mm² per lb/ft²


def _layers(roof: dict) -> list[dict]:
    """The roof's section, bottom (inside) to top (outside): skins and core, each with what it can take."""
    core = M.sheet(roof["core"])["mech"]
    out = []
    for name in roof.get("skins_in") or []:
        sk = M.SKINS.get(name)
        if sk:
            out.append({"name": f"{name} (inside)", "t": sk["t"], "E": sk["E"], "G": sk["G"],
                        "tension": sk["strength"],
                        "compression": min(sk["strength"], 0.5 * (sk["E"] * core["E"] * core["G"]) ** (1 / 3))})
    out.append({"name": roof["core"], "t": float(roof["core_t"]), "E": core["E"], "G": core["G"],
                "tension": core["strength"], "compression": core.get("compression", core["strength"]),
                "core": True})
    for name in roof.get("skins_out") or []:
        sk = M.SKINS.get(name)
        if sk:
            out.append({"name": f"{name} (outside)", "t": sk["t"], "E": sk["E"], "G": sk["G"],
                        "tension": sk["strength"],
                        "compression": min(sk["strength"], 0.5 * (sk["E"] * core["E"] * core["G"]) ** (1 / 3))})
    return out


def panel(roof: dict, span: float, q: float) -> dict:
    """A 1 mm strip of roof, simply supported over ``span`` (mm) under pressure ``q`` (N/mm²)."""
    layers = _layers(roof)
    z = 0.0
    for L in layers:
        L["z0"], L["z1"] = z, z + L["t"]
        z += L["t"]
    ea = sum(L["E"] * L["t"] for L in layers)
    na = sum(L["E"] * L["t"] * (L["z0"] + L["z1"]) / 2 for L in layers) / ea
    ei = sum(L["E"] * (L["t"] ** 3 / 12 + L["t"] * ((L["z0"] + L["z1"]) / 2 - na) ** 2) for L in layers)
    m = q * span ** 2 / 8.0
    v = q * span / 2.0
    worst = []
    for L in layers:
        for zz in (L["z0"], L["z1"]):
            stress = m * (zz - na) * L["E"] / ei          # + above the axis: compression under snow
            if abs(stress) < 1e-12:
                continue
            limit = L["compression"] if stress > 0 else L["tension"]
            worst.append((limit / abs(stress), L["name"], "compression" if stress > 0 else "tension", abs(stress)))
    core = next(L for L in layers if L.get("core"))
    skins = [L for L in layers if not L.get("core")]
    d = (skins[-1]["z0"] + skins[-1]["z1"]) / 2 - (skins[0]["z0"] + skins[0]["z1"]) / 2 if len(skins) == 2 else 0.0
    tau = v / d if d > 0 else 1.5 * v / core["t"]          # sandwich: shear over the skins' spacing
    shear_safety = M.sheet(roof["core"])["mech"]["shear_strength"] / tau
    sag = 5 * q * span ** 4 / (384 * ei) + q * span ** 2 / (8 * core["G"] * core["t"])
    safety, name, sense, stress = min(worst)
    if shear_safety < safety:
        safety, name, sense, stress = shear_safety, roof["core"], "shear", tau
    return {"element": "roof panel", "span_mm": round(span, 1), "safety": round(safety, 2),
            "governs": f"{name} in {sense}", "stress_mpa": round(stress, 3), "sag_mm": round(sag, 1)}


def stick(name: str, size: str, span: float, w: float) -> dict:
    """A lumber stick, simply supported over ``span`` (mm), carrying ``w`` (N/mm) along it."""
    lum = M.STICKS["lumber"]
    b, h = lum["sizes"][size]
    b, h = min(b, h), max(b, h)                              # on edge: the deep way
    s = b * h ** 2 / 6.0
    i = b * h ** 3 / 12.0
    m = w * span ** 2 / 8.0
    stress = m / s
    sag = 5 * w * span ** 4 / (384 * lum["mech"]["E"] * i)
    return {"element": name, "size": size, "span_mm": round(span, 1),
            "safety": round(lum["mech"]["strength"] / stress, 2) if stress else 99.0,
            "governs": f"{size} in bending", "stress_mpa": round(stress, 2), "sag_mm": round(sag, 1)}


def check(roof: dict, psf: float) -> dict:
    """The roof, its beams and its rails under ``psf`` of snow. Safety is on breaking strength."""
    q = psf * PSF
    length, width = float(roof["length"]), float(roof["width"])     # x: front to back; y: across
    b = roof.get("beams") or {}
    n, size, along = int(b.get("count", 0)), b.get("size", "2x2"), b.get("dir", "fore-aft")
    out = []
    if n and along == "fore-aft":                  # beams front to back split the width
        spacing = width / (n + 1)
        out.append(panel(roof, min(spacing, length), q))
        out.append(stick(f"{n} roof beam(s), front to back", size, length, q * spacing))
        rail_w = n * (q * spacing * length / 2.0) / roof["rail_span"]   # the beams' ends, spread along it
    elif n:                                        # beams across split the length
        spacing = length / (n + 1)
        out.append(panel(roof, min(spacing, width), q))
        out.append(stick(f"{n} roof beam(s), across", size, width, q * spacing))
        rail_w = q * spacing / 2.0
    else:
        out.append(panel(roof, min(length, width), q))
        rail_w = q * min(length, width) / 2.0
    if roof.get("rail_size") and roof.get("rail_span"):
        out.append(stick("front and back top rails", roof["rail_size"], float(roof["rail_span"]), rail_w))
    worst = min(out, key=lambda e: e["safety"])
    return {"psf": psf, "safety": worst["safety"], "governing": f"{worst['element']}: {worst['governs']}",
            "sag_mm": max(e["sag_mm"] for e in out), "elements": out}


def search(store: DesignStore, part_id: str, options: dict, *, psf: float = 20.0, min_safety: float = 2.0,
           emit: Optional[Callable] = None) -> dict:
    """Every combination of ``options`` (BUILD entries → values to try), weighed, priced and checked
    under snow; the lightest that holds ``min_safety`` is recommended."""
    from .scorecard import cost_and_waste

    emit = emit or (lambda *a, **k: None)
    keys = list(options)
    combos = list(itertools.product(*(options[k] for k in keys)))
    rows = []
    for i, values in enumerate(combos):
        build = dict(zip(keys, values))
        d = C.declared(store, part_id, build)
        if not d.get("roof"):
            raise ValueError(f"'{part_id}' doesn't say how its roof is built — give it roof(params, build)")
        r = C.report(store, part_id, build)
        r["pieces_raw"] = C.takeoff(C._items(d))
        snow = check(d["roof"], psf)
        cost = cost_and_waste(store, {part_id: r}, {})
        rows.append({"build": build, "mass_lb": r["mass_lb"], "cost_usd": cost["usd"], "safety": snow["safety"],
                     "governing": snow["governing"], "sag_in": round(snow["sag_mm"] / M.IN, 2),
                     "holds": snow["safety"] >= min_safety, "elements": snow["elements"]})
        emit("progress", f"{i + 1}/{len(combos)}: {build} → {r['mass_lb']} lb, {snow['safety']}x",
             progress=(i + 1) / len(combos))
    ok = [r for r in rows if r["holds"]]
    best = min(ok, key=lambda r: (r["mass_lb"], r["cost_usd"])) if ok else max(rows, key=lambda r: r["safety"])
    cheapest = min(ok, key=lambda r: (r["cost_usd"], r["mass_lb"])) if ok else None
    # the trade-off: nothing else both lighter and cheaper
    front = [r for r in ok if not any(o["mass_lb"] <= r["mass_lb"] and o["cost_usd"] <= r["cost_usd"]
                                      and (o["mass_lb"], o["cost_usd"]) != (r["mass_lb"], r["cost_usd"]) for o in ok)]
    rid = time.strftime("%Y%m%d-%H%M%S")
    rec = {"id": rid, "part": part_id, "created": time.time(), "psf": psf, "min_safety": min_safety,
           "options": options, "rows": rows, "best": best["build"], "cheapest": cheapest and cheapest["build"],
           "frontier": [r["build"] for r in sorted(front, key=lambda r: r["mass_lb"])]}
    root = os.path.join(store.root, "searches")
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, f"{rid}-snow.json"), "w") as f:
        json.dump(rec, f, indent=2)
    store.append_history(part_id, {"kind": "search", "action": "snow", "run": rid, "tried": len(rows),
                                   "best": best["build"]})
    emit("done", f"{len(rows)} tried, {len(ok)} hold {min_safety}x; lightest that holds: {best['build']}")
    return rec
