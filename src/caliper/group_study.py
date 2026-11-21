"""CALI-36 (#17) slice E: a group's own "Will it work?" (Theo: "yes check the box on the platform").

The load study (:mod:`caliper.load_study`), run over a group's parts as one solid. Only its setup is new
(:func:`prepare_group`, beside :func:`caliper.load_study.prepare`); every check after it is the part study's own
(:func:`~caliper.load_study.check_load`, the plate check, buckling, the verdicts). The foreman's OK on #17:

- **A group that mounts on another** is checked with it, held where that one is held: the box's cases go through the
  platform to what the platform stands on. A group that mounts on nothing is checked alone.
- **Its cases** are its own parts' strength loads (the person's edits included), one at a time, named by part. Every
  load, support and piece is posed from its part's own frame into the design's (``store.part_pose``).
- **Its supports** are its parts' own, posed; one that lands on another part of the solid is the union's to carry, so
  it's dropped. A part marked ``fixed`` is the surroundings: never in the solid, and a support on it stays.
- **Each piece is its own material** (#348), over every part. The solid is each part voxelized on one grid, together:
  one part's mesh never cancels another's where they overlap.
- **Its run** is kept on the group (``group_loads/``), never in a part's runs, with each part's version: stale when any
  of them changes.
- **Its own weight isn't a load here** (the load study has none), said on every run until Theo says what a camper on
  the road carries (#17, the foreman).

Not in E1, said: the joints where two parts meet (E2: until then taken as one solid, on the verdict's note, as a part's
joints were before #301), the skins of a sandwich panel (#351), a printed part."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Callable, Optional

import numpy as np

from . import construction as C
from . import load_study as L
from .design import DesignStore
from .errors import scrubbed
from .runs import newest_first

#: Said on every group run until Theo says what a camper on the road carries (#17, the foreman's question 2).
OWN_WEIGHT = "Its own weight isn't a load here: only the loads its parts declare are checked."
#: Where two parts meet, until E2 reads the joints between them.
MEET = "Where its parts meet is taken as one solid: the joints between parts aren't checked yet."


def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "group_loads")


def _parts_of(store: DesignStore, gid: str) -> tuple[list[str], list[str]]:
    """The group's own parts, and the parts of what it mounts on, followed down (two deep at most, as A allows): ``(own,
    under)``. Raises ValueError, in words, for a name that isn't a group."""
    from .plan import group_parts

    groups = store.design.groups or []
    by = {g["id"]: g for g in groups}
    if gid not in by:
        raise ValueError(f"there's no group {gid!r} in this design's plan")
    if store.design.part(gid) is not None:
        raise ValueError(f"{gid} names both a part and a group: rename the part")
    own = group_parts(groups, gid)
    under, todo, seen = [], list(by[gid].get("mounts_on") or []), {gid}
    while todo:
        at = todo.pop(0)
        if at in seen:
            continue
        seen.add(at)
        if at in by:
            under += [p for p in group_parts(groups, at) if p not in own and p not in under]
            todo += list(by[at].get("mounts_on") or [])
        elif at not in own and at not in under:
            under.append(at)
    return own, under


def _pt(M: np.ndarray, p) -> np.ndarray:
    p = np.asarray(p, float)
    return p @ M[:3, :3].T + M[:3, 3]


def pose_box(lo, hi, M: np.ndarray) -> tuple[list, list, bool]:
    """A box in a part's own frame, in the design's: the box round its posed corners, and whether a turn other than a
    quarter one made it bigger than it was (said where it's used)."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    got = _pt(M, corners)
    R = M[:3, :3]
    turned = not np.allclose(np.abs(R), np.round(np.abs(R)), atol=1e-6)
    return got.min(axis=0).tolist(), got.max(axis=0).tolist(), bool(turned)


def pose_load(ld: dict, M: np.ndarray, pid: str) -> dict:
    """One of a part's loads, as :func:`caliper.load_study.parse_loads` gives it, in the design's frame: its box and its
    force turned with the part, named by it."""
    lo, hi, turn = pose_box(ld["lo"], ld["hi"], M)
    force = (np.asarray(ld["force"], float) @ M[:3, :3].T).tolist()
    return {**ld, "name": f"{pid}: {ld['name']}", "part": pid, "lo": lo, "hi": hi, "force": force,
            **({"turned": True} if turn else {})}


def _pose_piece(pc: dict, M: np.ndarray, pid: str) -> dict:
    """A part's piece, its sides already found in its own frame (a proper turn keeps them), posed, keyed by its part."""
    out = {**pc, "part": pid, "name": f"{pid}'s {pc['name']}", "own_name": pc["name"], "key": f"{pid}'s {pc['key']}"}
    for k in ("polys", "holes", "pictures", "mids"):
        if pc.get(k) is not None:
            out[k] = [_pt(M, p) for p in pc[k]]
    for k in ("a", "b"):
        if pc.get(k) is not None:
            out[k] = _pt(M, pc[k])
    return out


#: A joint's points and directions, as :func:`caliper.joint_check.setup` gives them in its part's own frame.
_JOINT_POINTS, _JOINT_DIRS = ("mid",), ("out", "normal", "along", "axis")
_JOINT_KEYS = ("edge", "face", "host", "piece")


def _pose_joint(j: dict, M: np.ndarray, pid: str) -> dict:
    """One of a part's joints, posed into the design's frame and keyed by its part, as its pieces are."""
    R = M[:3, :3]
    out = {**j, "part": pid, "pieces": [f"{pid}'s {k}" for k in j["pieces"]]}
    for k in _JOINT_POINTS:
        if j.get(k) is not None:
            out[k] = _pt(M, j[k])
    for k in _JOINT_DIRS:
        if j.get(k) is not None:
            out[k] = np.asarray(j[k], float) @ R.T
    for k in _JOINT_KEYS:
        if j.get(k) is not None:
            out[k] = f"{pid}'s {j[k]}"
    if j.get("points"):
        out["points"] = [_pt(M, p) for p in j["points"]]
    if j.get("faces"):
        out["faces"] = [{**f, "normal": np.asarray(f["normal"], float) @ R.T} for f in j["faces"]]
    if j.get("top_z") is not None and j.get("mid") is not None:   # the notch's top, as high as it was over its middle
        out["top_z"] = float(out["mid"][2] + (j["top_z"] - float(np.asarray(j["mid"], float)[2])))
    return out


def prepare_group(store: DesignStore, gid: str, emit: Optional[Callable] = None,
                  spacing: Optional[float] = None) -> dict:
    """What a strength check of a group needs, as :func:`caliper.load_study.prepare` gives a part's: the same keys, so
    :func:`caliper.load_study.check_load` runs on it unchanged. Raises ValueError, in words, where it can't be checked."""
    import trimesh
    from whittle import LoadStudy, Material, Mesh
    from whittle.voxel import Grid

    from . import fasteners
    from . import joint_check as JC
    from . import scenarios as SC
    from .consistency import _sides, shapes, tolerance
    from .measure import closed, open_near

    emit = emit or (lambda *a, **k: None)
    own, under = _parts_of(store, gid)
    fixed = {p.id for p in store.assembly.parts if p.role == "fixed"}
    solid_ids = [p for p in own + under if p not in fixed]
    unbuilt = [p for p in solid_ids if not (store.design.part(p) and store.design.part(p).version)]
    if unbuilt:
        raise ValueError(f"waits for {' and '.join(unbuilt)} to be built")
    parts: dict = {}
    for pid in solid_ids:
        script = store.read_script(pid) if store.is_scripted(pid) else ""
        if "def members(" in script:
            raise ValueError(f"the {pid} is a frame of members: its frame study checks it, not this one")
        try:
            declared = C.declared(store, pid)
            local = store.part_local(pid).require_mesh()
        except Exception as e:  # noqa: BLE001 — the part didn't build: the group isn't checked, and says which
            raise ValueError(f"the {gid} isn't checked: the {pid} didn't build ({scrubbed(e)})")
        if not closed(local):
            raise ValueError(f"the {pid} isn't checked: its shape isn't closed {open_near(local)}")
        if any(isinstance(it, dict) and it.get("kind") == "printed" for it in declared.get("construction") or []):
            raise ValueError(f"the {pid} has printed pieces: a group with a printed part isn't checked as one yet")
        pieces = shapes(declared)
        fasteners.keys(pieces)
        said = (store.design.grain or {}).get(pid) or {}
        for pc in pieces:
            if pc["kind"] == "sheet":
                pc["grain"] = (said.get(pc["name"]) or {}).get("grain")
        _sides(local, pieces)
        thins, walls, where, found = L._thin(declared, local, pieces)
        M = np.asarray(store.part_pose(pid), float)
        joints = None
        if len([pc for pc in pieces if pc.get("material") in ("plywood", "lumber")]) > 1:   # its own, by hand (#301)
            try:
                joints = JC.setup(store, pid)
            except Exception:  # noqa: BLE001 — not read: not checked, and said, as a part's own check does
                joints = "unread"
        parts[pid] = {"declared": declared, "local": local, "M": M, "pieces": pieces, "joints": joints,
                      "mesh": local.copy().apply_transform(M), "thins": thins, "walls": walls, "where": where,
                      "found": found}

    loads, turned = [], []
    for pid in own:
        if pid not in parts:
            continue
        for ld in L.parse_loads(SC.loads(store, pid, parts[pid]["declared"])):
            loads.append(pose_load(ld, parts[pid]["M"], pid))
            if loads[-1].get("turned"):
                turned.append(loads[-1]["name"])
    if not loads:
        raise ValueError(f"the {gid} doesn't say what it must hold: none of its parts has loads()")

    mesh = trimesh.util.concatenate([parts[p]["mesh"] for p in solid_ids])
    pieces = [_pose_piece(pc, parts[p]["M"], p) for p in solid_ids for pc in parts[p]["pieces"]]
    wood = [pc for pc in pieces if pc["kind"] in ("sheet", "stick")]
    mat = L.material(wood) if wood else L.material(pieces)
    tol = tolerance(mesh)
    thins = [t for p in solid_ids for t in parts[p]["thins"]]
    walls = min((parts[p]["walls"] for p in solid_ids if parts[p]["walls"] is not None), default=None)
    thinnest_at = min(solid_ids, key=lambda p: min(parts[p]["thins"]) if parts[p]["thins"] else float("inf"))
    where = dict(parts[thinnest_at]["where"] or {})
    if where.get("piece"):
        where["piece"] = f"{thinnest_at}'s {where['piece']}"
    if where.get("at") is not None:
        where["at"] = _pt(parts[thinnest_at]["M"], where["at"]).tolist()
    volume = float(sum(abs(parts[p]["local"].volume) for p in solid_ids))
    longest = float(max(mesh.extents))
    least = L.finest(volume, longest, L.FINER_BUDGET)
    if spacing is None:
        spacing, coarse = L.spacing_for(pieces, volume, longest, walls)
    elif spacing < least:
        coarse = (f"Asked for {spacing:g} mm voxels, finer than a study of a group this size may take: it ran at "
                  f"{least:.2f} mm.")
        spacing = least
    else:
        coarse = None

    # its supports: each part's own, posed; one landing on another part of the solid is the union's to carry
    rch = L.reach(tol, spacing)
    held = []
    for pid in solid_ids:
        p = parts[pid]
        for h in L.parse_held(SC.held(store, pid, p["declared"]), p["local"].bounds.tolist(), max(spacing * 0.6, 1.0)):
            lo, hi, _ = pose_box(h["lo"], h["hi"], p["M"])
            if any(L.touches(parts[o]["mesh"], (lo, hi), rch)[0] for o in solid_ids if o != pid):
                continue
            held.append({**h, "name": f"{pid}: {h['name']}", "part": pid, "lo": lo, "hi": hi,
                         **({"ground": float(lo[2]) + 1.0} if h.get("default") else {})})
    if not held:
        raise ValueError(f"nothing holds the {gid} up: every support its parts give lands on another of its parts")
    for item, support in [(h, True) for h in held] + [(ld, False) for ld in loads]:
        on, gap = L.touches(mesh, (item["lo"], item["hi"]), rch)
        if not on:
            raise ValueError(L.missed(item["name"], gap, rch, support))

    emit("voxels", f"voxelizing the {gid} ({len(solid_ids)} parts) at {spacing:.1f} mm")
    wmat = Material(name=mat["name"], youngs_modulus=mat["E"], poisson_ratio=L.POISSON,
                    strength=mat["strength"], density=mat["density"])
    grid = Grid.around(Mesh(np.asarray(mesh.vertices, float), np.asarray(mesh.faces)), spacing=spacing)
    solid = np.zeros(grid.shape, dtype=bool)
    for pid in solid_ids:                                    # each on its own: an overlap is solid, never cancelled
        m = parts[pid]["mesh"]
        solid |= grid.voxelize(Mesh(np.asarray(m.vertices, float), np.asarray(m.faces)))
    if not solid.any():
        raise ValueError(f"the {gid} voxelized to nothing at {spacing:.1f} mm")
    ls = LoadStudy.from_voxels(grid, solid, material=wmat)
    grow = rch + spacing / 2
    thin = (f"' touches the group only where it's thinner than a voxel ({spacing:.1f} mm), so the strength check "
            f"has nothing there to work with")
    try:
        for h in held:
            ls.support(box=L._grow(h["lo"], h["hi"], grow))
    except ValueError:
        raise ValueError(f"'{h['name']}" + thin)
    attach = np.zeros(ls.grid.shape, dtype=bool)
    for h in held:
        attach |= ls.region(box=L._grow(h["lo"], h["hi"], grow))
    boxes = []
    for load in loads:
        box = L._grow(load["lo"], load["hi"], grow)
        try:
            attach |= ls.region(box=box)
        except ValueError:
            raise ValueError(f"'{load['name']}" + thin)
        boxes.append(box)
    ctx = {"declared": {"construction": []}, "loads": loads, "boxes": boxes, "mesh": mesh, "pieces": pieces,
           "mat": mat, "tol": tol, "spacing": spacing, "coarse": coarse, "held": held, "ls": ls,
           "thinnest": min(thins) if thins else None, "finest": least, "thinnest_where": where,
           "found": [f for p in solid_ids for f in parts[p]["found"]], "thin_said": None,
           "attach": attach, "plate_mat": (L.material(wood) if wood else mat), "grow": grow, "rest": None,
           "headline": L.headline(L.material(wood) if wood else None, None), "trim": [], "unsized": [],
           "group": gid, "solid_ids": solid_ids, "own": [p for p in own if p in parts], "turned": turned,
           "joints": None}
    ctx["patches"] = L._held_patches(ctx)
    # each part's own joints, by hand and by the FEA, posed (a part's own check reads them; its group can't read less:
    # the stool's own check fails at its joints, 0.5x, where its FEA alone reads 2.14x). Between parts: E2
    setups = {p: parts[p]["joints"] for p in solid_ids if parts[p]["joints"] is not None}
    if setups and "unread" not in setups.values():
        ctx["joints"] = {"joints": [_pose_joint(j, parts[p]["M"], p) for p, su in setups.items() for j in su["joints"]],
                         "pieces": pieces, "tol": tol, "screw_mm": min(su["screw_mm"] for su in setups.values())}
    if len({pc["material"] for pc in wood}) > 1:            # each piece its own, over every part (#348)
        L._two_materials(ctx, wood, ctx["plate_mat"], None)
    return ctx


def study_group(store: DesignStore, gid: str, *, min_safety: float = L.MIN_SAFETY, emit: Optional[Callable] = None,
                spacing: Optional[float] = None, stop: Optional[Callable[[], None]] = None) -> dict:
    """Every case of the group's own parts through the group, as :func:`caliper.load_study.study` runs a part's. The
    run record, kept on the group."""
    emit = emit or (lambda *a, **k: None)
    t0 = time.time()
    ctx = prepare_group(store, gid, emit, spacing=spacing)
    loads, mat, held = ctx["loads"], ctx["mat"], ctx["held"]
    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out_dir = os.path.join(runs_dir(store), rid)
    os.makedirs(out_dir, exist_ok=True)
    cases = []
    every = L.solved(ctx)
    for i, load in enumerate(loads):
        emit("case", f"{load['name']}: {load['lb']:g} lb × {load['factor']:g}", progress=i / len(loads))
        case, r = L.check_load(ctx, i, min_safety, got=every[i])
        if r.supported:
            with open(os.path.join(out_dir, f"case_{i:02d}.json"), "w") as f:
                json.dump(L.heat_mesh(ctx["mesh"], ctx["ls"].grid, r.von_mises, r.solid, 2 * ctx["spacing"]), f)
            case["heat"] = f"case_{i:02d}.json"
        cases.append(case)
    notes = [f"{mat['name']}: E {mat['E']:g} MPa, strength {mat['strength']:g} MPa — {mat['basis']}.", *L.NOTES,
             *L.buckling_notes(ctx["pieces"], loads, mat, ctx["tol"], ctx.get("plate_mat"), held=held,
                               voxel=ctx.get("spacing")), OWN_WEIGHT, MEET]
    for k in ("note", "coarse"):
        if ctx.get(k):
            notes.append(ctx[k])
    if ctx["turned"]:
        notes.append(f"Turned other than a quarter turn, so taken as the box round it: {', '.join(ctx['turned'])}.")
    worst = L.run_safety(cases)
    record = {
        "id": rid, "group": gid, "kind": "load", "created": time.time(),
        "members": {p: store.design.part(p).version for p in ctx["solid_ids"]}, "own": ctx["own"],
        "seconds": round(time.time() - t0, 1), "material": mat, "spacing_mm": round(ctx["spacing"], 2),
        "voxels": int(ctx["ls"].solid.sum()), "headline": ctx.get("headline") or mat["name"],
        "min_safety": min_safety, "held": held, "cases": cases, "notes": notes, "cut": True,
        "safety": worst, "holds": bool(cases) and all(c.get("holds") for c in cases),  # producer
    }
    wooden = [pc for pc in ctx["pieces"] if pc.get("material") in ("plywood", "lumber")]
    if ctx.get("joints") is not None:                 # its parts' own joints, as a part's run says them (#301)
        chained = [c.get("joints") or {} for c in cases]
        record["joints_checked"] = True
        record["joints_unchecked"] = sorted({u for J in chained if J.get("chain") is not False
                                             for u in J.get("unchecked") or []})
        record["joints_unchained"] = sorted({u for J in chained if J.get("chain") is False
                                             for u in J.get("unchecked") or []})
        if record["joints_unchained"]:
            record["wood_joints"] = len(ctx["joints"]["joints"])
        elif record["joints_unchecked"]:
            record["wood_joints"] = len(record["joints_unchecked"])
    elif len(wooden) > 1:                             # its joints, taken as solid wood: said on its verdict (#222)
        record["wood_joints"] = "uncounted"
    thin = ctx.get("thinnest")
    if thin:                                          # can the FEA see its thinnest wall? (CALI-97)
        record["thinnest_mm"] = round(thin, 2)
        if ctx.get("thinnest_where"):
            record["thinnest_where"] = ctx["thinnest_where"]
        record["unseen"] = L.unseen_walls(ctx.get("found") or [], ctx["spacing"])
        record["across"] = round(thin / ctx["spacing"], 3)
        record["resolved"] = L._sees(thin / ctx["spacing"])
    with open(os.path.join(out_dir, "run.json"), "w") as f:
        json.dump(record, f, indent=2, default=str)
    from . import verdicts

    v = verdicts.run(record)
    store.append_log({"kind": "load", "action": "studied", "group": gid, "run": rid})
    emit("done", L.done_words(len(cases), v, worst), run=rid, progress=1.0)
    return record


def load_run(store: DesignStore, rid: str) -> Optional[dict]:
    if not rid or "/" in rid or ".." in rid:
        return None
    path = os.path.join(runs_dir(store), rid, "run.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_runs(store: DesignStore, gid: Optional[str] = None) -> list[dict]:
    root = runs_dir(store)
    if not os.path.isdir(root):
        return []
    got = [r for r in (load_run(store, rid) for rid in sorted(os.listdir(root), reverse=True))
           if r and (gid is None or r.get("group") == gid)]
    return newest_first(got)


def stale(store: DesignStore, run: dict) -> Optional[str]:
    """Why a group's run is of another version of it, in words, or None: a part changed, gone, or not built."""
    for pid, v in (run.get("members") or {}).items():
        now = store.design.part(pid)
        if now is None:
            return f"the {pid} has gone since it was checked"
        if now.version != v:
            return f"the {pid} has changed since it was checked"
    return None
