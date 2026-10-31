"""CALI-82 (#54), slice 3 — carve a printed part where it isn't working, every step checked.

Theo's stool: "a plywood top and printed sides, since the sides would work in compression and we could
whittle them down more interestingly". Plywood is cut with a jigsaw, so lightening it keeps to holes a saw
can follow (CALI-71). A printer makes any shape, so its part can be carved free-form: whittle's sweep takes
material out where the strain energy says it isn't working, in steps, opening through wherever the physics
says. It keeps the plywood (or any declared sheet or stick), where the part is pushed and where it's held.

Each step is checked by the strength check (in both materials, CALI-82 slice 2) against the safety the part
must have, and the chart runs down until a step doesn't hold. Using a step writes its shape as the part's: the
plywood exactly as the script makes it, the printed rest as carved and smoothed, kept in the part's
``carved/`` folder and named in the script (``CARVED``). A revision through the chat after that drops the
carve (it no longer fits) and says so.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Callable, Optional

import numpy as np

from .design import DesignStore

STATIONS = 7
REMOVE_UP_TO = 0.7
NAME = "CARVED"


def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "carves")


def study(store: DesignStore, part_id: str, *, min_safety: Optional[float] = None, stations: int = STATIONS,
          remove_up_to: float = REMOVE_UP_TO, emit: Optional[Callable] = None) -> dict:
    """Carve the printed part down in steps, checking each; returns the run record."""
    from scipy import ndimage
    from whittle import Load

    from . import construction as C
    from . import firstrun
    from . import load_study as L
    from . import materials as M

    emit = emit or (lambda *a, **k: None)
    min_safety = min_safety or firstrun._min_safety(store)
    t0 = time.time()
    ctx = L.prepare(store, part_id, emit)
    mat = ctx["mat"]
    if not mat.get("printed"):
        raise ValueError(f"'{part_id}' isn't printed: only a printed part (or the printed rest of one) can be "
                         f"carved free-form; a sheet is lightened with holes a saw can cut")
    ls, s = ctx["ls"], ctx["spacing"]
    # each load its own case, as the strength check takes them
    ls.loads = [Load(ls.region(box=box), tuple(float(v) * load["factor"] for v in load["force"]), case=i)
                for i, (load, box) in enumerate(zip(ctx["loads"], ctx["boxes"]))]
    printed_strength = mat["strength"]
    wood = (ctx["strength_map"] != printed_strength) & ls.solid if ctx.get("strength_map") is not None \
        else np.zeros(ls.grid.shape, dtype=bool)
    ls.protected = ls.protected | wood | ndimage.binary_dilation(ctx["attach"], iterations=1)
    lo, hi = ls.grid.origin, np.asarray(ls.grid.origin) + s * np.asarray(ls.grid.shape)
    ls.whittle(box=(tuple(float(v) for v in lo), tuple(float(v) for v in hi)))   # any printed surface may open

    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out_dir = os.path.join(runs_dir(store), rid)
    os.makedirs(out_dir, exist_ok=True)
    emit("carving", f"carving the printed {mat['name']} in {stations - 1} steps")
    sweep = ls.sweep(remove_up_to=remove_up_to, stations=stations,
                     progress=lambda f: emit("carving", "", progress=round(0.7 * f, 3)))
    density = M.printed(mat["key"])["density"] / 1000.0           # g/cm³, solid
    voxel_cm3 = ls.grid.voxel_volume / 1000.0
    printed0 = None
    out = []
    for k, st in enumerate(sweep.stations):
        emit("checking", f"step {k}: {st.removed:.0%} of it carved away", progress=0.7 + 0.3 * k / len(sweep.stations))
        worst, sides, weak = None, None, None
        for i in range(len(ctx["loads"])):
            case, r = L.check_load(ctx, i, min_safety, solid=st.design)
            if case.get("safety") is not None and (worst is None or case["safety"] < worst):
                worst, weak = case["safety"], (case.get("plate") or {}).get("piece") if case["governs"] == "plate" \
                    else case["fea"].get("in")
            if r.supported:                                    # the printed part's own: what the carve changes
                judged = r.solid & ~wood & ~ndimage.binary_dilation(ctx["attach"], iterations=1)
                worked = float((r.von_mises[judged] / printed_strength).max()) if judged.any() else 0.0
                mine = round(1.0 / worked, 2) if worked > 0 else None
                sides = mine if sides is None or (mine is not None and mine < sides) else sides
            else:
                sides = 0.0
        printed_voxels = float((st.design & ~wood).sum())
        grams = printed_voxels * voxel_cm3 * density * mat["solid"]
        printed0 = grams if printed0 is None else printed0
        mesh = st.build()
        import trimesh

        tm = trimesh.Trimesh(np.asarray(mesh.vertices, float), np.asarray(mesh.faces, int), process=True)
        f = f"station_{k:02d}.stl"
        tm.export(os.path.join(out_dir, f))
        holds = sides is not None and sides >= min_safety         # the printed part, carved: what this is about
        out.append({"index": k, "removed": round(float(st.removed), 3), "safety": sides, "holds": holds,
                    "whole": worst, "whole_holds": worst is not None and worst >= min_safety, "weakest": weak,
                    "printed_g": round(grams), "saved_g": round(printed0 - grams), "stl": f})
        if not holds and k > 0:
            break                                                  # the chart stops where it runs out
    best = max((x for x in out if x["holds"]), key=lambda x: x["saved_g"], default=None)
    first = out[0]
    if not first["whole_holds"] and first["holds"]:
        # the part fails where the carve can't reach: say so first, it's the thing to fix
        weak_note = (f"As it is, it doesn't hold: {first['whole']:g} times over, and it needs {min_safety:g}; the "
                     f"weak link is the {first['weakest'] or 'wood'}, which carving the printed part doesn't change.")
    else:
        weak_note = ""
    record = {"id": rid, "part": part_id, "kind": "carve", "created": time.time(),
              "version": store.design.part(part_id).version, "min_safety": min_safety,
              "material": mat["name"], "spacing_mm": round(s, 2), "seconds": round(time.time() - t0, 1),
              "stations": out, "best": best["index"] if best else None, "weak": weak_note,
              "notes": [*([weak_note] if weak_note else []),
                        "The safety on the chart is the printed part's own; the whole part's is beside it.",
                        f"Carved by whittle's sweep, {mat['name']} only: the "
                        + ("wood, " if wood.any() else "") + "where it's pushed and where it's held are kept.",
                        "Each step is checked by the strength check; using one rebuilds the part with that shape "
                        "and checks it again: that's the number to go by.", *([mat["note"]] if mat.get("note") else [])]}
    with open(os.path.join(out_dir, "run.json"), "w") as fh:
        json.dump(record, fh, indent=2, default=str)
    store.append_history(part_id, {"kind": "carve", "action": "studied", "run": rid, "stations": len(out)})
    store.append_log({"kind": "carve", "action": "studied", "part": part_id, "run": rid})
    emit("done", f"{len(out)} steps: the lightest that holds saves {best['saved_g']} g" if best and best["saved_g"]
         else f"{len(out)} steps", run=rid, progress=1.0)
    return record


def list_runs(store: DesignStore, part_id: Optional[str] = None) -> list[dict]:
    root = runs_dir(store)
    if not os.path.isdir(root):
        return []
    out = []
    for rid in sorted(os.listdir(root), reverse=True):
        rec = load_run(store, rid)
        if rec and (part_id is None or rec["part"] == part_id):
            out.append(rec)
    return out


def load_run(store: DesignStore, rid: str) -> Optional[dict]:
    if not rid or "/" in rid or ".." in rid:
        return None
    p = os.path.join(runs_dir(store), rid, "run.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def station_path(store: DesignStore, rid: str, index: int) -> str:
    rec = load_run(store, rid)
    if rec is None:
        raise FileNotFoundError(f"no carve {rid!r}")
    st = next((x for x in rec["stations"] if x["index"] == int(index)), None)
    if st is None:
        raise FileNotFoundError(f"carve {rid} has no step {index}")
    return os.path.join(runs_dir(store), rid, st["stl"])


def adopt(store: DesignStore, rid: str, index: int) -> dict:
    """Make a step's shape the part's: the wood exactly as the script makes it, the printed rest as carved."""
    import trimesh

    from . import construction as C
    from . import sandbox

    rec = load_run(store, rid)
    if rec is None:
        raise FileNotFoundError(f"no carve {rid!r}")
    pid = rec["part"]
    station = trimesh.load(station_path(store, rid, index), force="mesh")
    script = strip(store.read_script(pid))
    built = sandbox.run_script(script, timeout=120)
    if not built.ok:
        raise ValueError(f"'{pid}' won't build to carve: {built.error}")
    whole = built.geometry.require_mesh()
    wood = C.wood_solids(built.declared or {}, whole)
    from .occt import OCCT

    if wood:
        cut = trimesh.util.concatenate(wood)
        # the carve kept the wood's voxels, half a voxel proud of it: trim that lip off its edges and outside,
        # and leave its inner face exact so the carved part stays joined to it
        lip = trimesh.util.concatenate(C.wood_solids(built.declared or {}, whole, proud=float(rec["spacing_mm"]),
                                                     inner=False))
        with OCCT:                                       # manifold3d, one boolean at a time
            exact = whole.intersection(cut, engine="manifold")
            printed = station.difference(lip, engine="manifold")
            shape = trimesh.util.concatenate([exact, printed]) if not len(printed.faces) or not len(exact.faces) \
                else exact.union(printed, engine="manifold")
    else:
        shape = station
    name = f"carved-{rid}-{int(index):02d}.stl"
    folder = os.path.join(store.part_dir(pid), "carved")
    os.makedirs(folder, exist_ok=True)
    shape.export(os.path.join(folder, name))
    st = next(x for x in rec["stations"] if x["index"] == int(index))
    script = script.rstrip("\n") + (f"\n\n\n# The printed rest as carved by the strength study (CALI-82): Caliper builds the "
                                    f"part as this mesh.\n{NAME} = \"{name}\"\n")
    version = store.write_part(pid, script, action="carve",
                               feedback=f"carved: {st['removed']:.0%} of the printed part out, {st['saved_g']} g "
                                        f"lighter, {st['safety']}x",
                               extra={"carve_run": rid, "station": int(index)})
    return {"version": version, "removed": st["removed"], "saved_g": st["saved_g"], "file": name}


def strip(script: str) -> str:
    """The script without its carve (a revision changes what was carved)."""
    return re.sub(r'\n*(?:# The printed rest as carved[^\n]*\n)?' + NAME + r'\s*=\s*["\'][^"\']*["\']\n?', "\n",
                  script).rstrip("\n") + "\n"
