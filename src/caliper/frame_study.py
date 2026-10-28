"""CALI-40 — size a tube frame: the lightest tubes that still hold, and what the hitch has to carry.

A welded tube frame isn't a voxel problem: at a hitch carrier's scale whittle's voxels are ~1.5 in and a
⅛ in tube wall is invisible. It's a frame problem — each tube a beam — and whittle's ``FrameStudy`` (built
by the whittle-agent session for exactly this) solves it: per-member stress and safety factor, how far it
sags, what the supports hold, and a sweep from the frame as drawn to the lightest tubes that pass.

Caliper's side is the plumbing between a part and that study:

- **The part declares its own structure.** Its script defines ``members(params)`` — centrelines, the tube
  each one is, its group, and the PARAMS that size it — and ``supports(params)``. Both run in a separate
  process (a script may be LLM-authored). Ends that meet within :data:`MERGE_MM` become one joint.
- **Two load cases.** ``standing`` (×1) is what the hitch carries at rest — the number to compare with the
  hitch's rating. ``driving`` (×``factor``, 2.5 by default for bumps) is what the safety target is held to.
  The load (the box and what's in it) is spread along the members of ``on_groups``; self-weight is added.
- **Sizes come back as numbers.** Using a station writes each group's tube into the PARAMS its members name
  — a new, still-parametric revision of the part, measured like any other.

whittle's notes travel with every result, including its fatigue warning: welded steel under road
vibration cracks at weld toes, which neither a frame model nor a voxel model sees.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from typing import Callable, Optional

from .design import DesignStore

#: Member ends closer than this are one joint.
MERGE_MM = 1.0
LB = 4.4482216152605          # newtons per pound-force
LBIN = LB * 25.4               # newton-millimetres per pound-inch
KG_LB = 2.20462262


# ---------------------------------------------------------------------------
# Reading the structure a part declares
# ---------------------------------------------------------------------------
def frame_def(store: DesignStore, part_id: str, timeout: float = 60.0) -> dict:
    """``{"members": [...], "supports": [...]}`` from the part's script, run in its own process."""
    if not store.is_scripted(part_id):
        raise ValueError(f"'{part_id}' is a mesh right now — roll it back to its script first")
    script = store.read_script(part_id)
    probe = (script + "\n\nimport json as _json\n"
             "_m = members({}) if 'members' in globals() else None\n"
             "_s = supports({}) if 'supports' in globals() else []\n"
             "print('@@FRAME@@' + _json.dumps({'members': _m, 'supports': _s}, default=list))\n")
    try:
        out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                             timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ValueError(f"'{part_id}'s members() took longer than {timeout:g}s")
    line = next((ln for ln in out.stdout.splitlines() if ln.startswith("@@FRAME@@")), None)
    if line is None:
        tail = [ln for ln in out.stderr.strip().splitlines() if ln.strip()]
        raise ValueError(f"couldn't read '{part_id}'s members(): "
                         f"{tail[-1] if tail else 'no output'}")
    data = json.loads(line[len("@@FRAME@@"):])
    if not data.get("members"):
        raise ValueError(f"'{part_id}' doesn't declare members(params) — a frame study needs its "
                         f"tube centrelines")
    if not data.get("supports"):
        raise ValueError(f"'{part_id}' doesn't declare supports(params) — where is it held?")
    return data


def section_key(outer_mm: float, wall_mm: float) -> str:
    """The whittle catalog name for a square tube, e.g. (50.8, 3.175) -> "2x2x1/8"."""
    from whittle import TUBES, tube_size

    for key in TUBES:
        o, w = tube_size(key)
        if abs(o - outer_mm) < 0.05 and (abs(w - wall_mm) < 0.05 or (2 * w >= o and 2 * wall_mm >= outer_mm)):
            return key
    raise ValueError(f"no catalog tube is {outer_mm / 25.4:.3g} in with a {wall_mm / 25.4:.3g} in wall")


def build_spec(fd: dict, *, load_lb: float = 100.0, factor: float = 2.5,
               on_groups=("rails",)) -> dict:
    """whittle's ``FrameStudy.from_dict`` input, plus what Caliper needs to read the answer."""
    nodes: list[list[float]] = []

    def node_of(xyz) -> int:
        for i, n in enumerate(nodes):
            if sum((a - b) ** 2 for a, b in zip(n, xyz)) <= MERGE_MM ** 2:
                return i
        nodes.append([float(v) for v in xyz])
        return len(nodes) - 1

    members, loaded = [], []
    for i, m in enumerate(fd["members"]):
        members.append({"a": node_of(m["a"]), "b": node_of(m["b"]),
                        "section": section_key(m["outer"], m["wall"]), "group": m["group"]})
        if m["group"] in on_groups:
            loaded.append(i)
    if not loaded:
        raise ValueError(f"no members in {list(on_groups)} to carry the load")

    supports = []
    for s in fd["supports"]:
        at = node_of(s["at"])
        if at >= len(nodes) - 0 and not any(at in (m["a"], m["b"]) for m in members):
            raise ValueError(f"support at {s['at']} isn't on any member")
        supports.append({"node": at, "fix": list(s.get("fix", "all"))})

    each = -load_lb * LB / len(loaded)
    cases = {"standing": {"factor": 1.0, "self_weight": True},
             "driving": {"factor": float(factor), "self_weight": True}}
    loads = [{"case": c, "member": i, "total": [0.0, 0.0, each]} for c in cases for i in loaded]
    return {"spec": {"material": "steel", "nodes": nodes, "members": members, "supports": supports,
                     "cases": cases, "loads": loads},
            "mouth": nodes[supports[0]["node"]], "names": [m["name"] for m in fd["members"]],
            "groups": [m["group"] for m in fd["members"]],
            "size_params": {m["group"]: m.get("size_params") for m in fd["members"]}}


# ---------------------------------------------------------------------------
# Running it
# ---------------------------------------------------------------------------
def _summary(result, built: dict) -> dict:
    """What a person reads off one design: weight, worst member, sag, and what the hitch holds."""
    mouth = built["mouth"]
    out = {"mass_kg": round(float(result.mass), 2), "mass_lb": round(float(result.mass) * KG_LB, 1),
           "safety": round(float(result.safety), 2),
           "governing": {"case": result.governing[0], "member": built["names"][result.governing[1]]},
           "deflection_mm": round(float(result.deflection), 1),
           "deflection_in": round(float(result.deflection) / 25.4, 2),
           "notes": list(result.notes), "receiver": {}}
    for name, case in result.cases.items():
        force, moment = case.resultant(about=mouth)
        out["receiver"][name] = {"force_lb": round(abs(float(force[2])) / LB, 1),
                                 "moment_lbin": round(abs(float(moment[1])) / LBIN, 0)}
    return out


def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "frames")


def study(store: DesignStore, part_id: str, *, load_lb: float = 100.0, factor: float = 2.5,
          min_safety: float = 3.5, on_groups=("rails",), catalogs: Optional[dict] = None,
          emit: Optional[Callable] = None) -> dict:
    """Analyse the frame as drawn, then sweep for the lightest tubes that keep ``min_safety``."""
    from whittle import TUBES, FrameStudy, io, tube_size

    emit = emit or (lambda *a, **k: None)
    fd = frame_def(store, part_id)
    built = build_spec(fd, load_lb=load_lb, factor=factor, on_groups=on_groups)
    fs = FrameStudy.from_dict(built["spec"])
    emit("planned", f"{len(fd['members'])} members, {len(built['spec']['nodes'])} joints — "
                    f"{load_lb:g} lb on {', '.join(on_groups)}, ×{factor:g} driving")

    drawn = _summary(fs.analyze(), built)
    emit("analysed", f"as drawn: {drawn['mass_lb']} lb of steel, safety {drawn['safety']}x")

    if catalogs is None:
        # a group can be any catalog tube — except one whose outside has to fit something (the
        # shank in the receiver): it keeps its outer size and only its wall may change
        catalogs = {}
        for g in sorted(set(built["groups"])):
            current = next(m for m in fd["members"] if m["group"] == g)
            if g == "shank":
                catalogs[g] = [k for k in TUBES if abs(tube_size(k)[0] - current["outer"]) < 0.05]
            else:
                catalogs[g] = list(TUBES)
    sweep = fs.sweep(groups=catalogs, min_safety=float(min_safety))
    emit("swept", f"{len(list(sweep))} designs")

    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out_dir = os.path.join(runs_dir(store), rid)
    os.makedirs(out_dir, exist_ok=True)
    stations = []
    for i, st in enumerate(sweep):
        row = {"index": i, "design": dict(st.design), **_summary(st.analysis, built)}
        stations.append(row)
        with open(os.path.join(out_dir, f"station_{i:02d}.stl"), "wb") as f:
            f.write(io.stl_bytes(fs.mesh(st.analysis.sections)))
    record = {
        "id": rid, "part": part_id, "kind": "frame", "created": time.time(),
        "load_lb": load_lb, "factor": factor, "min_safety": min_safety, "on_groups": list(on_groups),
        "drawn": drawn, "stations": stations, "note": getattr(sweep, "note", "") or "",
        "size_params": built["size_params"], "catalogs": catalogs,
        "members": [{"name": n, "group": g} for n, g in zip(built["names"], built["groups"])],
    }
    with open(os.path.join(out_dir, "run.json"), "w") as f:
        json.dump(record, f, indent=2)
    store.append_history(part_id, {"kind": "frame", "action": "studied", "run": rid,
                                   "stations": len(stations)})
    store.append_log({"kind": "frame", "action": "studied", "part": part_id, "run": rid})
    emit("done", f"{len(stations)} designs, from {stations[0]['mass_lb']} to "
                 f"{stations[-1]['mass_lb']} lb of steel", run=rid)
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
    if "/" in rid or ".." in rid:
        raise ValueError("bad run id")
    return os.path.join(runs_dir(store), rid, f"station_{int(index):02d}.stl")


def adopt(store: DesignStore, rid: str, index: int) -> dict:
    """Write a station's tubes into the frame's PARAMS — a new parametric revision of the part."""
    from whittle import tube_size

    from .aero import write_params

    rec = load_run(store, rid)
    if rec is None:
        raise FileNotFoundError(f"no frame study {rid!r}")
    st = next((s for s in rec["stations"] if s["index"] == int(index)), None)
    if st is None:
        raise FileNotFoundError(f"study {rid} has no design {index}")
    pid = rec["part"]
    values = {}
    for group, key in st["design"].items():
        names = (rec.get("size_params") or {}).get(group)
        if not names or len(names) != 2:
            raise ValueError(f"'{pid}' doesn't say which PARAMS size its {group}")
        outer, wall = tube_size(key)
        values[names[0]], values[names[1]] = round(outer, 3), round(min(wall, outer / 2.0), 3)
    script = write_params(store.read_script(pid), values)
    pretty = ", ".join(f"{g} {k}" for g, k in st["design"].items())
    version = store.write_part(pid, script, action="frame",
                               feedback=f"sized by frame study: design {index} ({pretty})",
                               extra={"frame_run": rid, "station": int(index), "design": st["design"],
                                      "mass_lb": st["mass_lb"], "safety": st["safety"]})
    return {"version": version, "design": st["design"]}
