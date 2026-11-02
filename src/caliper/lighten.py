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
from .consistency import _frame
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
#: The panel someone stands on gets round holes a hole saw cuts, small enough to step over, one at a time.
HOLE_SAW_MM = 1.5 * IN


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


def panels(ctx: dict, stood_on: bool = False) -> list[dict]:
    """The flat panels the loads pass through (or, ``stood_on``, the ones a load lands on face-on), each as a
    grid of columns (cells) in its own plane."""
    from .consistency import _edge_dist2d, _frame, _inside2d

    ls, s = ctx["ls"], ctx["spacing"]
    centres = np.asarray(ls.grid.origin) + s * np.argwhere(ls.solid)
    idx = np.argwhere(ls.solid)
    out = []
    for pc in ctx["pieces"]:
        if pc["kind"] != "sheet" or len(pc["polys"]) != 1 or _loaded_face_on(pc, ctx["loads"], ctx["tol"]) != stood_on:
            continue
        poly, side, t = pc["polys"][0], pc["sides"][0], pc["thickness"]
        o, u, v, n, flat = _frame(poly)
        lo = flat.min(axis=0)
        shape = np.maximum(np.ceil((flat.max(axis=0) - lo) / s).astype(int), 1)
        g = np.stack(np.meshgrid((np.arange(shape[0]) + 0.5) * s + lo[0],
                                 (np.arange(shape[1]) + 0.5) * s + lo[1], indexing="ij"), -1).reshape(-1, 2)
        inside = _inside2d(g, flat).reshape(shape)
        rim = (_edge_dist2d(g, flat) < RIM_MM).reshape(shape)
        for pic in pc.get("pictures") or []:     # a picture cut out (CALI-78) keeps a web of wood round it
            rel = np.asarray(pic, float) - o
            ring = np.stack([rel @ u, rel @ v], axis=1)
            rim |= (_inside2d(g, ring) | (_edge_dist2d(g, ring) < MIN_WEB_MM)).reshape(shape)
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


def sites(p: dict, s: float) -> list[dict]:
    """Where a hole-saw hole fits in a panel someone stands on: centres on a grid, a web apart, inside the rim.
    Each with the cells under it."""
    from shapely import contains_xy
    from shapely.geometry import Point, Polygon

    r = HOLE_SAW_MM / 2
    room = Polygon(p["flat"]).buffer(-(RIM_MM + r), join_style=2)
    if room.is_empty:
        return []
    pitch = HOLE_SAW_MM + MIN_WEB_MM
    x0, y0, x1, y1 = room.bounds
    xs = np.arange(0, (x1 - x0) // pitch + 1) * pitch
    ys = np.arange(0, (y1 - y0) // pitch + 1) * pitch
    xs, ys = xs + x0 + ((x1 - x0) - xs[-1]) / 2, ys + y0 + ((y1 - y0) - ys[-1]) / 2   # centred in the room
    g = np.stack(np.meshgrid((np.arange(p["shape"][0]) + 0.5) * s + p["lo"][0],
                             (np.arange(p["shape"][1]) + 0.5) * s + p["lo"][1], indexing="ij"), -1)
    out = []
    for x in xs:
        for y in ys:
            if room.buffer(0.5).contains(Point(x, y)):
                circle = Point(x, y).buffer(r, quad_segs=8)
                out.append({"at": (float(x), float(y)), "poly": circle,
                            "cells": contains_xy(circle, g[..., 0], g[..., 1]) & p["inside"]})
    return out


#: A round hole in a plate in bending: the stress at its edge over the stress there without it (Peterson,
#: for a thin plate, about 1.8 to 2.1). The voxels round a hole are stair-stepped, and a voxel model's stress
#: there reports the steps; so the hole's own edge is judged by this, from the solid panel's stress where
#: it goes, and the rest of the panel by the FEA with a ring of voxels round each hole left out.
KT_HOLE = 2.0


def _panel_peak(p: dict, von_mises: np.ndarray, solid: np.ndarray, near: np.ndarray, ring=None) -> float:
    """How hard one panel works: its worst stress beside (not at) where loads and supports attach, and not in
    the ``ring`` of voxels round its holes."""
    vx = p["voxels"]
    ok = solid[vx[:, 0], vx[:, 1], vx[:, 2]] & ~near[vx[:, 0], vx[:, 1], vx[:, 2]]
    if ring is not None:
        ok &= ~ring[vx[:, 0], vx[:, 1], vx[:, 2]]
    return float(von_mises[vx[ok, 0], vx[ok, 1], vx[ok, 2]].max()) if ok.any() else 0.0


def _ring(p: dict, cells: np.ndarray, shape) -> np.ndarray:
    """The voxels next to a panel's holes (``cells`` are the hole's columns)."""
    from scipy import ndimage

    gone = np.zeros(shape, dtype=bool)
    hit = cells[p["cells"][:, 0], p["cells"][:, 1]]
    vx = p["voxels"][hit]
    gone[vx[:, 0], vx[:, 1], vx[:, 2]] = True
    return ndimage.binary_dilation(gone, iterations=1)


def judge_holed(ctx: dict, i: int, case: dict, r, min_safety: float) -> dict:
    """A panel stood on that already has holes (from ``HOLES``): the plate formula doesn't apply to it, so it's
    judged as the lightening study judges one: solved once with its holes filled (the plate check's
    calibration, and the stress where each hole is), then as it is, with each hole's edge at KT_HOLE times
    that stress and the rest by the FEA, both scaled by the calibration."""
    from scipy import ndimage
    from shapely.geometry import Polygon

    holed = [pc for pc in ctx["pieces"] if pc["kind"] == "sheet" and pc.get("holes") and len(pc["polys"]) == 1
             and _loaded_face_on(pc, ctx["loads"], ctx["tol"])]
    if not holed or not r.supported:
        return case
    ls, s, mat = ctx["ls"], ctx["spacing"], ctx["mat"]
    filled = ls.solid.copy()
    for pc in holed:                                     # the panel as if it were solid
        o, u, v, n, _ = _frame(pc["polys"][0])
        n = n * pc["sides"][0]
        for h in pc["holes"]:
            box = Polygon(np.stack([(h - o) @ u, (h - o) @ v], axis=1))
            x0, y0, x1, y1 = box.bounds
            for x in np.arange(x0, x1 + s, s / 2):
                for y in np.arange(y0, y1 + s, s / 2):
                    if box.buffer(s / 2).contains(type(box.centroid)(x, y)):
                        for w in np.arange(s / 2, pc["thickness"], s / 2):
                            ix = np.round((o + x * u + y * v + w * n - np.asarray(ls.grid.origin)) / s).astype(int)
                            if np.all(ix >= 0) and np.all(ix < filled.shape):
                                filled[tuple(ix)] = True
    cache = ctx.setdefault("_filled", {})                  # the filled solve, once per load
    if i not in cache:
        held, ls.solid = ls.solid, filled                  # the panels' columns, mapped on the filled part
        try:
            cache[i] = (ls.solver().solve(filled), {p["name"]: p for p in panels(ctx, stood_on=True)})
        finally:
            ls.solid = held
    r0, tops = cache[i]
    near = ndimage.binary_dilation(ctx["attach"], iterations=1)
    load, worst, allow = ctx["loads"][i], None, mat["strength"] * mat["across"]
    pl = L.plate_check(ctx["pieces"], load, mat, ctx["tol"])
    for pc in holed:
        p = tops.get(pc["name"])
        if p is None:
            continue
        peak0 = _panel_peak(p, r0.von_mises, r0.solid, near)
        k = max(1.0, pl["stress_mpa"] / peak0) if pl and pl.get("done") and pl["piece"] == pc["name"] and peak0 > 0 else 1.0
        cells = _covered(p, [Polygon(np.stack([(h - p["o"]) @ p["u"], (h - p["o"]) @ p["v"]], axis=1))
                             for h in pc["holes"]], s)
        peak = _panel_peak(p, r.von_mises, r.solid, near, _ring(p, cells, filled.shape))
        before = _column_stress(p, r0.von_mises, filled)
        edge = float(np.max(np.where(cells, before, 0.0)))
        mine = min(allow / (peak * k) if peak > 0 else np.inf, allow / (KT_HOLE * edge * k) if edge > 0 else np.inf)
        worst = mine if worst is None else min(worst, mine)
    if worst is None or not np.isfinite(worst):
        return case
    fea = (case.get("fea") or {}).get("safety")
    safety = round(min(worst, fea) if fea else worst, 2)
    plate = dict(pl or {}, done=False, why="it has holes, so the plate formula doesn't apply; the FEA does, "
                                           "calibrated against it on the panel solid")
    case.update({"safety": safety, "governs": "fea-calibrated", "holds": safety >= min_safety, "plate": plate,
                 "breaks_lb": round(case["lb"] * case["factor"] * safety, -1)})
    return case


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
    """From the part as it is to where the safety runs out, every step checked in 3D: the walls first (holes
    where the wood isn't working), then hole-saw holes in the panel stood on, then thinner sheet (estimated)."""
    from scipy import ndimage

    from . import construction as C
    from . import materials as M

    emit = emit or (lambda *a, **k: None)
    t0 = time.time()
    ctx = L.prepare(store, part_id, emit)
    s, mat = ctx["spacing"], ctx["mat"]
    plist, tops = panels(ctx), panels(ctx, stood_on=True)
    # a panel stood on that already has holes is judged as it is (judge_holed), and gets no more
    tops = [p for p in tops if not any(pc["name"] == p["name"] and pc.get("holes") for pc in ctx["pieces"])]
    if not plist and not tops:
        raise ValueError(f"'{part_id}' has no flat panel to lighten")
    density = mat["density"] * 1e-3                       # g/mm³ (from g/cm³)
    whole = sum(float(p["inside"].sum()) * s * s for p in plist)
    near = ndimage.binary_dilation(ctx["attach"], iterations=1)
    spots = {p["name"]: sites(p, s) for p in tops}

    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out_dir = os.path.join(runs_dir(store), rid)
    os.makedirs(out_dir, exist_ok=True)

    solid = ctx["ls"].solid.copy()
    # holes it already has: free cells with no wood (opened, so a cell the grid happened to miss isn't one)
    removed = {p["name"]: ndimage.binary_opening(
        ~np.isfinite(_column_stress(p, np.zeros(solid.shape), solid)) & p["free"],
        structure=_disk(MIN_HOLE_MM / 2 / s)) for p in plist}
    chosen = {p["name"]: [] for p in tops}                # hole-saw holes in the panels stood on
    calib: dict = {}                                      # (case, top) -> how far the FEA reads low there
    vm0: dict = {}                                        # case -> its stress with nothing taken out
    # the walls in steps of their inside; the top one hole at a time (each one counts on a panel stood on)
    holes_max = max((len(v) for v in spots.values()), default=0)
    plan = ([("walls", 0.0)] + [("walls", f) for f in steps]
            + [("top", (n + 1) / holes_max) for n in range(holes_max)] if tops else [("walls", 0.0)] + [("walls", f) for f in steps])
    stations, last, wall_holes, wall_cover = [], None, {}, {}
    for k, (phase, target) in enumerate(plan):
        emit("station", f"step {k}: {'the walls' if phase == 'walls' else 'the top'}, {target:.0%}",
             progress=k / len(plan))
        holes = dict(wall_holes)
        if phase == "walls" and k:
            # the quietest columns of what's left, across every wall, until the target is out
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
            for p in plist:
                holes[p["name"]], wall_cover[p["name"]] = clean(p, removed[p["name"]], s)
        if phase == "top":
            # the quietest hole-saw spots of what's left, in every panel stood on
            for p in tops:
                stress = _column_stress(p, last, solid)
                left = [x for x in spots[p["name"]] if x not in chosen[p["name"]]]
                left.sort(key=lambda x: float(np.max(np.where(x["cells"], stress, -np.inf))))
                want = int(round(target * len(spots[p["name"]])))
                chosen[p["name"]] += left[:max(0, want - len(chosen[p["name"]]))]
        for p in tops:
            if chosen[p["name"]]:
                holes[p["name"]] = [x["poly"] for x in chosen[p["name"]]]
        cut = ctx["ls"].solid.copy()
        for p in plist:
            if holes.get(p["name"]) and p["name"] in wall_cover:
                cut = _cut_solid(cut, p, wall_cover[p["name"]])
        for p in tops:
            if chosen[p["name"]]:
                cut = _cut_solid(cut, p, np.any([x["cells"] for x in chosen[p["name"]]], axis=0))
        cases, results = [], []
        for i in range(len(ctx["loads"])):
            case, r = L.check_load(ctx, i, min_safety, cut)
            if r.supported:
                if phase == "walls":                     # the part the top's holes go into: the latest walls
                    vm0[i] = r.von_mises
                for p in tops:
                    holed = np.any([x["cells"] for x in chosen[p["name"]]], axis=0) if chosen[p["name"]] else None
                    ring = _ring(p, holed, cut.shape) if holed is not None else None
                    peak = _panel_peak(p, r.von_mises, r.solid, near, ring)
                    pl = case.get("plate") or {}
                    if phase == "walls" and pl.get("done") and pl.get("piece") == p["name"] and peak > 0:
                        # how far the FEA reads low against the plate check on this panel, solid, in the part
                        # as the walls leave it: carried on to its holes
                        calib[(i, p["name"])] = max(1.0, pl["stress_mpa"] / peak)
                    if holed is not None and peak > 0:
                        # holes in it: the plate formula no longer applies. The rest of the panel by the FEA,
                        # and each hole's edge by KT_HOLE times the stress the solid panel had there; both
                        # scaled by how far the FEA read low against the plate check, solid
                        kk, allow = calib.get((i, p["name"]), 1.0), mat["strength"] * mat["across"]
                        before = _column_stress(p, vm0.get(i, r.von_mises), ctx["ls"].solid)
                        edge = max(float(np.max(np.where(x["cells"], before, 0.0))) for x in chosen[p["name"]])
                        mine = min(allow / (peak * kk), allow / (KT_HOLE * edge * kk) if edge > 0 else np.inf)
                        fea = (case.get("fea") or {}).get("safety")
                        safety = round(min(mine, fea) if fea else mine, 2)
                        case.update({"safety": safety, "governs": "fea-calibrated", "holds": safety >= min_safety,
                                     "breaks_lb": round(case["lb"] * case["factor"] * safety, -1)})
            cases.append(case)
            results.append(r)
        safety = min((c["safety"] for c in cases if c.get("safety") is not None), default=None)
        wall_area = sum(h.area for p in plist for h in holes.get(p["name"], []))
        saved_g = sum(h.area * p["t"] * density for p in plist + tops for h in holes.get(p["name"], []))
        st = {"index": k, "phase": phase, "target": target, "removed": round(wall_area / whole, 3) if whole else 0.0,
              "saved_lb": round(saved_g / 453.59237, 2), "holes": sum(len(v) for v in holes.values()),
              "top_holes": sum(len(chosen[p["name"]]) for p in tops),
              "safety": safety, "holds": bool(cases) and all(c.get("holds") for c in cases),
              "cases": [{"name": c["name"], "safety": c.get("safety"), "governs": c.get("governs"),
                         "fea_safety": (c.get("fea") or {}).get("safety"), "breaks_lb": c.get("breaks_lb"),
                         "in": (c.get("fea") or {}).get("in")} for c in cases],
              "panels": {p["name"]: [to_3d(p, h) for h in holes.get(p["name"], [])] for p in plist + tops}}
        if stations and st["saved_lb"] <= stations[-1]["saved_lb"] + 1e-3:
            continue                                     # the clean-up ate this step: nothing new
        st["index"] = len(stations)
        with open(os.path.join(out_dir, f"station_{st['index']:02d}.stl"), "wb") as f:
            f.write(preview(ctx["mesh"], plist + tops, holes))
        stations.append(st)
        last = np.max([np.where(r.solid, r.von_mises, 0.0) for r in results if r.supported], axis=0) \
            if any(r.supported for r in results) else np.zeros(solid.shape)
        solid = cut
        if phase == "walls":
            wall_holes = {n: v for n, v in holes.items() if n in wall_cover}
        if not st["holds"]:
            break

    # thinner sheet, from the lightest step that holds: an estimate, until it's rebuilt and checked
    thinner = _thinner(ctx, stations, tops, min_safety, density, C, M)
    stations += [dict(t, index=len(stations) + i) for i, t in enumerate(thinner)]

    record = {
        "id": rid, "part": part_id, "kind": "lighten", "created": time.time(),
        "version": store.design.part(part_id).version, "seconds": round(time.time() - t0, 1),
        "min_safety": min_safety, "material": mat["name"], "spacing_mm": round(s, 2),
        "panels": [{"name": p["name"], "thickness_mm": p["t"], "normal": [round(float(c), 6) for c in p["n"]],
                    "stood_on": p in tops} for p in plist + tops],
        "rules": {"rim_mm": RIM_MM, "min_hole_mm": MIN_HOLE_MM, "min_web_mm": MIN_WEB_MM, "round_mm": ROUND_MM,
                  "hole_saw_mm": HOLE_SAW_MM},
        "stations": stations,
        "notes": [
            "The walls first: holes all the way through, so a jigsaw (or a router) can cut them, with a 1.5 in "
            "solid rim round each panel where it's glued and screwed, no hole or strip between holes narrower "
            "than 1.5 in, corners rounded to 1/2 in.",
            "Then the panel someone stands on: round 1 1/2 in holes (a hole saw), small enough to step over, "
            "where it works least, one at a time. Solid, it's judged by the plate check. With holes the formula "
            "no longer applies: the rest of the panel is judged by the FEA, and each hole's edge by twice the "
            "stress the solid panel had there (a round hole in a plate in bending), both scaled up by however "
            "much the FEA read low against the plate check on the solid panel.",
            "Then thinner sheet, as an estimate from the lightest step that holds with the panel stood on still "
            "solid: that panel by the plate check at that thickness, the walls by their FEA scaled with the "
            "thickness. Use it to rebuild it in that sheet, and the strength check runs on the real thing.",
            "Every step is the FEA of the part with its holes in, on the voxel grid. It takes the joints as solid "
            "wood and doesn't check buckling, which these short, thick strips are far from. Once you cut a step "
            "in, the strength check runs again on the part as rebuilt, and that's the number to go by: a hole's "
            "edge is sensitive to where the grid falls, so it can read lower than its step did.",
        ],
    }
    with open(os.path.join(out_dir, "run.json"), "w") as f:
        json.dump(record, f, indent=2, default=str)
    best = max((x for x in stations if x["holds"] and not x.get("estimate")), key=lambda x: x["saved_lb"], default=None)
    store.append_history(part_id, {"kind": "lighten", "action": "studied", "run": rid,
                                   "stations": len(stations), "best_removed": best and best["removed"]})
    store.append_log({"kind": "lighten", "action": "studied", "part": part_id, "run": rid})
    emit("done", (f"{len(stations)} steps; the lightest that holds is {best['saved_lb']} lb lighter at "
                  f"{best['safety']}x") if best else "nothing lighter holds", run=rid, progress=1.0)
    return record


def _covered(p: dict, polys: list, s: float) -> np.ndarray:
    from shapely import contains_xy

    g = np.stack(np.meshgrid((np.arange(p["shape"][0]) + 0.5) * s + p["lo"][0],
                             (np.arange(p["shape"][1]) + 0.5) * s + p["lo"][1], indexing="ij"), -1)
    out = np.zeros(p["shape"], dtype=bool)
    for h in polys:
        out |= contains_xy(h, g[..., 0], g[..., 1])
    return out & p["inside"]


def _thinner(ctx, stations, tops, min_safety, density, C, M) -> list[dict]:
    """The lightest step that holds with the panel stood on still solid, in each thinner sheet that's sold:
    until (and including) the first that wouldn't hold. Estimates: the panel stood on by the plate check at
    that thickness, the walls by their FEA scaled with the thickness."""
    # from the lightest step that holds with the panel stood on still solid: there the plate check is exact at
    # any thickness, and holes in that panel save next to nothing for what they cost it
    base = max((x for x in stations if x["holds"] and not x.get("top_holes")), key=lambda x: x["saved_lb"],
               default=None)
    sheets = [pc for pc in ctx["pieces"] if pc["kind"] == "sheet"]
    if base is None or not sheets:
        return []
    t0 = max(pc["thickness"] for pc in sheets)
    wood_g = sum(pc["volume"] for pc in sheets) * density           # as it is now, with any holes it has
    out = []
    for t in sorted((x for x in C.THICKNESSES if x < t0 - 0.01), reverse=True):
        ratio = t / t0
        worst = None
        for c in base["cases"]:
            walls = (c.get("fea_safety") or 0) * ratio
            if c.get("governs") == "plate" and not base.get("top_holes"):
                pl = _plate_at(ctx, c["name"], t)
                top = pl if pl is not None else (c["safety"] or 0) * ratio ** 2
            else:
                top = (c["safety"] or 0) * ratio ** 2
            est = min(walls, top) if walls else top
            worst = est if worst is None else min(worst, est)
        saved = base["saved_lb"] + (wood_g / 453.59237 - base["saved_lb"]) * (1 - ratio)
        out.append({"phase": "thinner", "estimate": True, "thickness_mm": t, "label": M.nominal(t),
                    "removed": base["removed"], "holes": base["holes"], "top_holes": base.get("top_holes", 0),
                    "safety": round(worst, 2), "holds": worst >= min_safety, "saved_lb": round(saved, 2),
                    "from_step": base["index"], "cases": [], "panels": base["panels"]})
        if worst < min_safety:
            break
    return out


def _plate_at(ctx, case_name: str, t: float) -> Optional[float]:
    """The plate check's safety (grain the wrong way) for a load at another sheet thickness, if it has one."""
    i = next((k for k, ld in enumerate(ctx["loads"]) if ld["name"] == case_name), None)
    pl = L.plate_check(ctx["pieces"], ctx["loads"][i], ctx["mat"], ctx["tol"]) if i is not None else None
    if not pl or not pl.get("done"):
        return None
    return min(pl["by_thickness"], key=lambda b: abs(b["thickness_mm"] - t))["safety_across"]


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
    from . import holes as H

    rec = load_run(store, rid)
    if rec is None:
        raise FileNotFoundError(f"no lightening study {rid!r}")
    st = next((x for x in rec["stations"] if x["index"] == int(index)), None)
    if st is None:
        raise FileNotFoundError(f"study {rid} has no station {index}")
    if st.get("estimate"):
        raise ValueError(f"step {index} is an estimate in {st['label']} sheet: rebuild it in that sheet first")
    pid = rec["part"]
    holes = [{"piece": p["name"], "normal": p["normal"], "depth": p["thickness_mm"],
              "polygons": st["panels"].get(p["name"], [])} for p in rec["panels"] if st["panels"].get(p["name"])]
    script = store.read_script(pid)
    # a picture cut into a panel (CALI-78) stays; the lightening holes are this step's
    keep = [h for h in H.read(script) if h.get("picture")]
    script = H.write(script, keep + holes)
    version = store.write_part(pid, script, action="lighten",
                               feedback=f"lightened: {st['removed']:.0%} out of the walls, {st['holes']} holes, "
                                        f"{st['saved_lb']} lb lighter, {st['safety']}x",
                               extra={"lighten_run": rid, "station": int(index)})
    return {"version": version, "removed": st["removed"], "holes": st["holes"], "saved_lb": st["saved_lb"]}
