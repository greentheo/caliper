"""CALI-54 (#1) — will it hold? What a part says it must carry, checked two ways.

A part says what it must hold in ``loads()`` (an adult stepping up, a shelf of books) and where it's
held in ``held()`` (the floor, when it doesn't say). Caliper checks it two ways and goes by the worse:

- **whittle's voxel FEA** of the part as built, in the material its ``construction()`` names: a stress
  picture (where it works hardest), how far it gives, and a peak *beside* where the load and the floor
  attach (right at a contact, a voxel model reports the mesh, not the part). With about four voxels
  through a 3/4 in panel it's good for the picture and to perhaps ±50% on the number: the joints are
  solid wood to it, and a panel's edges come out partly clamped.
- **A plate check** for a sheet a load pushes on face-on and that rests on other pieces all round: the
  panel as a flat plate free to rotate at its edges (simply supported, the safe side of glued and
  screwed) with the load over its footprint at the middle, the worst place (Roark, Table 11.4).
  Plywood is about half as strong across its face grain, so it's said both ways, and the verdict
  takes the grain the wrong way.

The verdict is the lower safety factor at the load times its ``factor`` (2 for someone stepping onto
it), against ``min_safety``. Neither model checks the glue or the screws.
"""

from __future__ import annotations

import base64
import json
import math
import os
import time
import uuid
from typing import Callable, Optional

import numpy as np

from . import construction as C
from . import materials as M
from .design import DesignStore

LB = 4.4482216152605          # newtons per pound-force
GRAVITY = 9.80665
#: Voxels through the thinnest piece, if the part isn't so big that it would take too long.
VOXELS_THROUGH = 4
MAX_VOXELS = 150_000
MIN_SAFETY = 2.0
POISSON = 0.3
#: Roark Table 11.4, a rectangular plate simply supported on all edges, ν = 0.3, by a/b (long/short):
#: β for the stress under a load on a small central circle, α for the deflection there.
_AB = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 1e9]
_BETA = [0.435, 0.650, 0.789, 0.875, 0.927, 0.958, 1.000]
_ALPHA = [0.1267, 0.1478, 0.1621, 0.1714, 0.1769, 0.1803, 0.1851]
#: whittle's own figures, for a material Caliper's table has no mechanical properties for.
_WHITTLE_NAMES = {"steel": "steel", "plywood": "plywood", "xps": "xps", "aluminum": "aluminum"}


# ---------------------------------------------------------------------------
# What the part declares
# ---------------------------------------------------------------------------
def _box(item: dict, what: str) -> tuple[list[float], list[float]]:
    try:
        lo = [float(v) for v in item["lo"]]
        hi = [float(v) for v in item["hi"]]
    except KeyError as e:
        raise ValueError(f"{what} needs {e.args[0]!r}: the corners of the box it acts on") from None
    except (TypeError, ValueError):
        raise ValueError(f"{what}: lo and hi are (x, y, z) in mm") from None
    if len(lo) != 3 or len(hi) != 3:
        raise ValueError(f"{what}: lo and hi are (x, y, z) in mm")
    return [min(a, b) for a, b in zip(lo, hi)], [max(a, b) for a, b in zip(lo, hi)]


def parse_loads(items) -> list[dict]:
    """``loads()`` as Caliper uses it: name, the force (N, as declared) and factor, the box it acts on.
    Raises ValueError, naming the load, for anything it can't act on."""
    if not isinstance(items, (list, tuple)):
        raise ValueError("loads() returns a list of loads")
    out = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"load {i + 1} isn't a dict")
        name = str(item.get("name") or f"load {i + 1}")
        lo, hi = _box(item, f"'{name}'")
        if "force" in item:
            force = [float(v) for v in item["force"]]
            if len(force) != 3:
                raise ValueError(f"'{name}': force is (fx, fy, fz) in newtons")
        elif "lb" in item:
            force = [0.0, 0.0, -float(item["lb"]) * LB]
        elif "kg" in item:
            force = [0.0, 0.0, -float(item["kg"]) * GRAVITY]
        else:
            raise ValueError(f"'{name}' says where but not how much: give lb, kg or force")
        factor = float(item.get("factor", 1.0))
        if factor <= 0 or not math.isfinite(factor) or not any(force):
            raise ValueError(f"'{name}': the load and its factor must be more than nothing")
        out.append({"name": name, "force": force, "factor": factor, "lo": lo, "hi": hi,
                    "lb": round(float(np.linalg.norm(force)) / LB, 1)})
    return out


def parse_held(items, bounds, depth: float) -> list[dict]:
    """``held()``, or the floor: everything within ``depth`` of the part's underside."""
    if not items:
        (x0, y0, z0), (x1, y1, _) = bounds
        return [{"name": "the floor", "lo": [x0 - 1, y0 - 1, z0 - 1], "hi": [x1 + 1, y1 + 1, z0 + depth],
                 "default": True}]
    out = []
    for i, item in enumerate(items):
        name = str(item.get("name") or f"support {i + 1}")
        lo, hi = _box(item, f"'{name}'")
        out.append({"name": name, "lo": lo, "hi": hi})
    return out


def material(pieces: list[dict]) -> dict:
    """The one material the part is analysed in: what most of it is made of, by volume."""
    by = {}
    for pc in pieces:
        by[pc["material"]] = by.get(pc["material"], 0.0) + pc["volume"]
    if not by:
        raise ValueError("it doesn't say what it's built from (construction()), so there's no "
                         "material to analyse it in")
    key = max(by, key=by.get)
    table = M.SHEETS.get(key) or M.STICKS.get(key) or {}
    mech = table.get("mech")
    if mech:
        out = {"key": key, "name": table["name"], "E": mech["E"], "strength": mech["strength"],
               "density": table["density"] / 1000.0, "basis": mech.get("basis", "")}
    else:
        from whittle import MATERIALS

        w = MATERIALS.get(_WHITTLE_NAMES.get(key, key))
        if w is None:
            raise ValueError(f"the materials table has no strength for {key!r}")
        out = {"key": key, "name": table.get("name", w.name), "E": w.youngs_modulus,
               "strength": w.strength, "density": w.density, "basis": f"whittle's {w.name}"}
    # plywood is about half as strong across its face grain (see the materials table's basis)
    out["across"] = 0.5 if key == "plywood" else 1.0
    if len(by) > 1:
        out["note"] = (f"Analysed as all {out['name']} (most of it by volume); it's also "
                       + ", ".join(k for k in by if k != key) + ".")
    return out


def spacing_for(pieces: list[dict], volume: float, longest: float) -> tuple[float, Optional[str]]:
    """Voxel size: VOXELS_THROUGH across the thinnest piece, unless that's more voxels than a study
    should take; then as fine as MAX_VOXELS allows, and a note saying so."""
    thin = [pc["thickness"] for pc in pieces if pc["kind"] == "sheet"]
    thin += [2 * pc["half"] for pc in pieces if pc["kind"] == "stick"]
    want = min(thin) / VOXELS_THROUGH if thin else longest / 48
    floor = max((volume / MAX_VOXELS) ** (1 / 3), longest / 160)
    if want >= floor:
        return want, None
    return floor, (f"The voxels are {floor:.1f} mm, coarser than {VOXELS_THROUGH} across its thinnest "
                   f"piece ({min(thin):.1f} mm), to keep the study quick: read the FEA as a picture.")


# ---------------------------------------------------------------------------
# The plate check
# ---------------------------------------------------------------------------
def _interp(x: float, xs: list, ys: list) -> float:
    return float(np.interp(x, xs, ys))


def plate(a: float, b: float, t: float, force: float, footprint: float, E: float) -> dict:
    """A plate a × b (mm) × t, simply supported all round, a central load ``force`` (N) over
    ``footprint`` mm²: the peak stress (MPa) and the deflection (mm) under it. Roark, Table 11.4."""
    a, b = max(a, b), min(a, b)
    r0 = min(math.sqrt(max(footprint, 1.0) / math.pi), b / 2)
    if r0 < 0.5 * t:                        # the equivalent radius for a load on a small spot
        r0 = math.sqrt(1.6 * r0 ** 2 + t ** 2) - 0.675 * t
    beta, alpha = _interp(a / b, _AB, _BETA), _interp(a / b, _AB, _ALPHA)
    stress = 3 * force / (2 * math.pi * t ** 2) * ((1 + POISSON) * math.log(2 * b / (math.pi * r0)) + beta)
    return {"stress_mpa": stress, "deflection_mm": alpha * force * b ** 2 / (E * t ** 3)}


def _held_edges(pc: dict, k: int, others: list[dict], tol: float) -> int:
    """How many of a panel's edges another piece holds: one it butts against, or one under it (up to a
    fifth of the way in: a top that overhangs its sides by an inch still rests on them)."""
    from .consistency import _frame, segment_distance, slab_distance

    poly = pc["polys"][k]
    side, t = pc["sides"][k], pc["thickness"]
    o, u, v, n, flat = _frame(poly)
    centre = poly.mean(axis=0)
    held = 0
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        mid = (p + q) / 2
        inward = centre - mid
        inward -= (inward @ n) * n
        inward /= np.linalg.norm(inward) or 1.0
        reach = max(t, min(0.2 * float(((poly - mid) @ inward).max()), 100.0))
        probes = np.array([mid - inward * 2 * tol + side * n * t / 2]        # beside the edge
                          + [mid + inward * dist + side * n * (t + 2 * tol)  # under it
                             for dist in np.arange(t / 2, reach + 1e-6, t / 2)])
        for other in others:
            if other["kind"] == "sheet":
                d = min(slab_distance(probes, op, other["thickness"], s).min()
                        for op, s in zip(other["polys"], other["sides"]))
            else:
                d = float((segment_distance(probes, other["a"], other["b"]) - other["half"]).min())
            if d <= tol:
                held += 1
                break
    return held


def plate_check(pieces: list[dict], load: dict, mat: dict, tol: float) -> Optional[dict]:
    """The sheet a load pushes on face-on, checked as a plate — or None if it lands on no sheet, or on
    one that isn't held all round (the FEA is the number for that one)."""
    from .consistency import _frame, _inside2d

    lo, hi = np.asarray(load["lo"]), np.asarray(load["hi"])
    c = (lo + hi) / 2
    f = np.asarray(load["force"], float) * load["factor"]
    fmag = float(np.linalg.norm(f))
    for pc in pieces:
        if pc["kind"] != "sheet":
            continue
        for k, poly in enumerate(pc["polys"]):
            o, u, v, n, flat = _frame(poly)
            rel = c - o
            depth = abs(float((hi - lo) @ np.abs(n))) / 2
            if (abs(float(rel @ n)) > pc["thickness"] + depth + tol
                    or not _inside2d(np.array([[rel @ u, rel @ v]]), flat)[0]
                    or abs(float(f @ n)) < 0.7 * fmag):
                continue
            others = [x for x in pieces if x is not pc]
            edges = _held_edges(pc, k, others, tol)
            a, b = C.min_rect(flat.tolist())
            ext = hi - lo
            fu, fv = abs(float(ext @ np.abs(u))), abs(float(ext @ np.abs(v)))
            base = {"piece": pc["name"], "a_mm": round(a, 1), "b_mm": round(b, 1),
                    "edges": len(poly), "edges_held": edges, "footprint_mm": [round(fu, 1), round(fv, 1)]}
            if edges < len(poly) or len(poly) != 4:
                return {**base, "done": False,
                        "why": f"only {edges} of its {len(poly)} edges rest on another piece; the plate "
                               f"check covers a panel held all round, so the FEA is the number for it"}
            t = pc["thickness"]
            got = plate(a, b, t, float(abs(f @ n)), max(fu * fv, 1.0), mat["E"])
            safety = mat["strength"] / got["stress_mpa"]
            by_t = []
            for tt in C.THICKNESSES:
                if tt > 26:
                    continue
                g = plate(a, b, tt, float(abs(f @ n)), max(fu * fv, 1.0), mat["E"])
                by_t.append({"thickness_mm": tt, "label": M.nominal(tt),
                             "safety": round(mat["strength"] / g["stress_mpa"], 2),
                             "safety_across": round(mat["strength"] * mat["across"] / g["stress_mpa"], 2),
                             "deflection_mm": round(g["deflection_mm"], 3)})
            return {**base, "done": True, "thickness_mm": t, "stress_mpa": round(got["stress_mpa"], 2),
                    "safety": round(safety, 2), "safety_across": round(safety * mat["across"], 2),
                    "deflection_mm": round(got["deflection_mm"], 3), "by_thickness": by_t}
    return None


# ---------------------------------------------------------------------------
# The FEA, and the picture
# ---------------------------------------------------------------------------
def _grow(lo, hi, by: float):
    return (tuple(float(v) - by for v in lo), tuple(float(v) + by for v in hi))


def heat_mesh(mesh, grid, von_mises: np.ndarray, solid: np.ndarray, max_edge: float) -> dict:
    """The part's own surface, split finely enough to carry a stress per vertex: the worst of the voxels
    around each vertex. Base64 typed arrays, as three.js takes them."""
    import trimesh

    v, f = np.asarray(mesh.vertices), np.asarray(mesh.faces)
    for _ in range(6):
        try:
            v2, f2 = trimesh.remesh.subdivide_to_size(v, f, max_edge=max_edge, max_iter=12)
        except ValueError:
            v2, f2 = v, f
        if len(f2) <= 400_000:
            break
        max_edge *= 1.5
    v, f = v2, f2
    vm = np.where(solid, von_mises, 0.0)
    shape = np.asarray(vm.shape)
    low = np.floor((v - np.asarray(grid.origin)) / grid.spacing).astype(np.int64)
    heat = np.zeros(len(v))
    for corner in np.ndindex(2, 2, 2):
        cell = low + np.asarray(corner)
        ok = np.all((cell >= 0) & (cell < shape), axis=1)
        vals = np.zeros(len(v))
        cc = cell[ok]
        vals[ok] = vm[cc[:, 0], cc[:, 1], cc[:, 2]]
        heat = np.maximum(heat, vals)

    def b64(a):
        return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")

    return {"positions": b64(v.astype(np.float32)), "index": b64(f.astype(np.uint32)),
            "heat": b64(heat.astype(np.float32)), "max": float(heat.max()) if len(heat) else 0.0}


def _nearest_piece(point: np.ndarray, pieces: list[dict]) -> Optional[str]:
    from .consistency import segment_distance, slab_distance

    best = None
    for pc in pieces:
        if pc["kind"] == "sheet":
            d = min(float(slab_distance(point[None], p, pc["thickness"], s)[0])
                    for p, s in zip(pc["polys"], pc["sides"]))
        else:
            d = float(segment_distance(point[None], pc["a"], pc["b"])[0]) - pc["half"]
        if best is None or d < best[0]:
            best = (d, pc["name"])
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Running it, and keeping the results with the design
# ---------------------------------------------------------------------------
def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "loads")


def study(store: DesignStore, part_id: str, *, min_safety: float = MIN_SAFETY,
          emit: Optional[Callable] = None) -> dict:
    """Every load the part declares, through whittle's FEA and the plate check. Returns the run record."""
    from scipy import ndimage
    from whittle import LoadStudy, Material, Mesh

    from .consistency import _sides, shapes, tolerance

    emit = emit or (lambda *a, **k: None)
    t0 = time.time()
    declared = C.declared(store, part_id)
    if not declared.get("loads"):
        raise ValueError(f"'{part_id}' doesn't say what it must hold: its script has no loads()")
    loads = parse_loads(declared["loads"])
    mesh = store.part_geometry(part_id).require_mesh()
    if not mesh.is_watertight:
        raise ValueError(f"'{part_id}' isn't a closed solid, so it can't be voxelized")
    pieces = shapes(declared)
    mat = material(pieces)
    _sides(mesh, pieces)
    tol = tolerance(mesh)
    spacing, coarse = spacing_for(pieces, float(abs(mesh.volume)), float(max(mesh.extents)))
    held = parse_held(declared.get("held"), mesh.bounds.tolist(), max(spacing * 0.6, 1.0))

    emit("voxels", f"voxelizing '{part_id}' at {spacing:.1f} mm in {mat['name']}")
    wmat = Material(name=mat["name"], youngs_modulus=mat["E"], poisson_ratio=POISSON,
                    strength=mat["strength"], density=mat["density"])
    ls = LoadStudy(Mesh(np.asarray(mesh.vertices, float), np.asarray(mesh.faces)), material=wmat,
                   spacing=spacing)
    grow = spacing                        # a box on the surface still takes the voxels just under it
    try:
        for h in held:
            ls.support(box=_grow(h["lo"], h["hi"], grow))
    except ValueError:
        raise ValueError(f"'{h['name']}' doesn't touch the part — nothing holds it there")
    attach = np.zeros(ls.grid.shape, dtype=bool)
    for h in held:
        attach |= ls.region(box=_grow(h["lo"], h["hi"], grow))

    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out_dir = os.path.join(runs_dir(store), rid)
    os.makedirs(out_dir, exist_ok=True)
    cases = []
    for i, load in enumerate(loads):
        emit("case", f"{load['name']}: {load['lb']:g} lb × {load['factor']:g}", progress=i / len(loads))
        box = _grow(load["lo"], load["hi"], grow)
        ls.loads = []
        try:
            ls.load(tuple(float(v) * load["factor"] for v in load["force"]), box=box)
        except ValueError:
            raise ValueError(f"'{load['name']}' doesn't touch the part — it pushes on thin air")
        r = ls.analyze()
        case = {"name": load["name"], "lb": load["lb"], "factor": load["factor"],
                "force_n": [round(v, 1) for v in load["force"]], "lo": load["lo"], "hi": load["hi"]}
        if not r.supported:
            case.update({"holds": False, "safety": 0.0, "governs": "fea",
                         "fea": {"supported": False},
                         "why": "nothing connects where it's pushed to where it's held"})
            cases.append(case)
            continue
        near = ndimage.binary_dilation(attach | ls.region(box=box), iterations=1)
        judged = r.solid & ~near
        if judged.sum() < 20:
            judged = r.solid
        vm = np.where(judged, r.von_mises, 0.0)
        hot = np.unravel_index(int(np.argmax(vm)), vm.shape)
        at = np.asarray(ls.grid.origin) + ls.grid.spacing * np.asarray(hot)
        peak = float(vm[hot])
        fea = {"supported": True, "peak_mpa": round(peak, 2), "robust_mpa": round(float(r.peak_stress), 2),
               "safety": round(mat["strength"] / peak, 2) if peak > 0 else None,
               "deflection_mm": round(float(r.max_displacement), 3),
               "at": [round(float(x), 1) for x in at], "in": _nearest_piece(at, pieces)}
        pl = plate_check(pieces, load, mat, tol)
        options = [("fea", fea["safety"])]
        if pl and pl.get("done"):
            options.append(("plate", pl["safety_across"]))
        governs, safety = min(((k, s) for k, s in options if s is not None), key=lambda x: x[1],
                              default=("fea", None))
        case.update({"fea": fea, "plate": pl, "safety": safety, "governs": governs,
                     "holds": bool(safety is not None and safety >= min_safety),
                     # where it's predicted to break, placed the same way: linear to failure, as wood is
                     # close to; the joints aren't modelled and may go first
                     "breaks_lb": round(load["lb"] * load["factor"] * safety, -1) if safety else None})
        with open(os.path.join(out_dir, f"case_{i:02d}.json"), "w") as f:
            json.dump(heat_mesh(mesh, ls.grid, r.von_mises, r.solid, 2 * spacing), f)
        case["heat"] = f"case_{i:02d}.json"
        cases.append(case)

    notes = [
        f"{mat['name']}: E {mat['E']:g} MPa, strength {mat['strength']:g} MPa — {mat['basis']}.",
        "The FEA takes the joints as solid wood and its panel edges come out partly clamped, so it "
        "reads stiffer than glued-and-screwed; the plate check frees the edges, the safe side. Neither "
        "checks the glue or the screws.",
        "“Breaks at” is the load, placed the same way, at which the governing check reaches the "
        "material's strength: a prediction to test, not a rating.",
    ]
    if mat.get("note"):
        notes.append(mat["note"])
    if coarse:
        notes.append(coarse)
    if any(h.get("default") for h in held):
        notes.append("Held by the floor: everything at its underside, as if it stands on a flat floor.")
    worst = min((c["safety"] for c in cases if c.get("safety") is not None), default=None)
    record = {
        "id": rid, "part": part_id, "kind": "load", "created": time.time(),
        "version": store.design.part(part_id).version, "seconds": round(time.time() - t0, 1),
        "material": mat, "spacing_mm": round(spacing, 2), "voxels": int(ls.solid.sum()),
        "min_safety": min_safety, "held": held, "cases": cases, "notes": notes,
        "safety": worst, "holds": bool(cases) and all(c.get("holds") for c in cases),
    }
    with open(os.path.join(out_dir, "run.json"), "w") as f:
        json.dump(record, f, indent=2, default=str)
    store.append_history(part_id, {"kind": "load", "action": "studied", "run": rid,
                                   "cases": len(cases), "safety": worst, "holds": record["holds"]})
    store.append_log({"kind": "load", "action": "studied", "part": part_id, "run": rid})
    emit("done", f"{len(cases)} load(s) checked: "
         + ("it holds" if record["holds"] else "it doesn't hold") + (f", {worst:g}x" if worst else ""),
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


def heat_path(store: DesignStore, rid: str, index: int) -> str:
    if not rid or "/" in rid or ".." in rid:
        raise ValueError("bad run id")
    return os.path.join(runs_dir(store), rid, f"case_{int(index):02d}.json")
