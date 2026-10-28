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
import math
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
GRAVITY = 9.80665              # m/s², so kg -> N
#: Point loads closer than this along a member are combined at their balance point.
BIN_MM = 50.0


# ---------------------------------------------------------------------------
# Reading the structure a part declares
# ---------------------------------------------------------------------------
def frame_def(store: DesignStore, part_id: str, timeout: float = 60.0,
              params: Optional[dict] = None) -> dict:
    """``{"members": [...], "supports": [...]}`` from the part's script, run in its own process.
    ``params`` overrides its PARAMS — a what-if layout, say."""
    if not store.is_scripted(part_id):
        raise ValueError(f"'{part_id}' is a mesh right now — roll it back to its script first")
    script = store.read_script(part_id)
    over = json.dumps(params or {})
    probe = (script + "\n\nimport json as _json\n"
             f"_p = _json.loads({over!r})\n"
             "_m = members(_p) if 'members' in globals() else None\n"
             "_s = supports(_p) if 'supports' in globals() else []\n"
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


def read_layouts(script: str) -> dict[str, dict]:
    """A frame's named what-if layouts — ``LAYOUTS = {"X only": {"edges": 0}}`` — PARAMS overrides
    that change which tubes there are, not their sizes. A frame study runs one at a time."""
    import ast

    try:
        tree = ast.parse(script)
    except SyntaxError:
        return {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "LAYOUTS"):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return {}
            return {str(k): dict(v) for k, v in value.items() if isinstance(v, dict)} \
                if isinstance(value, dict) else {}
    return {}


def layout_name(script: str, params: Optional[dict]) -> Optional[str]:
    """Which of the frame's LAYOUTS these PARAMS (over the script's own) are, if any."""
    from .aero import read_params

    full = {**(read_params(script) or {}), **(params or {})}
    for name, values in read_layouts(script).items():
        if all(full.get(k) == v for k, v in values.items()):
            return name
    return None


def section_key(outer_mm: float, wall_mm: float) -> str:
    """The whittle catalog name for a square tube, e.g. (50.8, 3.175) -> "2x2x1/8"."""
    from whittle import TUBES, tube_size

    for key in TUBES:
        o, w = tube_size(key)
        if abs(o - outer_mm) < 0.05 and (abs(w - wall_mm) < 0.05 or (2 * w >= o and 2 * wall_mm >= outer_mm)):
            return key
    raise ValueError(f"no catalog tube is {outer_mm / 25.4:.3g} in with a {wall_mm / 25.4:.3g} in wall")


def build_spec(fd: dict, *, load_lb: float = 100.0, factor: float = 2.5,
               on_groups=("rails",), points=None, bin_mm: float = BIN_MM, walls=None) -> dict:
    """whittle's ``FrameStudy.from_dict`` input, plus what Caliper needs to read the answer.

    Without ``points``, ``load_lb`` is spread evenly along the members of ``on_groups`` (CALI-40). With
    ``points`` — ``(xyz, kg)`` or ``(xyz, kg, via)``, the weight of what the frame carries where it is
    (CALI-43) — each lands on the nearest member that carries the floor (those a part marks
    ``"carries": True``, else those in ``on_groups``) as a point load where it meets it, so a tube
    bends where the load sits. Loads within ``bin_mm`` of each other along a member are combined at
    their balance point (force and moment kept). Members stay whole: whittle checks buckling over a
    member's own length.

    ``walls`` (CALI-44): a part's ``shell()`` beams, added as members of their own material (group
    "walls"), fastened to the frame where their ends come within :data:`SNAP_MM` of a joint. They carry
    the floor too; a point that comes ``via`` "walls" lands on a wall only.
    """
    nodes: list[list[float]] = []

    def nearest(xyz, within: float, among) -> Optional[int]:
        best, at = None, within ** 2
        for i in among:
            d = sum((a - b) ** 2 for a, b in zip(nodes[i], xyz))
            if d <= at:
                best, at = i, d
        return best

    def node_of(xyz) -> int:
        found = nearest(xyz, MERGE_MM, range(len(nodes)))
        if found is not None:
            return found
        nodes.append([float(v) for v in xyz])
        return len(nodes) - 1

    marked = any(m.get("carries") for m in fd["members"])
    carries = [bool(m.get("carries")) if marked else m["group"] in on_groups for m in fd["members"]]
    if not any(carries):
        raise ValueError(f"no members in {list(on_groups)} to carry the load")

    members, loaded, names, groups, outers = [], [], [], [], []
    for i, m in enumerate(fd["members"]):
        members.append({"a": node_of(m["a"]), "b": node_of(m["b"]),
                        "section": section_key(m["outer"], m["wall"]), "group": m["group"]})
        names.append(m["name"]); groups.append(m["group"]); outers.append(float(m["outer"]))
        plan = math.hypot(m["b"][0] - m["a"][0], m["b"][1] - m["a"][1])
        if carries[i] and (points is None or plan > 1.0):     # a vertical stub can't hold up a floor
            loaded.append(i)
    steel = len(members)
    joints = sorted({n for m in members for n in (m["a"], m["b"])})
    wall_ix, fastened, checks = [], set(), []
    for w in walls or []:
        ends = []
        for xyz in (w["a"], w["b"]):
            n = nearest(xyz, SNAP_MM, [j for j in joints if j not in ends])   # not both ends to one joint
            if n is None:
                n = node_of(xyz)
            else:
                fastened.add(n)
            ends.append(n)
        if ends[0] == ends[1]:
            raise ValueError(f"{w['name']} is too short to be a wall beam")
        section, material, check = wall_section(w, math.dist(w["a"], w["b"]))
        checks.append(check)
        wall_ix.append(len(members))
        members.append({"a": ends[0], "b": ends[1], "section": section, "material": material,
                        "group": "walls"})
        names.append(w["name"]); groups.append("walls"); outers.append(float(w["depth"]))

    supports = []
    for s in fd["supports"]:
        at = node_of(s["at"])
        if not any(at in (m["a"], m["b"]) for m in members):
            raise ValueError(f"support at {s['at']} isn't on any member")
        supports.append({"node": at, "fix": list(s.get("fix", "all"))})

    cases = {"standing": {"factor": 1.0, "self_weight": True},
             "driving": {"factor": float(factor), "self_weight": True}}
    applied = None
    if points is None:
        each = -load_lb * LB / len(loaded)
        loads = [{"case": c, "member": i, "total": [0.0, 0.0, each]} for c in cases for i in loaded]
    else:
        import numpy as np

        xyz = np.array([p[0] for p in points], dtype=np.float64)
        kg = np.array([p[1] for p in points], dtype=np.float64)
        via_walls = np.array([len(p) > 2 and p[2] == "walls" for p in points]) if wall_ix else \
            np.zeros(len(points), dtype=bool)
        targets = loaded + wall_ix
        pa = np.array([nodes[members[i]["a"]][:2] for i in targets])
        pb = np.array([nodes[members[i]["b"]][:2] for i in targets])
        span = pb - pa
        t = np.clip(((xyz[:, None, :2] - pa[None]) * span[None]).sum(-1) / (span ** 2).sum(-1)[None], 0, 1)
        gap = np.linalg.norm(xyz[:, None, :2] - (pa[None] + t[..., None] * span[None]), axis=-1)
        gap[np.ix_(via_walls, np.arange(len(loaded)))] = np.inf     # through the walls: walls only
        near = gap.argmin(axis=1)
        tt = t[np.arange(len(xyz)), near]
        loads, lands, total = [], np.zeros(3), 0.0
        for k, i in enumerate(targets):
            on = near == k
            if not on.any():
                continue
            a, b = np.array(nodes[members[i]["a"]]), np.array(nodes[members[i]["b"]])
            n_bins = max(1, math.ceil(float(np.linalg.norm(b - a)) / bin_mm))
            which = np.minimum((tt[on] * n_bins).astype(int), n_bins - 1)
            w, s_ = kg[on], tt[on]
            for j in np.unique(which):
                sel = which == j
                mass = float(w[sel].sum())
                at = float((w[sel] * s_[sel]).sum() / mass)
                loads += [{"case": c, "member": i, "at": at, "force": [0.0, 0.0, -mass * GRAVITY]}
                          for c in cases]
                lands += mass * (a + at * (b - a))
                total += mass
        floor = ~via_walls
        reach = gap[floor].min(axis=1).max() if floor.any() else 0.0
        on_walls = float(kg[np.isin(near, np.arange(len(loaded), len(targets)))].sum())
        applied = {"mass_kg": float(kg.sum()), "cog": ((kg[:, None] * xyz).sum(0) / kg.sum()).tolist(),
                   "lands": (lands / total).tolist(), "reach_mm": float(reach), "on_walls_kg": on_walls}
    return {"spec": {"material": "steel", "nodes": nodes, "members": members, "supports": supports,
                     "cases": cases, "loads": loads},
            "mouth": nodes[supports[0]["node"]], "names": names, "groups": groups, "applied": applied,
            "ends": [(m["a"], m["b"]) for m in members], "outers": outers, "steel": steel,
            "walls": [{"name": names[i], "depth_in": round(outers[i] / 25.4, 1), "skins": c["skins"],
                       "core": c["core"]} for i, c in zip(wall_ix, checks)],
            "wall_checks": checks,
            "fastened": [nodes[n] for n in sorted(fastened)], "fastened_ix": sorted(fastened),
            "size_params": {m["group"]: m.get("size_params") for m in fd["members"]}}


# ---------------------------------------------------------------------------
# Walls that carry load: a part's shell() as beams (CALI-44)
# ---------------------------------------------------------------------------
#: A wall beam's end this close to a frame joint is fastened there (the frame's corners sit a little in
#: from the box's).
SNAP_MM = 60.0


def wall_section(wall: dict, length: float) -> tuple[dict, dict, dict]:
    """A sandwich wall acting as a deep beam in its own plane: a whittle section, its material, and
    what Caliper checks itself (the foam's shear).

    The wall is a foam core with skins (``M.SKINS``), ``depth`` tall. Everything is transformed to the
    first skin's material, so whittle's stress is the skin's and its strength the skin's — or the
    stress it wrinkles at in compression, if lower: the skins carry the bending. Caliper checks the
    foam's shear itself (whittle reads a skin-equivalent shear). Shear spreads over the layers by their stiffness (G·t), and whittle bends the wall with
    that shear stiffness too (span/depth is ~1–3 and the core is soft, so it matters). The floor holds a
    wall's bottom edge straight sideways and the box holds its walls square, so sideways bending and
    twisting are taken as stiff as the in-plane bending.
    """
    from . import materials as M

    core = M.sheet(wall["core"])["mech"]
    layers = [(float(wall["core_t"]), core["E"], core["G"], core["strength"])]
    for name in wall.get("skins") or []:
        sk = M.SKINS.get(name)
        if sk:
            layers.append((sk["t"], sk["E"], sk["G"], sk["strength"]))
    _, e_ref, g_ref, strength = layers[1] if len(layers) > 1 else layers[0]
    if len(layers) > 1:
        # a thin skin on soft foam wrinkles in compression before it breaks (Hoff & Mautner)
        strength = min(strength, 0.5 * (e_ref * core["E"] * core["G"]) ** (1.0 / 3.0))
    h = float(wall["depth"])
    t_eq = sum(t * e / e_ref for t, e, _, _ in layers)
    gt = sum(t * g for t, _, g, _ in layers)                     # in-plane shear stiffness per height
    iy = t_eq * h ** 3 / 12.0
    shear = h * gt / g_ref                                       # so that G·A_s is the wall's
    section = {"name": f"{wall.get('name', 'wall')} ({h / 25.4:.0f} in deep)",
               "width": t_eq, "height": h, "area": t_eq * h, "mass_area": 0.0,
               "iy": iy, "iz": iy, "j": iy, "sy": iy / (h / 2.0), "sz": iy / (h / 2.0),
               "wt": iy / (h / 2.0), "shear_y": shear, "shear_z": shear}
    material = {"youngs_modulus": e_ref, "shear_modulus": g_ref, "strength": strength, "density": 0.0}
    check = {"depth": h, "core_t": float(wall["core_t"]), "core_shear": core["shear_strength"],
             "skin_strength": strength,
             "skins": " + ".join(wall.get("skins") or []) or "no skin", "core": wall["core"]}
    return section, material, check


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
    out["joints"] = _joints(result, built)
    walls = []
    first = built.get("steel", len(built["names"]))
    for k in range(first, len(built["names"])):
        ck = built["wall_checks"][k - first]
        skin = min((float(c.safety[k]), name) for name, c in result.cases.items())
        # the foam's shear, taking all the wall's shear in the foam (a skin's own share is a guess for PMF)
        v = max(float(abs(c.end_forces[k, i])) for c in result.cases.values() for i in (1, 2, 7, 8))
        tau = v / (ck["depth"] * ck["core_t"])
        foam = ck["core_shear"] / tau if tau > 0 else float("inf")
        walls.append({"name": built["names"][k], "skin_safety": round(skin[0], 2),
                      "foam_safety": round(min(foam, 999.0), 2), "safety": round(min(skin[0], foam), 2),
                      "case": skin[1]})
    if walls:
        out["walls"] = walls
        # what the box's fixings to the frame carry: the walls' shear where they're fastened
        fixed = {}
        for k in range(first, len(built["names"])):
            for end, cols in ((0, (1, 2)), (1, (7, 8))):
                n = built["ends"][k][end]
                if n in built.get("fastened_ix", ()):
                    for name, c in result.cases.items():
                        v = float(math.hypot(*(c.end_forces[k, i] for i in cols)))
                        fixed[(n, name)] = fixed.get((n, name), 0.0) + v
        if fixed:
            (n, case), v = max(fixed.items(), key=lambda kv: kv[1])
            out["fixing"] = {"force_lb": round(v / LB, 1), "case": case,
                             "at": [round(x, 1) for x in built["spec"]["nodes"][n]]}
    return out


def _joints(result, built: dict, case: str = "driving", top: int = 3) -> list[dict]:
    """The hardest-worked joints where three or more tubes meet: the bending each welded tube end puts
    into the joint, worst first — what a gusset there has to carry. A tube that runs straight through
    (two collinear ends of the same tube, nothing bigger in the way) is one piece, not a weld, so its
    bending doesn't count."""
    import numpy as np

    c = result.cases.get(case) or next(iter(result.cases.values()))
    nodes = np.asarray(built["spec"]["nodes"], dtype=np.float64)
    sections = [m["section"] for m in built["spec"]["members"]]
    meet: dict[int, list[int]] = {}
    for k, (a, b) in enumerate(built["ends"][:built.get("steel", len(built["ends"]))]):   # welds: steel
        meet.setdefault(a, []).append(k)
        meet.setdefault(b, []).append(k)

    def away(k, n):                     # unit vector from node n along member k
        a, b = built["ends"][k]
        v = nodes[b if n == a else a] - nodes[n]
        return v / np.linalg.norm(v)

    out = []
    for n, ks in meet.items():
        if len(ks) < 3:
            continue
        # a bigger tube meeting them here is in the way: they're cut and welded to its sides
        through, biggest = set(), max(built["outers"][k] for k in ks)
        for i, k in enumerate(ks):
            for q in ks[i + 1:]:
                if (sections[k] == sections[q] and built["outers"][k] >= biggest - 0.01
                        and float(np.dot(away(k, n), away(q, n))) < -0.9999):
                    through.update((k, q))
        worst = {"bending": 0.0, "torsion": 0.0, "member": None}
        for k in ks:
            if k in through:
                continue
            a, _ = built["ends"][k]
            f = c.end_forces[k, 3:6] if n == a else c.end_forces[k, 9:12]
            bend = float(np.hypot(f[1], f[2]))
            if bend > worst["bending"]:
                worst = {"bending": bend, "torsion": abs(float(f[0])), "member": built["names"][k]}
        if worst["member"] is None:
            continue
        out.append({"members": sorted({built["names"][k] for k in ks}), "at": [round(v, 1) for v in nodes[n]],
                    "case": case, "worst_member": worst["member"],
                    "bending_lbin": round(worst["bending"] / LBIN), "torsion_lbin": round(worst["torsion"] / LBIN)})
    return sorted(out, key=lambda j: -j["bending_lbin"])[:top]


def runs_dir(store: DesignStore) -> str:
    return os.path.join(store.root, "frames")


def study(store: DesignStore, part_id: str, *, load_lb: float = 100.0, factor: float = 2.5,
          min_safety: float = 3.5, on_groups=("rails",), catalogs: Optional[dict] = None,
          emit: Optional[Callable] = None, from_design: bool = False, payload_lb: float = 100.0,
          params: Optional[dict] = None, walls: bool = True, build: Optional[dict] = None) -> dict:
    """Analyse the frame as drawn, then sweep for the lightest tubes that keep ``min_safety``.

    ``from_design``: carry the design's other parts as they're built (their ``construction()``), each
    piece's weight where it is, plus ``payload_lb`` spread over the floor — instead of ``load_lb``
    spread along ``on_groups``. ``params`` overrides the frame's PARAMS for a what-if layout.
    ``walls``: a part that declares ``shell()`` carries load with its walls too (CALI-44). ``build``
    tries other construction choices for the parts it carries (``{part: {BUILD entry: value}}``).
    """
    from whittle import TUBES, FrameStudy, io, tube_size

    from . import construction

    emit = emit or (lambda *a, **k: None)
    fd = frame_def(store, part_id, params=params)
    loads, carried = None, None
    if from_design:
        carried = construction.design_loads(store, skip=(part_id,), payload_lb=payload_lb, walls=walls,
                                            build=build)
        if not carried["points"]:
            raise ValueError("no other part says what it's built from — nothing for the frame to carry")
        loads = carried["points"]
        load_lb = carried["mass_kg"] * KG_LB
    built = build_spec(fd, load_lb=load_lb, factor=factor, on_groups=on_groups, points=loads,
                       walls=carried["shell"] if carried else None)
    fs = FrameStudy.from_dict(built["spec"])
    steel_only = FrameStudy.from_dict({**built["spec"], "members": built["spec"]["members"][:built["steel"]],
                                       "loads": []}) if built["walls"] else fs
    what = (", ".join(f"{p['part']} {p['mass_kg'] * KG_LB:.0f} lb" for p in carried["parts"]) + " where they sit"
            if carried else f"{load_lb:g} lb on {', '.join(on_groups)}")
    emit("planned", f"{len(fd['members'])} members, {len(built['spec']['nodes'])} joints — "
                    f"{what}, ×{factor:g} driving")

    drawn = _summary(fs.analyze(), built)
    emit("analysed", f"as drawn: {drawn['mass_lb']} lb of steel, safety {drawn['safety']}x")

    if catalogs is None:
        # a group can be any catalog tube — except one whose outside has to fit something (the
        # shank in the receiver): it keeps its outer size and only its wall may change
        catalogs = {}
        for g in sorted(set(built["groups"]) - {"walls"}):       # the walls are what they're built from
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
            f.write(io.stl_bytes(steel_only.mesh(st.analysis.sections[:built["steel"]])))
    carrying = None
    if carried:
        ap = built["applied"]
        carrying = {"parts": [{"part": p["part"], "mass_lb": round(p["mass_kg"] * KG_LB, 1)} for p in carried["parts"]],
                    "payload_lb": payload_lb, "mass_lb": round(ap["mass_kg"] * KG_LB, 1),
                    "cog": [round(v, 1) for v in ap["cog"]],
                    # the floor carries each bit sideways to the nearest tube: how far that moves it
                    "shift_in": round((ap["cog"][0] - ap["lands"][0]) / 25.4, 2),
                    "reach_in": round(ap["reach_mm"] / 25.4, 1), "notes": carried["notes"],
                    "walls": built["walls"], "on_walls_lb": round(ap["on_walls_kg"] * KG_LB, 1),
                    "fastened": [[round(v, 1) for v in n] for n in built["fastened"]]}
    record = {
        "id": rid, "part": part_id, "kind": "frame", "created": time.time(), "params": params or {},
        "build": build or {}, "walls": bool(carried and carried["shell"]),
        "layout": layout_name(store.read_script(part_id), params),
        "carrying": carrying,
        "load_lb": round(load_lb, 1), "factor": factor, "min_safety": min_safety, "on_groups": list(on_groups),
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
    values.update(rec.get("params") or {})      # a what-if layout comes with its sizes
    script = write_params(store.read_script(pid), values)
    pretty = ", ".join(f"{g} {k}" for g, k in st["design"].items())
    version = store.write_part(pid, script, action="frame",
                               feedback=f"sized by frame study: design {index} ({pretty})",
                               extra={"frame_run": rid, "station": int(index), "design": st["design"],
                                      "mass_lb": st["mass_lb"], "safety": st["safety"]})
    return {"version": version, "design": st["design"]}
