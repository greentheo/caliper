"""CALI-71 (#32) — lighten a sheet part where the wood isn't working, in cuts a sheet can take.

The strength check (``load_study``) says a part holds and draws where it works hardest. A plywood stool's
walls work at a tenth of what they can take. whittle's 3D lightening would take voxels out anywhere,
leaving pockets in a panel's thickness that a sheet can't be cut into: plywood comes out all the way
through or not at all. So Caliper lightens panel by panel, through the thickness:

1. **Which panels:** every flat sheet the loads pass *through*. The one a load lands on face-on (the top)
   stays solid, and the plate check keeps judging it.
2. **Where the wood isn't working:** the strength check's own FEA, read straight through each panel. A
   column's stress is the worst of its voxels, across every load.
3. **Holes a jigsaw can cut:** the quietest columns come out first, cleaned into holes with a solid rim
   round the panel (its joints are there), no hole narrower than :data:`MIN_HOLE_MM`, no web between two
   holes narrower than :data:`MIN_WEB_MM`, and rounded corners.
4. **Checked again in 3D, every step:** each station is re-analysed with its holes in, and the next takes
   out the quietest of what's left. It stops at the first that doesn't hold.

Using a station writes its holes into the script as ``HOLES`` (see ``holes.py``), so every later build cuts
them and the weight, the bill of materials and the patterns all see them.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Callable, Optional

import numpy as np

from . import load_study as L
from .design import DesignStore

IN = 25.4
#: Solid plywood left round every lightened panel: its glue and screws are along its edges.
RIM_MM = 1.5 * IN
#: The narrowest hole: a jigsaw blade, started in a 3/8 in pilot hole, turns inside about this.
MIN_HOLE_MM = 1.5 * IN
#: The narrowest strip left between two holes.
MIN_WEB_MM = 1.5 * IN
#: Corners rounded to this radius: a jigsaw has to turn, and a sharp inside corner starts a crack.
ROUND_MM = 0.5 * IN
#: How much of each panel's inside (within the rim) each station takes out, cumulatively.
STEPS = (0.25, 0.5, 0.75, 1.0)


# ---------------------------------------------------------------------------
# Which panels, and their wood as a grid of columns through the thickness
# ---------------------------------------------------------------------------
def _loaded_face_on(pc: dict, loads: list[dict], tol: float) -> bool:
    from .consistency import _frame, _inside2d

    for load in loads:
        lo, hi = np.asarray(load["lo"]), np.asarray(load["hi"])
        c = (lo + hi) / 2
        for poly in pc["polys"]:
            o, u, v, n, flat = _frame(poly)
            rel = c - o
            depth = abs(float((hi - lo) @ np.abs(n))) / 2
            if (abs(float(rel @ n)) <= pc["thickness"] + depth + tol
                    and _inside2d(np.array([[rel @ u, rel @ v]]), flat)[0]):
                return True
    return False


def panels(ctx: dict) -> list[dict]:
    """The flat panels the loads pass through, each as a grid of columns (cells) in its own plane."""
    from .consistency import _edge_dist2d, _frame, _inside2d

    ls, s = ctx["ls"], ctx["spacing"]
    centres = np.asarray(ls.grid.origin) + s * np.argwhere(ls.solid)
    idx = np.argwhere(ls.solid)
    out = []
    for pc in ctx["pieces"]:
        if pc["kind"] != "sheet" or len(pc["polys"]) != 1 or _loaded_face_on(pc, ctx["loads"], ctx["tol"]):
            continue
        poly, side, t = pc["polys"][0], pc["sides"][0], pc["thickness"]
        o, u, v, n, flat = _frame(poly)
        lo = flat.min(axis=0)
        shape = np.maximum(np.ceil((flat.max(axis=0) - lo) / s).astype(int), 1)
        g = np.stack(np.meshgrid((np.arange(shape[0]) + 0.5) * s + lo[0],
                                 (np.arange(shape[1]) + 0.5) * s + lo[1], indexing="ij"), -1).reshape(-1, 2)
        inside = _inside2d(g, flat).reshape(shape)
        rim = (_edge_dist2d(g, flat) < RIM_MM).reshape(shape)
        rel = centres - o
        w = (rel @ n) * side
        uv = np.stack([rel @ u, rel @ v], axis=1)
        cell = np.floor((uv - lo) / s).astype(int)
        mine = ((w > -0.25 * s) & (w < t + 0.25 * s) & np.all(cell >= 0, axis=1) & np.all(cell < shape, axis=1))
        mine[mine] &= inside[cell[mine, 0], cell[mine, 1]]
        if not mine.any():
            continue
        out.append({"name": pc["name"], "o": o, "u": u, "v": v, "n": n * side, "t": t, "lo": lo,
                    "flat": flat, "shape": tuple(shape), "inside": inside, "free": inside & ~rim,
                    "voxels": idx[mine], "cells": cell[mine], "material": pc.get("material")})
    return out


def _column_stress(p: dict, von_mises: np.ndarray, solid: np.ndarray) -> np.ndarray:
    """Per cell, the worst stress through the panel's thickness; +inf where there's no wood left."""
    vx = p["voxels"]
    alive = solid[vx[:, 0], vx[:, 1], vx[:, 2]]
    worst = np.full(p["shape"], -np.inf)
    np.maximum.at(worst, (p["cells"][:, 0], p["cells"][:, 1]),
                  np.where(alive, von_mises[vx[:, 0], vx[:, 1], vx[:, 2]], -np.inf))
    return np.where(np.isfinite(worst), worst, np.inf)


# ---------------------------------------------------------------------------
# Holes a jigsaw can cut
# ---------------------------------------------------------------------------
def _disk(r_cells: float) -> np.ndarray:
    k = int(np.ceil(r_cells))
    y, x = np.ogrid[-k:k + 1, -k:k + 1]
    return x * x + y * y <= r_cells * r_cells + 1e-9


def clean(p: dict, want: np.ndarray, s: float):
    """The cells someone asked to take out, as holes a jigsaw can cut: shapely polygons in the panel's
    plane, and the cells they cover."""
    from scipy import ndimage
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from skimage import measure

    rem = want & p["free"]
    rem = ndimage.binary_opening(rem, structure=_disk(MIN_HOLE_MM / 2 / s))
    keep = p["inside"] & ~rem
    thin = keep & ~ndimage.binary_opening(keep, structure=_disk(MIN_WEB_MM / 2 / s)) & ~(p["inside"] & ~p["free"])
    rem &= ~ndimage.binary_dilation(thin, structure=_disk(MIN_WEB_MM / 2 / s))
    rem = ndimage.binary_opening(rem, structure=_disk(MIN_HOLE_MM / 2 / s))
    polys = []
    # inside the rim, always: a hole that crept into it would cut into a glued joint
    room = Polygon(p["flat"]).buffer(-RIM_MM, join_style=2)
    R = ROUND_MM
    for c in measure.find_contours(np.pad(rem.astype(float), 1), 0.5):
        pts = (c - 1 + 0.5) * s + p["lo"]                 # back to the panel's (u, v), in mm
        if len(pts) < 4:
            continue
        poly = Polygon(pts).buffer(0)
        if poly.is_empty:
            continue
        # smooth the voxel steps both ways (fill notches, then round corners), then keep the arcs
        poly = poly.buffer(R).buffer(-2 * R).buffer(R)
        poly = poly.intersection(room).buffer(-R).buffer(R).simplify(0.5)
        for g in getattr(poly, "geoms", [poly]):
            if g.area >= MIN_HOLE_MM ** 2 * 0.6:
                polys.append(g)
    holes = unary_union(polys) if polys else None
    holes = [] if holes is None else list(getattr(holes, "geoms", [holes]))
    # the cells the holes really cover: what the FEA checks is what gets cut
    from shapely import contains_xy

    g = np.stack(np.meshgrid((np.arange(p["shape"][0]) + 0.5) * s + p["lo"][0],
                             (np.arange(p["shape"][1]) + 0.5) * s + p["lo"][1], indexing="ij"), -1)
    covered = np.zeros(p["shape"], dtype=bool)
    for h in holes:
        covered |= contains_xy(h, g[..., 0], g[..., 1])
    return holes, covered & p["inside"]


def to_3d(p: dict, poly) -> list[list[float]]:
    """A hole in the panel's plane as points on its outline face."""
    xy = np.asarray(poly.exterior.coords)[:-1]
    pts = p["o"] + xy[:, :1] * p["u"] + xy[:, 1:] * p["v"]
    return [[round(float(c), 2) for c in pt] for pt in pts]


def _cut_solid(solid: np.ndarray, p: dict, covered: np.ndarray) -> np.ndarray:
    hit = covered[p["cells"][:, 0], p["cells"][:, 1]]
    vx = p["voxels"][hit]
    solid = solid.copy()
    solid[vx[:, 0], vx[:, 1], vx[:, 2]] = False
    return solid


def preview(mesh, plist: list[dict], holes: dict) -> bytes:
    """The part with its holes cut, as STL (for the viewport)."""
    import trimesh

    prisms = []
    for p in plist:
        for poly in holes.get(p["name"], []):
            pr = trimesh.creation.extrude_polygon(poly, p["t"] + 2.0)
            T = np.eye(4)
            T[:3, 0], T[:3, 1], T[:3, 2] = p["u"], p["v"], p["n"]
            T[:3, 3] = p["o"] - p["n"] * 1.0             # (trimesh keeps a mirrored prism outside-out)
            pr.apply_transform(T)
            prisms.append(pr)
    out = mesh.difference(trimesh.util.concatenate(prisms), engine="manifold") if prisms else mesh
    return out.export(file_type="stl")


# ---------------------------------------------------------------------------
# The study
# ---------------------------------------------------------------------------
def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "lighten")


def study(store: DesignStore, part_id: str, *, min_safety: float = L.MIN_SAFETY, steps=STEPS,
          emit: Optional[Callable] = None) -> dict:
    """From the part as it is to the lightest station that still holds, every one checked in 3D."""
    emit = emit or (lambda *a, **k: None)
    t0 = time.time()
    ctx = L.prepare(store, part_id, emit)
    s, mat = ctx["spacing"], ctx["mat"]
    plist = panels(ctx)
    if not plist:
        raise ValueError(f"'{part_id}' has no flat panel the loads pass through to lighten")
    density = mat["density"] * 1e-3                       # g/mm³ (from g/cm³)
    whole = sum(float(p["inside"].sum()) * s * s for p in plist)

    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out_dir = os.path.join(runs_dir(store), rid)
    os.makedirs(out_dir, exist_ok=True)

    from scipy import ndimage

    solid = ctx["ls"].solid.copy()
    # holes it already has: free cells with no wood (opened, so a cell the grid happened to miss isn't one)
    removed = {p["name"]: ndimage.binary_opening(
        ~np.isfinite(_column_stress(p, np.zeros(solid.shape), solid)) & p["free"],
        structure=_disk(MIN_HOLE_MM / 2 / s)) for p in plist}
    stations, last = [], None
    for k, target in enumerate((0.0, *steps)):
        emit("station", f"station {k}: {target:.0%} of the walls' insides", progress=k / (len(steps) + 1))
        holes, cut = {}, solid
        if k:
            # the quietest columns of what's left, across every panel, until the target is out
            stress = {p["name"]: _column_stress(p, last, solid) for p in plist}
            pool = np.concatenate([np.where(p["free"] & ~removed[p["name"]], stress[p["name"]], np.inf).ravel()
                                   for p in plist])
            goal = int(round(target * sum(int(p["free"].sum()) for p in plist)))
            have = sum(int(removed[p["name"]].sum()) for p in plist)
            if goal > have:
                finite = np.sort(pool[np.isfinite(pool)])
                level = finite[min(goal - have, len(finite)) - 1] if len(finite) else -np.inf
                for p in plist:
                    removed[p["name"]] |= p["free"] & (stress[p["name"]] <= level)
            cut = ctx["ls"].solid.copy()
            for p in plist:
                polys, covered = clean(p, removed[p["name"]], s)
                holes[p["name"]] = polys
                cut = _cut_solid(cut, p, covered)
        cases, results = [], []
        for i in range(len(ctx["loads"])):
            case, r = L.check_load(ctx, i, min_safety, cut)
            cases.append(case)
            results.append(r)
        safety = min((c["safety"] for c in cases if c.get("safety") is not None), default=None)
        hole_area = sum(h.area for hs in holes.values() for h in hs)
        saved_g = sum(h.area * p["t"] * density for p in plist for h in holes.get(p["name"], []))
        st = {"index": k, "target": target, "removed": round(hole_area / whole, 3) if whole else 0.0,
              "saved_lb": round(saved_g / 453.59237, 2), "holes": sum(len(v) for v in holes.values()),
              "safety": safety, "holds": bool(cases) and all(c.get("holds") for c in cases),
              "cases": [{"name": c["name"], "safety": c.get("safety"), "governs": c.get("governs"),
                         "fea_safety": (c.get("fea") or {}).get("safety"),
                         "in": (c.get("fea") or {}).get("in")} for c in cases],
              "panels": {p["name"]: [to_3d(p, h) for h in holes.get(p["name"], [])] for p in plist}}
        if stations and st["removed"] <= stations[-1]["removed"] + 1e-3:
            continue                                     # the clean-up ate this step: nothing new
        st["index"] = len(stations)
        with open(os.path.join(out_dir, f"station_{st['index']:02d}.stl"), "wb") as f:
            f.write(preview(ctx["mesh"], plist, holes))
        stations.append(st)
        last = np.max([np.where(r.solid, r.von_mises, 0.0) for r in results if r.supported], axis=0) \
            if any(r.supported for r in results) else np.zeros(solid.shape)
        solid = cut
        if not st["holds"]:
            break

    record = {
        "id": rid, "part": part_id, "kind": "lighten", "created": time.time(),
        "version": store.design.part(part_id).version, "seconds": round(time.time() - t0, 1),
        "min_safety": min_safety, "material": mat["name"], "spacing_mm": round(s, 2),
        "panels": [{"name": p["name"], "thickness_mm": p["t"], "normal": [round(float(c), 6) for c in p["n"]]}
                   for p in plist],
        "rules": {"rim_mm": RIM_MM, "min_hole_mm": MIN_HOLE_MM, "min_web_mm": MIN_WEB_MM, "round_mm": ROUND_MM},
        "stations": stations,
        "notes": [
            "Holes go all the way through, so a jigsaw (or a router) can cut them: a 1.5 in solid rim "
            "round each panel where it's glued and screwed, no hole or strip between holes narrower than "
            "1.5 in, corners rounded to 1/2 in.",
            "Only the panels the load passes through are lightened; the one it lands on stays solid, and "
            "the plate check keeps judging it.",
            "Each station is the FEA of the part with its holes in. It takes the joints as solid wood and "
            "doesn't check buckling, which these short, thick strips are far from.",
        ],
    }
    with open(os.path.join(out_dir, "run.json"), "w") as f:
        json.dump(record, f, indent=2, default=str)
    best = max((x for x in stations if x["holds"]), key=lambda x: x["removed"], default=None)
    store.append_history(part_id, {"kind": "lighten", "action": "studied", "run": rid,
                                   "stations": len(stations), "best_removed": best and best["removed"]})
    store.append_log({"kind": "lighten", "action": "studied", "part": part_id, "run": rid})
    emit("done", (f"{len(stations)} stations; the lightest that holds takes out {best['removed']:.0%} of the "
                  f"walls ({best['saved_lb']} lb), {best['safety']}x") if best else "nothing lighter holds",
         run=rid, progress=1.0)
    return record


def list_runs(store: DesignStore, part_id: Optional[str] = None) -> list[dict]:
    root = runs_dir(store)
    if not os.path.isdir(root):
        return []
    out = []
    for rid in sorted(os.listdir(root), reverse=True):
        rec = load_run(store, rid)
        if rec and (part_id is None or rec.get("part") == part_id):
            out.append(rec)
    return out


def load_run(store: DesignStore, rid: str) -> Optional[dict]:
    if not rid or "/" in rid or ".." in rid:
        return None
    path = os.path.join(runs_dir(store), rid, "run.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def station_path(store: DesignStore, rid: str, index: int) -> str:
    if not rid or "/" in rid or ".." in rid:
        raise ValueError("bad run id")
    return os.path.join(runs_dir(store), rid, f"station_{int(index):02d}.stl")


def adopt(store: DesignStore, rid: str, index: int) -> dict:
    """Write a station's holes into the part's script as ``HOLES``: a new revision that cuts them."""
    import ast

    from .holes import NAME

    rec = load_run(store, rid)
    if rec is None:
        raise FileNotFoundError(f"no lightening study {rid!r}")
    st = next((x for x in rec["stations"] if x["index"] == int(index)), None)
    if st is None:
        raise FileNotFoundError(f"study {rid} has no station {index}")
    pid = rec["part"]
    holes = [{"piece": p["name"], "normal": p["normal"], "depth": p["thickness_mm"],
              "polygons": st["panels"].get(p["name"], [])} for p in rec["panels"] if st["panels"].get(p["name"])]
    script = store.read_script(pid)
    block = f"{NAME} = " + json.dumps(holes, indent=4) + "\n"
    tree = ast.parse(script)
    lines = script.splitlines(keepends=True)
    old = next((n for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == NAME), None)
    if old is not None:
        script = "".join(lines[:old.lineno - 1]) + block + "".join(lines[old.end_lineno:])
    else:
        script = (script.rstrip("\n") + "\n\n\n# Lightening holes, cut all the way through (Caliper writes this "
                  "and cuts them after build()).\n" + block)
    version = store.write_part(pid, script, action="lighten",
                               feedback=f"lightened: {st['removed']:.0%} out of the walls, {st['holes']} holes, "
                                        f"{st['saved_lb']} lb lighter, {st['safety']}x",
                               extra={"lighten_run": rid, "station": int(index)})
    return {"version": version, "removed": st["removed"], "holes": st["holes"], "saved_lb": st["saved_lb"]}
