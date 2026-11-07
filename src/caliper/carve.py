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

from . import verdicts
from .design import DesignStore
from .runs import newest_first

STATIONS = 7
REMOVE_UP_TO = 0.7
NAME = "CARVED"
#: A step whose shape doesn't close up isn't offered, and isn't adopted (CALI-117, #105): a part that isn't watertight
#: can't be voxelized, so the check adopting it runs fails or reads wrong.
OPEN = ("its carved shape doesn't close up into a solid (it isn't watertight), so it can't be built or checked: "
        "use another step, or carve it again")


class NotClosed(ValueError):
    """A carved step whose shape isn't watertight, even repaired."""


def _closed(mesh):
    """The mesh as it will be read back, closed: its holes filled if that closes it (trimesh's repair: small gaps,
    flipped faces), or None.

    Judged after merging its vertices, as any STL round trip does (#124 review, #105's cause): where two surfaces
    meet along an edge the carve leaves a pinch, two vertices at one point kept apart by index. That's watertight
    in memory, and once merged it isn't (four faces on one edge), so the study offered a step adopt then refused.
    A pinch isn't something a fill can mend: such a step is marked, not repaired."""
    import trimesh

    from .measure import closed

    m = mesh.copy()
    m.merge_vertices()
    if closed(m, volume=True):
        return m
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    trimesh.repair.fill_holes(m)
    trimesh.repair.fix_normals(m)
    return m if closed(m, volume=True) else None


def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "carves")


def study(store: DesignStore, part_id: str, *, min_safety: Optional[float] = None, stations: int = STATIONS,
          remove_up_to: float = REMOVE_UP_TO, emit: Optional[Callable] = None,
          stop: Optional[Callable[[], None]] = None) -> dict:
    """Carve the printed part down in steps, checking each; returns the run record.

    ``stop`` is called at every step boundary (in the sweep and between the checks) and raises
    :class:`caliper.jobs.Cancelled` to end the carve there (CALI-101): the record keeps the steps it finished, marked
    "cancelled"."""
    from scipy import ndimage
    from whittle import Load

    from . import construction as C
    from . import firstrun
    from . import load_study as L
    from . import materials as M

    from .jobs import Cancelled

    emit = emit or (lambda *a, **k: None)
    stop = stop or (lambda: None)
    min_safety = min_safety or firstrun._min_safety(store)
    t0 = time.time()
    ctx = L.prepare(store, part_id, emit)
    mat = ctx["mat"]
    seen = L.resolution(ctx)                     # can its voxels see the walls? (CALI-106, #101)
    if seen.get("too_thin"):                     # none a study may make can: not carved by strength
        raise ValueError(f"Can't carve it by strength: {seen['said']}" if seen.get("said") else L.TOO_THIN)
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
    # on disk from the start and after every step, so a run that dies (a crash, a restart) says how far it got
    # (CALI-103); it's marked done at the end
    partial = {"id": rid, "part": part_id, "kind": "carve", "created": time.time(), "status": "running",
               "version": store.design.part(part_id).version, "min_safety": min_safety, "material": mat["name"],
               "spacing_mm": round(s, 2), "steps": stations, "stations": [], "best": None, "weak": "",
               "share": "printed", "notes": [], **seen}

    def keep(rec: dict) -> None:
        with open(os.path.join(out_dir, "run.json.tmp"), "w") as fh:
            json.dump(rec, fh, indent=2, default=str)
        os.replace(os.path.join(out_dir, "run.json.tmp"), os.path.join(out_dir, "run.json"))

    keep(partial)
    out: list = []
    try:
        # one count everywhere (#102 review): n checks, as drawn and n - 1 carved; the panel says "step k of n"
        emit("carving", f"carving the printed {mat['name']} in {stations} steps (as drawn, then {stations - 1} carved)")
        def swept(f: float) -> None:
            stop()                                                     # a cancel lands here too (CALI-101)
            emit("carving", "", progress=round(0.7 * f, 3))

        sweep = ls.sweep(remove_up_to=remove_up_to, stations=stations, progress=swept)
        density = M.printed(mat["key"])["density"] / 1000.0           # g/cm³, solid
        voxel_cm3 = ls.grid.voxel_volume / 1000.0
        printed0 = voxels0 = None
        for k, st in enumerate(sweep.stations):
            stop()                                                     # between steps: what's done is kept
            # the share of the printed part: whittle's own `removed` counts the wood it keeps too (CALI-86)
            printed_voxels = float((st.design & ~wood).sum())
            voxels0 = printed_voxels if voxels0 is None else voxels0
            removed = 1.0 - printed_voxels / voxels0 if voxels0 else 0.0
            emit("checking", f"step {k}: {removed:.0%} of the printed part carved away",
                 progress=0.7 + 0.3 * k / len(sweep.stations))
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
            grams = printed_voxels * voxel_cm3 * density * mat["solid"]
            printed0 = grams if printed0 is None else printed0
            mesh = st.build()
            import trimesh

            tm = _station_mesh(mesh)
            f = f"station_{k:02d}.stl"
            fixed = _closed(tm)                                        # repaired if it can be; else not offered
            (fixed or tm).export(os.path.join(out_dir, f))
            holds = sides is not None and sides >= min_safety         # producer: the printed part, carved: what this is about
            out.append({"index": k, "removed": round(removed, 3), "safety": sides, "holds": holds,
                        "whole": worst, "whole_holds": worst is not None and worst >= min_safety, "weakest": weak,  # producer
                        "printed_g": round(grams), "saved_g": round(printed0 - grams), "stl": f,
                        **({} if fixed is not None else {"closed": False, "why": OPEN})})
            keep({**partial, "stations": out})
            if not holds and k > 0:
                break                                                  # the chart stops where it runs out
        best = _offer(store, part_id, out, out_dir, s)
        first = out[0]

        if verdicts.station(first, whole=True)["kind"] == "fails" and verdicts.station(first)["kind"] != "fails":
            # the part fails where the carve can't reach: say so first, it's the thing to fix
            weak_note = (f"As it is, it doesn't hold: {first['whole']:g} times over, and it needs {min_safety:g}; the "
                         f"weak link is the {first['weakest'] or 'wood'}, which carving the printed part doesn't change.")
        else:
            weak_note = ""
        record = {"id": rid, "part": part_id, "kind": "carve", "created": time.time(), **seen,
                  "version": store.design.part(part_id).version, "min_safety": min_safety,
                  "material": mat["name"], "spacing_mm": round(s, 2), "seconds": round(time.time() - t0, 1),
                  "stations": out, "best": best["index"] if best else None, "weak": weak_note,
                  "share": "printed",                     # removed is the printed part's share (CALI-86); older runs: the solid's
                  "status": "done", "steps": stations,
                  "notes": [*([weak_note] if weak_note else []),
                            "The safety on the chart is the printed part's own; the whole part's is beside it.",
                            f"Carved by whittle's sweep, {mat['name']} only: the "
                            + ("wood, " if wood.any() else "") + "where it's pushed and where it's held are kept.",
                            "Each step is checked by the strength check; using one rebuilds the part with that shape "
                            "and checks it again: that's the number to go by.", *([mat["note"]] if mat.get("note") else [])]}
        keep(record)
        store.append_history(part_id, {"kind": "carve", "action": "studied", "run": rid, "stations": len(out)})
        store.append_log({"kind": "carve", "action": "studied", "part": part_id, "run": rid})
        from . import consistency

        v = verdicts.carve_step(best, consistency.filled(store, part_id), record) if best is not None else None
        why = ("too coarse to see its walls" if v and v["kind"] in ("unresolved", "unchecked")    # #101
               else "the whole part doesn't hold" if v and v["kind"] == "fails" else v["word"] if v else "")
        emit("done", f"{len(out)} steps: the lightest that holds saves {best['saved_g']} g"
             if v and v["counts_as_pass"] and best["saved_g"]
             else f"{len(out)} steps: the printed part comes off, but {why}"   # #132 review
             if best is not None and best["saved_g"] else f"{len(out)} steps", run=rid, progress=1.0)
        return record
    except Cancelled:
        # asked to stop (CALI-101): the steps it finished, and the lightest of them that holds, as a partial run
        # the lightest step whose printed part holds and closes up, as its verdict says (#132, #124)
        best = max((x for x in out if verdicts.station(x)["counts_as_pass"]), key=lambda x: x["saved_g"], default=None)
        keep({**partial, "stations": out, "status": "cancelled", "best": best["index"] if best else None,
              "seconds": round(time.time() - t0, 1)})
        store.append_history(part_id, {"kind": "carve", "action": "cancelled", "run": rid, "stations": len(out)})
        raise
    except BaseException as e:
        # a carve that fails says so, with what it finished: it doesn't read "not finished" forever (CALI-103)
        keep({**partial, "stations": out, "status": "failed", "error": f"{type(e).__name__}: {e}"})
        raise


def _station_mesh(mesh):
    """whittle's mesh of a step, as trimesh (one place, so a test can hand it a leaky one)."""
    import trimesh

    return trimesh.Trimesh(np.asarray(mesh.vertices, float), np.asarray(mesh.faces, int), process=True)


def _offer(store: DesignStore, part_id: str, out: list, out_dir: str, spacing: float) -> Optional[dict]:
    """The step to offer: the lightest that holds and whose part, as adopting it would build it, closes up. One that
    doesn't is marked (``closed: False``, with why) and the next lightest is tried. The part's script is built
    once for all of them (#124 review)."""
    from . import sandbox

    built = None
    for x in sorted((x for x in out if verdicts.station(x)["counts_as_pass"]), key=lambda x: -x["saved_g"]):
        if built is None:
            built = sandbox.run_script(strip(store.read_script(part_id)), timeout=120)
            if not built.ok:
                raise ValueError(f"'{part_id}' won't build to carve: {built.error}")
        try:
            _adopted(store, part_id, os.path.join(out_dir, x["stl"]), spacing, built=built)
            return x
        except NotClosed:
            x.update({"closed": False, "why": OPEN})
    return None


def _join(exact, printed):
    """The wood as drawn and the printed rest as carved, one solid (manifold3d's union)."""
    import trimesh

    if not len(printed.faces) or not len(exact.faces):
        return trimesh.util.concatenate([exact, printed])
    return exact.union(printed, engine="manifold")


def _adopted(store: DesignStore, pid: str, station_file: str, spacing: float, built=None):
    """The part a step would become: the wood exactly as the script makes it, the printed rest as carved. Closed up,
    or :class:`NotClosed` (CALI-117)."""
    import trimesh

    from . import construction as C
    from . import sandbox
    from .occt import OCCT

    station = _closed(trimesh.load(station_file, force="mesh"))
    if station is None:
        raise NotClosed(OPEN)
    if built is None:
        built = sandbox.run_script(strip(store.read_script(pid)), timeout=120)
        if not built.ok:
            raise ValueError(f"'{pid}' won't build to carve: {built.error}")
    whole = built.geometry.require_mesh()
    wood = C.wood_solids(built.declared or {}, whole)
    if not wood:
        return station
    cut = trimesh.util.concatenate(wood)
    # the carve kept the wood's voxels, half a voxel proud of it: trim that lip off its edges and outside,
    # and leave its inner face exact so the carved part stays joined to it
    lip = trimesh.util.concatenate(C.wood_solids(built.declared or {}, whole, proud=float(spacing), inner=False))
    with OCCT:                                       # manifold3d, one boolean at a time
        exact = whole.intersection(cut, engine="manifold")
        printed = station.difference(lip, engine="manifold")
        shape = _closed(_join(exact, printed))
    if shape is None:
        raise NotClosed(OPEN)
    return shape


def share(rec: dict) -> str:
    """What a run's "removed" is a share of, in words: a run saved before CALI-86 counted the whole solid, wood and
    all, and keeps that meaning; it's said, never relabelled."""
    return ("of the printed part" if rec.get("share") == "printed"
            else "of the whole solid (carved before CALI-86: carve again for the printed share)")


def list_runs(store: DesignStore, part_id: Optional[str] = None) -> list[dict]:
    root = runs_dir(store)
    if not os.path.isdir(root):
        return []
    out = []
    for rid in sorted(os.listdir(root), reverse=True):
        rec = load_run(store, rid)
        if rec and (part_id is None or rec["part"] == part_id):
            out.append(rec)
    return newest_first(out)          # made last first, not by id (CALI-97)


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


class Stale(ValueError):
    """A run of an older version of the part than the one there is."""


def adopt(store: DesignStore, rid: str, index: int) -> dict:
    """Make a step's shape the part's: the wood exactly as the script makes it, the printed rest as carved."""
    import trimesh

    rec = load_run(store, rid)
    if rec is None:
        raise FileNotFoundError(f"no carve {rid!r}")
    pid = rec["part"]
    entry = store.design.part(pid)
    if entry is None:
        raise FileNotFoundError(f"no part {pid!r}")
    if rec.get("version") != entry.version:          # a carve is of one version's shape (CALI-87)
        raise Stale(f"this carve is of version {rec.get('version')} and the part is at version {entry.version}: "
                    f"carve it again")
    st = next((x for x in rec["stations"] if x["index"] == int(index)), None)
    if st is not None and st.get("closed") is False:
        raise NotClosed(f"step {int(index)}: {OPEN}")
    script = strip(store.read_script(pid))
    try:
        shape = _adopted(store, pid, station_path(store, rid, index), float(rec["spacing_mm"]))
    except NotClosed:
        raise NotClosed(f"step {int(index)}: {OPEN}") from None
    name = f"carved-{rid}-{int(index):02d}.stl"
    folder = os.path.join(store.part_dir(pid), "carved")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    shape.export(path)
    from .measure import closed

    if not closed(trimesh.load(path, force="mesh")):             # as the part will be read back: never a leaky part
        os.remove(path)
        raise NotClosed(f"step {int(index)}: {OPEN}")
    st = next(x for x in rec["stations"] if x["index"] == int(index))
    script = script.rstrip("\n") + (f"\n\n\n# The printed rest as carved by the strength study (CALI-82): Caliper builds the "
                                    f"part as this mesh.\n{NAME} = \"{name}\"\n")
    version = store.write_part(pid, script, action="carve",
                               feedback=f"carved: {st['removed']:.0%} of the printed part out, {st['saved_g']} g "
                                        f"lighter, {st['safety']}x",
                               extra={"carve_run": rid, "station": int(index)})
    return {"version": version, "removed": st["removed"], "saved_g": st["saved_g"], "file": name}


#: What a revision that dropped the carve says (CALI-87: one rule for every writer of a part's script).
DROPPED = "The carve came off with this change (it was cut to the old shape): carve it again."
_LINE = re.compile(r"^" + NAME + r"\s*=", re.M)


def carved(script: str) -> bool:
    return bool(_LINE.search(script or ""))


def uncarve(script: str) -> tuple[str, bool]:
    """A revision of a part changes the shape its carve was cut from: the script without the carve, and whether
    there was one. Every writer that changes build() or its declarations goes through this."""
    return (strip(script), True) if carved(script) else (script, False)


def refuse_if_carved(script: str, what: str, then: str) -> None:
    """A picture or lightening would cut through the carving: refused until the carve is off (CALI-87). ``what`` is
    what would cut ("a T-rex", "holes"), ``then`` how to ask again ("put the T-rex on"). "Roll it back" is the chat's
    word for taking the last change off (chat._REVERT)."""
    if carved(script):
        raise ValueError(f"it's been carved, and {what} would cut through the carving. Say \"roll it back\" to take the "
                         f"carve off, {then}, then carve it again")


def strip(script: str) -> str:
    """The script without its carve (a revision changes what was carved)."""
    return re.sub(r'\n*(?:# The printed rest as carved[^\n]*\n)?' + NAME + r'\s*=\s*["\'][^"\']*["\']\n?', "\n",
                  script).rstrip("\n") + "\n"
