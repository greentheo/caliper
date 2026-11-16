"""CALI-190 (#301), #222 slice B: a hand check of each joint, needing what the wood needs.

whittle's FEA gives von Mises stress only, so no force across a joint can be read from it: a joint's force comes from hand
statics, as buckling's did (#235). This module is that check's geometry and arithmetic:

- **Where a joint is** (:func:`interfaces`): for every contact :func:`joints.contacts` finds, whose edge meets whose face,
  the same reading the patterns' screw marks use (``marks.screws``, ``marks._edge_on``), so the screws the check counts are
  the ones the shopping list buys. ``out`` points from the edge piece into the face piece.
- **What a force across it does** (:func:`split`): pressed in, it bears; pulled out, it's withdrawal; along the joint, it's
  shear. Worked out from the force's direction, never asked.

The capacities and the statics that give each joint its force follow #301's decisions (posted on #301).
"""

from __future__ import annotations

from typing import Optional

import numpy as np

#: Where a joint can't be read as an edge on a face: what it's said as instead.
UNPLACED = {"through": "a through tenon", "notch": "a notch", "into": "set into the other (a dado or rabbet)",
            "face": "one piece flat on the other's face"}


def interfaces(store, pid: str) -> list[dict]:
    """Every joint of a part as the check reads it: ``{"pieces": [a, b], "edge", "face", "out", "along", "length_mm",
    "area_mm2", "mid", "screws", "kind", "fix", "assumed"}``, or, where it isn't an edge on a face, ``{"pieces",
    "unplaced": why}``. Pieces by their keys (their names), sorted."""
    return setup(store, pid)["joints"]


def setup(store, pid: str) -> dict:
    """What the check of a part's joints needs, read once per study: ``{"joints", "pieces", "tol", "screw_mm"}``."""
    from . import construction as C
    from . import fasteners
    from . import joints as J
    from . import marks
    from .consistency import _sides, shapes, tolerance

    ok, said = J.readable(store.read_script(pid))
    mesh = store.part_geometry(pid).require_mesh()
    pieces = shapes(C.declared(store, pid))
    _sides(mesh, [pc for pc in pieces if pc["kind"] == "sheet"])
    fasteners.keys(pieces)
    tol = tolerance(mesh)
    by = {pc["key"]: pc for pc in pieces}
    found = J.contacts(pieces, tol)
    screws = marks.screws(pieces, tol, said if ok else None)
    listed = {tuple(j["pieces"]): j for j in J.listed(store, pid)}
    out = []
    for key, c in sorted(found.items()):
        j = listed.get(key) or {"kind": "butt", "fix": list(J.ASSUMED_FIX), "assumed": True}
        base = {"pieces": list(key), "kind": j.get("kind"), "fix": list(j.get("fix") or []), "assumed": bool(j.get("assumed"))}
        s = screws.get(key) or {}
        if c["how"] != "edge":
            out.append({**base, "unplaced": UNPLACED.get(c["how"], "not an edge on a face")})
            continue
        if s.get("on") and s.get("into"):                     # where the patterns' screws go, so the same pieces
            edge, face = by[s["into"]], by[s["on"]]
            g = marks._edge_on(edge, face, tol)
        else:                                                  # held without screws: whose edge, read the same way
            a, b = by[key[0]], by[key[1]]
            ga, gb = marks._edge_on(a, b, tol), marks._edge_on(b, a, tol)
            g, face, edge = (ga, b, a) if ga is not None and (gb is None or ga["length"] >= gb["length"]) else (gb, a, b)
        if g is None:
            out.append({**base, "unplaced": "one runs through or past the other, not an edge on its face"})
            continue
        t = float(edge["thickness"])
        sin = abs(float(marks._geom(face)[3] @ marks._geom(edge)[3])) if marks._sheet(face) and marks._sheet(edge) else 0.0
        out.append({**base, "edge": edge["key"], "face": face["key"], "out": np.asarray(g["out"], float),
                    "sin": sin, "edge_t": t,
                    "along": np.asarray(g["along"], float), "length_mm": float(g["length"]),
                    "area_mm2": float(g["length"]) * t, "mid": (np.asarray(g["a"]) + np.asarray(g["b"])) / 2.0,
                    "screws": int(s.get("n") or 0), "face_t": float(face["thickness"])})
    return {"joints": out, "pieces": pieces, "tol": tol, "screw_mm": fasteners.screw_length_mm(pieces)}


def split(joint: dict, force: np.ndarray, loaded: str) -> dict:
    """What a force does across a joint: ``{"bearing", "withdrawal", "shear"}``, each a magnitude in the force's units.
    ``force`` is what ``loaded`` (one of the joint's two pieces) puts through the joint into the other."""
    out = np.asarray(joint["out"], float)
    into = out if loaded == joint["edge"] else -out          # the way ``loaded`` pushes into the other
    f = np.asarray(force, float)
    push = float(f @ into)
    across = f - float(f @ out) * out
    return {"bearing": max(push, 0.0), "withdrawal": max(-push, 0.0), "shear": float(np.linalg.norm(across))}


def other(joint: dict, piece: str) -> Optional[str]:
    """The joint's other piece."""
    a, b = joint["pieces"]
    return b if piece == a else a if piece == b else None


# ---------------------------------------------------------------------------------------------------------------------------
# The statics: from where a load lands, down its supporting joints to what holds the part
# ---------------------------------------------------------------------------------------------------------------------------
#: How a piece held on more than two sides splits its load (#301 decision 5): "pairs", half each way (the pieces across it
#: one way, and across it the other), each pair by the lever rule; "ground", only the pieces that stand on what holds the
#: part, by the lever rule, while any do.
SHARE = "pairs"                          # pending: Theo (#301 decision 5; the foreman's pick, (a))
#: How many joints deep a load is followed before its path isn't a simple chain.
DEEPEST = 3
NOT_CHAIN = "its load path isn't a simple chain"
#: A splayed part whose feet nothing ties: their thrust has nowhere to go but the floor's grip (#311 review).
NO_TIE = "nothing ties its splayed sides"
#: A side leaning more than this off vertical is splayed: its foot pushes out.
SPLAY_DEG = 2.0


class NotChain(ValueError):
    """A load whose path down to what holds the part isn't one the hand check can follow. ``why``: its own words, for a
    person (never the exception's text, #311's CI: test_scrub_sweep)."""

    def __init__(self, why: str):
        super().__init__(why)
        self.why = why


def grounded(pieces: list[dict], held: list[dict], tol: float) -> set:
    """The pieces that touch what holds the part: a corner or an edge's middle within ``tol`` of a ``held`` box."""
    out = set()
    for pc in pieces:
        if pc["kind"] != "sheet":
            continue
        pts = np.vstack([np.vstack([p, (p + np.roll(p, -1, axis=0)) / 2.0]) for p in pc["polys"]])
        t = float(pc["thickness"])
        for side, p in zip(pc["sides"], pc["polys"]):            # both faces of the sheet
            from .consistency import _frame

            n = _frame(p)[3] * side
            pts = np.vstack([pts, p + n * t])
        for h in held:
            lo, hi = np.asarray(h["lo"], float) - tol, np.asarray(h["hi"], float) + tol
            if np.any(np.all((pts >= lo) & (pts <= hi), axis=1)):
                out.add(pc["key"])
                break
    return out


def loaded_piece(pieces: list[dict], load: dict) -> Optional[str]:
    """The sheet a load lands on: the nearest to its box's middle."""
    from .consistency import slab_distance

    c = (np.asarray(load["lo"], float) + np.asarray(load["hi"], float)) / 2.0
    best = None
    for pc in pieces:
        if pc["kind"] != "sheet":
            continue
        d = min(float(slab_distance(c[None, :], p, pc["thickness"], s)[0]) for p, s in zip(pc["polys"], pc["sides"]))
        if best is None or d < best[0]:
            best = (d, pc["key"])
    return best[1] if best else None


def _lever(mids: list[np.ndarray], at: np.ndarray, share: str) -> list[float]:
    """Each supporting joint's share of a load at ``at``: grouped by the way across the piece they lie (its two horizontal
    axes), a group's share by the lever rule between two on either side of the load, equally otherwise."""
    if len(mids) == 1:
        return [1.0]
    d = [m - at for m in mids]
    groups: dict[int, list[int]] = {}
    for i, v in enumerate(d):
        groups.setdefault(int(np.argmax(np.abs(v[:2]))), []).append(i)
    out = [0.0] * len(mids)
    each = 1.0 / len(groups)
    for axis, idx in groups.items():
        lo = [i for i in idx if d[i][axis] < 0]
        hi = [i for i in idx if d[i][axis] >= 0]
        if len(idx) == 2 and len(lo) == 1 and len(hi) == 1:
            a, b = abs(d[lo[0]][axis]), abs(d[hi[0]][axis])
            span = a + b or 1.0
            out[lo[0]], out[hi[0]] = each * b / span, each * a / span     # the nearer one carries more
        else:
            for i in idx:
                out[i] = each / len(idx)
    return out


def _into(joint: dict, piece: str) -> np.ndarray:
    """The way ``piece`` pushes into the joint's other piece."""
    out = np.asarray(joint["out"], float)
    return out if piece == joint["edge"] else -out


def _route(mine: list[dict], piece: str, f: np.ndarray, at: np.ndarray, share: str) -> list:
    """A piece's force among its supporting joints, axis by axis (#311 review: a push along a rail went half to each end, so
    one end was pulled out of its edge at 0x). Each component goes where the piece bears in that direction; where it bears
    nowhere, across the joints that can take it in shear; only where neither can, it pulls on them (withdrawal). Each
    share by the lever rule."""
    out = [np.zeros(3) for _ in mine]
    for axis in range(3):
        c = float(f[axis])
        if abs(c) < 1e-9:
            continue
        e = np.zeros(3)
        e[axis] = 1.0 if c > 0 else -1.0
        dots = [float(_into(j, piece) @ e) for j in mine]
        bear = [i for i, d in enumerate(dots) if d > 0.7]
        slide = [i for i, d in enumerate(dots) if abs(d) <= 0.7]
        take = bear or slide or list(range(len(mine)))
        for i, frac in zip(take, _lever([mine[i]["mid"] for i in take], at, share)):
            out[i][axis] += frac * c
    return list(zip(mine, out))


def _splay(pc: dict) -> Optional[tuple]:
    """A side leaning off vertical: ``(tan of its lean, the horizontal way its foot goes)``, or None. Its load runs down
    its line, so at the foot it pushes out by the load × that tan (#301, #311 review)."""
    from .consistency import _frame

    if pc["kind"] != "sheet":
        return None
    n = _frame(pc["polys"][0])[3]
    z = np.array([0.0, 0.0, 1.0])
    nz = abs(float(n @ z))
    if nz < np.sin(np.radians(SPLAY_DEG)) or nz > np.cos(np.radians(45.0)):
        return None                                           # upright, or lying down (a top, not a side)
    d = -z + float(z @ n) * n                                 # down its face
    d /= np.linalg.norm(d)
    h = d - float(d @ z) * z
    return float(np.linalg.norm(h) / abs(float(d @ z))), h / np.linalg.norm(h)


def demands(joints: list[dict], pieces: list[dict], load: dict, held: list[dict], tol: float,
            share: str = SHARE) -> dict:
    """What each joint carries under one load: ``{(a, b): {"from": the piece pushing, "force": N (3,)}}``. The load,
    × its factor, from the piece it lands on to the pieces holding it up, down to what holds the part; a splayed side's
    foot thrust into the tie between the feet. Raises :class:`NotChain` where that path can't be followed."""
    ground = grounded(pieces, held, tol)
    start = loaded_piece(pieces, load)
    if start is None:
        raise NotChain(NOT_CHAIN)
    by = {pc["key"]: pc for pc in pieces}
    splayed = {k: s for k in ground if k in by for s in [_splay(by[k])] if s is not None}
    placed = [j for j in joints if "unplaced" not in j]
    force = np.asarray(load["force"], float) * float(load["factor"])
    at = (np.asarray(load["lo"], float) + np.asarray(load["hi"], float)) / 2.0
    out: dict = {}
    arrived: dict = {}
    came_by: dict = {}                                        # the pieces that brought each side its load
    z = np.array([0.0, 0.0, 1.0])
    # how many joints each piece is from what holds the part: a piece is held up by those no farther from it than itself
    # (#311 review: a top read the shelf's other hanger, which hangs from it, as holding it up)
    far = {k: 0 for k in ground}
    edge = list(ground)
    while edge:
        nxt = []
        for k in edge:
            for j in placed:
                o = other(j, k)
                if o is not None and o not in far:
                    far[o] = far[k] + 1
                    nxt.append(o)
        edge = nxt

    def put(j: dict, piece: str, f: np.ndarray) -> None:
        got = out.setdefault(tuple(j["pieces"]), {"from": piece, "force": np.zeros(3)})
        got["force"] = got["force"] + f

    def down(piece: str, f: np.ndarray, at: np.ndarray, came: Optional[str], depth: int) -> None:
        if piece in ground:
            arrived[piece] = arrived.get(piece, np.zeros(3)) + f
            came_by.setdefault(piece, set()).add(came)
            return
        if depth > DEEPEST or piece not in far:
            raise NotChain(NOT_CHAIN)
        mine = [j for j in placed if piece in j["pieces"] and other(j, piece) != came
                and far.get(other(j, piece), DEEPEST + 9) <= far[piece]]
        if share == "ground" and any(other(j, piece) in ground for j in mine):
            mine = [j for j in mine if other(j, piece) in ground]
        if not mine:
            raise NotChain(NOT_CHAIN)
        for j, fj in _route(mine, piece, f, at, share):
            if not np.any(np.abs(fj) > 1e-9):
                continue
            to = other(j, piece)
            if to in splayed:                                 # down a leaning side's line: its top takes the lean too
                tan, h = splayed[to]
                fj = fj + max(0.0, -float(fj @ z)) * tan * h
            put(j, piece, fj)
            down(to, fj, j["mid"], piece, depth + 1)

    down(start, force, at, None, 0)
    for side, f in arrived.items():                           # each splayed foot's thrust, into the tie nearest it
        if side not in splayed:
            continue
        tan, h = splayed[side]
        push = max(0.0, -float(f @ z)) * tan
        if push <= 1e-9:
            continue
        # a tie: a piece joined to this side and another splayed one, not one that brought the load down (a step on top
        # holds the tops; it doesn't tie the feet)
        ties = [j for j in placed if side in j["pieces"] and other(j, side) not in came_by.get(side, set()) and any(
            other(j, side) in k["pieces"] and other(k, other(j, side)) in splayed and other(k, other(j, side)) != side
            for k in placed)]
        if not ties:
            raise NotChain(NO_TIE)
        put(min(ties, key=lambda j: float(j["mid"][2])), side, push * h)
    return out


# ---------------------------------------------------------------------------------------------------------------------------
# Capacities: mean ultimate, as the FEA's material strengths are (#301). Every number with its source, checked line by line
# (#301, issuecomment-6900765231). A #8 wood screw (shank 0.164 in) in 3/4 in plywood.
# ---------------------------------------------------------------------------------------------------------------------------
LBF = 4.4482216                          # N in a pound-force
IN = 25.4
#: Plywood's specific gravity when the plies' species isn't known: NDS 2018 Table 12.3.3B (p.88).
G_PLY = 0.42
SCREW_D_IN = 0.164                       # #8
#: Screw withdrawal from a face, lb per inch of thread, ultimate: NDS 2018 §12.2.2.1 Eq. 12.2-2 gives the design
#: W = 2850 G²D (82 lb/in at G 0.42, Table 12.2B), which is 1/5 of the ultimate (NDS 2005 Commentary C11.2.2.1, p.229).
WITHDRAW_FACE_LB_PER_IN = 5 * 2850 * G_PLY ** 2 * SCREW_D_IN
#: From an edge or end grain: no credit. NDS 2018 §12.2.2.3: "shall not be loaded in withdrawal from end grain"
#: (APA E830 Table 6 tested 360 lb for a #8 into a 3/4 in edge; "not normally recommended": not relied on).
WITHDRAW_EDGE_LB = 0.0                   # pending: Theo (#301 decision 2)
#: In shear into a face, ultimate: Z = 69 lb (NDS 2018 Table 12L, 3/4 in side, G 0.42) is "about 1/5 of maximum tested"
#: (NDS 2005 Commentary, p.231).
SHEAR_FACE_LB = 5 * 69.0
#: In shear into a plywood edge, ultimate: APA Technical Note E830 Table 6, a #8 into 3/4 in C-D plywood's edge, 1 in of
#: thread; scaled by the thread the bought screw has in the edge, never past what was tested (#301 decision 1).
SHEAR_EDGE_LB = 180.0                    # pending: Theo (#301 decision 1)
#: Thread in an edge E830's 180 lb was tested at.
SHEAR_EDGE_TESTED_IN = 1.0
#: Glue face to face, by the plywood's rolling shear: APA Plywood Design Specification Y510 (1997) Table 3, "All Other"
#: grades, dry, an allowable, not a mean (the safe side: #301 decision 3; the Wood Handbook's mean glue-line shear is
#: 207 psi, Table 12-2). For the face-glued joints (a glue block, a rabbet's or dado's cheeks) when their rule is added.
GLUE_FACE_PSI = 53.0                     # pending: Theo (#301 decision 3)
#: The same less 25% for a 3-layer panel over 5/8 in (Y510 Table 3 footnote 2): a panel whose plies aren't known is taken
#: as that.
GLUE_FACE_3PLY_PSI = 40.0                # pending: Theo (#301 decision 3)
#: Glue to an edge or end grain: no credit. Wood Handbook (2021) ch. 10, p.10-16: "practically impossible to make end-grain
#: butt joints… strong enough".
GLUE_EDGE_PSI = 0.0
#: Bearing on a plywood face: APA Panel Design Specification (2020) §4.4.7, p.19, a design value at 0.04 in deformation
#: (no plywood mean found): on the safe side.
BEARING_PSI = 360.0                      # pending: Theo (#301 decision 4), a design value
#: The kinds this check reads as an edge on a face. Others aren't checked until their own rules (a coupon for a dowel,
#: pocket screw or printed connector: #222's table has no sourced number for them).
EDGE_KINDS = ("butt", "bevel")


def capacity(joint: dict, screw_mm: float) -> dict:
    """What a joint of an edge on a face carries, N, mean ultimate, by mode: ``{"bearing", "withdrawal", "shear"}``, and
    ``{"why": {mode: what holds it, in words}}``. Screws go through the face piece into the edge piece's edge (the patterns'
    screw marks)."""
    area_in2 = joint["area_mm2"] / IN ** 2
    screwed = "screws" in joint["fix"] and joint["screws"] > 0
    n = joint["screws"] if screwed else 0
    from . import marks

    # the thread in the edge piece's wood: what's past the face piece, less what comes out of a bevel (#311 review)
    into_in = marks.thread_in(joint["face_t"], joint.get("edge_t", joint["face_t"]), joint.get("sin", 0.0), screw_mm) / IN
    per_shear = SHEAR_EDGE_LB * min(1.0, into_in / SHEAR_EDGE_TESTED_IN)
    glued = "glue" in joint["fix"]
    edge = joint["edge"]
    screws_said = f"{_count(n)} #8 screw{'s' if n != 1 else ''}"
    return {"bearing": BEARING_PSI * area_in2 * LBF,
            "withdrawal": (n * WITHDRAW_EDGE_LB + (GLUE_EDGE_PSI * area_in2 if glued else 0.0)) * LBF,
            "shear": (n * per_shear + (GLUE_EDGE_PSI * area_in2 if glued else 0.0)) * LBF,
            "why": {"bearing": f"the {edge}'s edge bearing on the {joint['face']}",
                    "withdrawal": f"{screws_said} pulled out of the {edge}'s edge" if n
                    else f"nothing holding the {edge}'s edge to the {joint['face']}",
                    "shear": f"{screws_said} in shear into the {edge}'s edge" if n
                    else f"glue alone on the {edge}'s edge"}}


def _count(n: int) -> str:
    return ["no", "one", "two", "three", "four", "five", "six"][n] if 0 <= n <= 6 else str(n)


def check(setup_: dict, load: dict, held: list[dict], min_safety: float, share: str = SHARE) -> dict:
    """One load case's joints: ``{"rows": [...], "governing": the lowest row or None, "unchecked": [why, ...]}``. A row:
    ``{"pieces", "between": "the step and the left side", "mode", "safety", "need", "holds", "said": what gives first}``;
    ``safety`` is the joint's capacity over its share of the load × factor, against the run's ``min_safety`` as the wood's
    is (Theo: "the same safety factor that the rest of the stool is checked at")."""
    joints = setup_["joints"]
    unchecked = [f"the joint between the {j['pieces'][0]} and the {j['pieces'][1]} ({j['unplaced']})"
                 for j in joints if "unplaced" in j]
    unchecked += [f"the joint between the {j['pieces'][0]} and the {j['pieces'][1]} (a {j['kind']})"
                  for j in joints if "unplaced" not in j and j.get("kind") not in EDGE_KINDS]
    try:
        got = demands(joints, setup_["pieces"], load, held, setup_["tol"], share)
    except NotChain as e:
        return {"rows": [], "governing": None, "unchecked": [e.why], "chain": False, "n": len(joints)}
    rows = []
    for j in joints:
        if "unplaced" in j or j.get("kind") not in EDGE_KINDS:
            continue
        d = got.get(tuple(j["pieces"]))
        first = d["from"] if d else j["face"]                  # the piece that pushes, then the one that holds it
        between = f"the {first} and the {other(j, first)}"
        if d is None:
            rows.append({"pieces": j["pieces"], "between": between, "mode": None, "safety": None, "holds": True,
                         "said": "carries none of this load"})
            continue
        parts = split(j, d["force"], d["from"])
        cap = capacity(j, setup_["screw_mm"])
        by = {m: (cap[m] / parts[m] if cap[m] > 0 else 0.0) for m in ("bearing", "withdrawal", "shear") if parts[m] > 1e-6}
        mode = min(by, key=by.get) if by else None
        from . import verdicts as V

        safety = V.cut(by[mode]) if mode else None             # cut toward safe, as every producer's (CALI-152)
        rows.append({"pieces": j["pieces"], "between": between, "edge": j["edge"], "face": j["face"], "mode": mode,
                     "safety": safety, "need": min_safety, "verdict": V.meets(safety, min_safety),
                     "holds": safety is None or safety >= min_safety,  # producer
                     "demand_lb": {m: round(v / LBF, 1) for m, v in parts.items() if v > 1e-6},
                     "capacity_lb": {m: round(cap[m] / LBF, 1) for m in by},
                     "said": cap["why"][mode] if mode else "carries none of this load", "assumed": j["assumed"]})
    rated = [r for r in rows if r["safety"] is not None]
    return {"rows": rows, "governing": min(rated, key=lambda r: r["safety"]) if rated else None,
            "unchecked": unchecked, "chain": True, "n": len(joints)}


#: The hand checks: a case they govern keeps, as ``over``, the check they took over from (``load_study.judged_by``).
HAND = ("buckling", "joint")


def lower(case: dict, governs: str, safety: Optional[float]) -> tuple:
    """A case's ``(governs, safety)`` with its joints in: the joint governs where it's the lowest (#301, the same path
    buckling's number takes). Sets ``over`` where it takes over from a check that isn't a hand check."""
    g = (case.get("joints") or {}).get("governing")
    if g and g.get("safety") is not None and (safety is None or g["safety"] < safety):
        if governs not in HAND:
            case["over"] = governs
        return "joint", g["safety"]
    return governs, safety
