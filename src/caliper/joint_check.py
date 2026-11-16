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
        if c["how"] in ("through", "notch") or c["how"] == "edge" and not _edged(key, by, s, tol):
            got = _notch(by[key[0]], by[key[1]], tol) or _notch(by[key[1]], by[key[0]], tol)
            if got is not None:                   # one run through or into the other's notch (CALI-192)
                out.append({**base, **got})
                continue
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
        normal = np.asarray(marks._geom(face)[3], float) if marks._sheet(face) else np.asarray(g["out"], float)
        normal = normal if float(normal @ np.asarray(g["out"], float)) >= 0 else -normal
        out.append({**base, "edge": edge["key"], "face": face["key"], "out": np.asarray(g["out"], float),
                    "normal": normal / (np.linalg.norm(normal) or 1.0),   # the face it bears on, from the edge into it
                    "sin": sin, "edge_t": t,
                    "along": np.asarray(g["along"], float), "length_mm": float(g["length"]),
                    "area_mm2": float(g["length"]) * t, "mid": (np.asarray(g["a"]) + np.asarray(g["b"])) / 2.0,
                    "screws": int(s.get("n") or 0), "face_t": float(face["thickness"])})
    return {"joints": out, "pieces": pieces, "tol": tol, "screw_mm": fasteners.screw_length_mm(pieces)}


def _edged(key: tuple, by: dict, s: dict, tol: float) -> bool:
    """Whether a contact reads as an edge on a face, the way the patterns' screw marks read it."""
    from . import marks

    if s.get("on") and s.get("into"):
        return marks._edge_on(by[s["into"]], by[s["on"]], tol) is not None
    a, b = by[key[0]], by[key[1]]
    return marks._edge_on(a, b, tol) is not None or marks._edge_on(b, a, tol) is not None


def _notch(host: dict, piece: dict, tol: float) -> Optional[dict]:
    """``piece`` run through a notch or mortise in ``host`` (CALI-192, v7's stringer through its sides): where it crosses
    the host's plane, a rectangle (its line there, by its thickness), each face of it closed where the host has wood just
    past it and open where it doesn't (a notch cut from an edge). None where it doesn't cross the host."""
    from .consistency import _frame, _inside2d

    if host.get("kind") != "sheet" or piece.get("kind") != "sheet" or not host.get("sides") or not piece.get("sides"):
        return None
    o, u, v, n, flat = _frame(host["polys"][0])
    ht, pt = float(host["thickness"]), float(piece["thickness"])
    hn = n * host["sides"][0]
    centre = o + hn * ht / 2.0                                # the host's middle plane
    P = np.asarray(piece["polys"][0], float)
    pn = _frame(P)[3] * piece["sides"][0]
    Pm = P + pn * pt / 2.0                                    # the piece's middle plane
    d = (Pm - centre) @ hn
    if d.min() > -ht / 2.0 + tol or d.max() < ht / 2.0 - tol:
        return None                                           # it doesn't run through the host's thickness
    pts = []
    for i in range(len(Pm)):
        a, b = Pm[i], Pm[(i + 1) % len(Pm)]
        da, db = d[i], d[(i + 1) % len(Pm)]
        if abs(da) < 1e-9:
            pts.append(a)
        elif da * db < 0:
            pts.append(a + (b - a) * (da / (da - db)))
    if len(pts) < 2:
        return None
    pts = np.asarray(pts)
    g = pts[-1] - pts[0]
    if np.linalg.norm(g) < 1e-6:
        return None
    g /= np.linalg.norm(g)
    along = pts @ g
    a, b = pts[int(np.argmin(along))], pts[int(np.argmax(along))]
    length = float(np.linalg.norm(b - a))
    if length <= tol:
        return None
    mid = (a + b) / 2.0
    across = pn - float(pn @ hn) * hn
    across /= np.linalg.norm(across) or 1.0
    to2d = lambda q: np.array([[(q - o) @ u, (q - o) @ v]])
    if not (flat.min(axis=0) - tol <= to2d(mid)[0]).all() or not (to2d(mid)[0] <= flat.max(axis=0) + tol).all():
        return None                                           # it isn't in the host's outline: the other way round
    faces = []
    for normal, half, face_len in ((across, pt / 2.0, length), (-across, pt / 2.0, length), (g, length / 2.0, pt),
                                   (-g, length / 2.0, pt)):
        past = mid + normal * (half + 2.0)
        faces.append({"normal": normal.copy(), "area_mm2": face_len * ht, "open": not bool(_inside2d(to2d(past), flat)[0])})
    return {"notch": True, "host": host["key"], "piece": piece["key"], "faces": faces, "axis": hn.copy(), "mid": mid,
            "along": g.copy(), "length_mm": length, "top_z": float(max(a[2], b[2]) if abs(g[2]) > 0.5 else mid[2])}


def split(joint: dict, force: np.ndarray, loaded: str) -> dict:
    """What a force does across a joint: ``{"bearing", "withdrawal", "shear"}``, each a magnitude in the force's units.
    ``force`` is what ``loaded`` (one of the joint's two pieces) puts through the joint into the other."""
    out = _face(joint)                                        # against the face it bears on (#311 re-check B)
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
SHARE = "pairs"                          # interim, see #316 (CALI-194) (#301 decision 5; the foreman's pick, (a))
#: How many joints deep a load is followed before its path isn't a simple chain.
DEEPEST = 3
NOT_CHAIN = "its load path isn't a simple chain"
#: A splayed part whose feet nothing ties: their thrust has nowhere to go but the floor's grip (#311 review).
NO_TIE = "nothing ties its splayed sides"
#: Three or more supports in a row under one piece: which carries what isn't settled by statics alone (#311).
IN_A_ROW = "it rests on three or more supports in a row"
#: More supports one way across a piece than the other: no simple share either way (#311).
UNEVEN = "it rests on more supports one way than the other"
#: Held both ways by supports that don't run most of the way across: how the load splits needs more than halves (#311).
SHORT = "its supports are short, so how the load splits isn't simple"
#: "Most of the way across": a support's joint at least this share of the piece's width along it (interim with
#: decision 5, see #316, CALI-194).
MOST_OF_THE_WAY = 0.75
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


def _lever(mids: list[np.ndarray], at: np.ndarray, share: str, spans: Optional[list] = None) -> list[float]:
    """Each supporting joint's share of a load at ``at``: grouped by the way across the piece they lie (its two horizontal
    axes, as they lie from each other), a group's share by statics. Two in a group share it by the lever rule, a load past
    them included: the near one
    then carries more than all of it and the far one is lifted, a negative share, so its joint takes a pull (#311: it read
    half each). Three or more in a row are statically indeterminate: not checked by hand, never a third each. ``spans``:
    each support's joint length and the piece's width the same way; held both ways ("half each way", decision 5), each
    pair takes only half the load's moment, which holds only where every support runs most of the way across (#311:
    a ring of four posts read the near one at 0.475 where statics needs 0.9 or more), so short ones aren't checked."""
    if len(mids) == 1:
        return [1.0]
    # grouped by how they lie from each other, never from the load (#311: a load near one edge read its pair as two):
    # each with the support farthest from it, along the horizontal axis the two differ in most
    groups: dict[int, list[int]] = {}
    for i, m in enumerate(mids):
        sp = spans[i] if spans else None
        if sp is not None and len(sp) > 2 and sp[0] >= MOST_OF_THE_WAY * sp[1]:
            along = np.asarray(sp[2], float)                  # a support across the piece pairs across its own line
            axis = int(np.argmin(np.abs(along[:2])))
        else:
            far = max((j for j in range(len(mids)) if j != i), key=lambda j: float(np.linalg.norm((mids[j] - m)[:2])))
            axis = int(np.argmax(np.abs((mids[far] - m)[:2])))
        groups.setdefault(axis, []).append(i)
    out = [0.0] * len(mids)
    each = 1.0 / len(groups)
    short = bool(spans) and any(sp[0] < MOST_OF_THE_WAY * sp[1] for sp in spans)
    if len(groups) > 1:
        if any(len(idx) > 2 for idx in groups.values()):
            raise NotChain(UNEVEN)
        if short:
            raise NotChain(SHORT)
    elif short and len(mids) == 2:          # two posts: nothing stops it turning about their line, off it (#311)
        line = (mids[1] - mids[0])[:2]
        off = abs(float(np.cross(line / (np.linalg.norm(line) or 1.0), (at - mids[0])[:2])))
        if off > 1.0:
            raise NotChain(SHORT)
    for axis, idx in groups.items():
        xs = [float(mids[i][axis]) for i in idx]
        if len(idx) == 1:
            out[idx[0]] = each
        elif len({round(x, 3) for x in xs}) == 1:          # side by side, not along it: equal
            for i in idx:
                out[i] = each / len(idx)
        elif len(idx) == 2:
            (a, b), x = xs, float(at[axis])
            out[idx[0]], out[idx[1]] = each * (b - x) / (b - a), each * (x - a) / (b - a)
        else:                                                 # three or more one way: in a row, or not
            other = 1 - axis
            spread = [float(mids[i][axis]) for i in idx], [float(mids[i][other]) for i in idx]
            raise NotChain(IN_A_ROW if np.ptp(spread[1]) <= 0.1 * np.ptp(spread[0]) else UNEVEN)
    return out


def _face(joint: dict) -> np.ndarray:
    """The normal of the face a joint bears on, from the edge piece into it: what bearing, withdrawal and shear are read
    against (#301: "the load's direction against the joint face"; #311 re-check B: not the edge's own direction, which on a
    splayed side's top read the push down its line as all bearing, 266 lb at 20°, where 91 lb of it crosses the screws)."""
    return np.asarray(joint.get("normal", joint["out"]), float)


def _bears(joint: dict, piece: str) -> list:
    """The ways ``piece`` pushes that a notch joint bears: on its closed faces (CALI-192)."""
    sign = 1.0 if piece == joint["piece"] else -1.0
    return [sign * np.asarray(f["normal"], float) for f in joint["faces"] if not f["open"]]


def _into(joint: dict, piece: str) -> np.ndarray:
    """The way ``piece`` pushes into the joint's other piece."""
    out = _face(joint)
    return out if piece == joint["edge"] else -out


def _across(pieces: dict, piece: str, along) -> float:
    """How wide a piece is the way a joint runs: its outline's spread along that direction, mm."""
    pc = pieces.get(piece)
    if pc is None or not pc.get("polys"):
        return 0.0
    pts = np.vstack(pc["polys"])
    return float(np.ptp(pts @ np.asarray(along, float)))


def _route(mine: list[dict], piece: str, f: np.ndarray, at: np.ndarray, share: str, pieces: Optional[dict] = None) -> list:
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
        dots = [None if j.get("notch") else float(_into(j, piece) @ e) for j in mine]
        bear = [i for i, (j, d) in enumerate(zip(mine, dots))
                if (d is None and any(float(n @ e) > 0.7 for n in _bears(j, piece))) or (d is not None and d > 0.7)]
        slide = [i for i, d in enumerate(dots) if d is not None and abs(d) <= 0.7]
        take = bear or slide or list(range(len(mine)))
        for i, frac in zip(take, _lever([mine[i]["mid"] for i in take], at, share,
                                        [(float(mine[i]["length_mm"]), _across(pieces, piece, mine[i]["along"]),
                                          mine[i]["along"]) for i in take] if pieces else None)):
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
            share: str = SHARE, arrivals: Optional[dict] = None) -> dict:
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
        for j, fj in _route(mine, piece, f, at, share, by):
            if not np.any(np.abs(fj) > 1e-9):
                continue
            to = other(j, piece)
            if to in splayed:                                 # down a leaning side's line: its top takes the lean too
                tan, h = splayed[to]
                fj = fj + max(0.0, -float(fj @ z)) * tan * h
            put(j, piece, fj)
            down(to, fj, j["mid"], piece, depth + 1)

    down(start, force, at, None, 0)
    if arrivals is not None:
        arrivals.update(arrived)
    pulls: dict = {}                                          # each tie's ends, and the thrust at each
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
            raise NotChain(_untied(joints, side, splayed, came_by.get(side, set())))
        tie = min(ties, key=lambda j: float(j["mid"][2]))
        pulls.setdefault(other(tie, side), []).append((tie, side, push, h))
    for ends in pulls.values():                               # a tie carries one tension: each end the larger (#311 re-check A)
        most = max(p for _, _, p, _ in ends)
        for tie, side, _, h in ends:
            put(tie, side, most * h)
    return out


def _untied(joints: list[dict], side: str, splayed: dict, came: set) -> str:
    """Why a splayed foot's thrust has no tie the check can follow: a tie that's there but it can't place (v7's stringer,
    through notches in its sides: CALI-192), named; else none (#311 re-check C)."""
    for j in joints:
        t = other(j, side)
        if "unplaced" not in j or t is None or t in came:
            continue
        if any(other(k, t) in splayed and other(k, t) != side for k in joints):
            return f"its tie, the {t}, isn't checked by hand: {j['unplaced']}"
    return NO_TIE


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
WITHDRAW_EDGE_LB = 0.0                   # Theo, 2026-11-16 (#301 decision 2)
#: In shear into a face, ultimate: Z = 69 lb (NDS 2018 Table 12L, 3/4 in side, G 0.42) is "about 1/5 of maximum tested"
#: (NDS 2005 Commentary, p.231).
SHEAR_FACE_LB = 5 * 69.0
#: In shear into a plywood edge, ultimate: APA Technical Note E830 Table 6, a #8 into 3/4 in C-D plywood's edge, 1 in of
#: thread; scaled by the thread the bought screw has in the edge, never past what was tested (#301 decision 1).
SHEAR_EDGE_LB = 180.0                    # Theo, 2026-11-16 (#301 decision 1)
#: Thread in an edge E830's 180 lb was tested at.
SHEAR_EDGE_TESTED_IN = 1.0
#: Glue face to face, by the plywood's rolling shear: APA Plywood Design Specification Y510 (1997) Table 3, "All Other"
#: grades, dry, an allowable, not a mean (the safe side: #301 decision 3; the Wood Handbook's mean glue-line shear is
#: 207 psi, Table 12-2). For the face-glued joints (a glue block, a rabbet's or dado's cheeks) when their rule is added.
GLUE_FACE_PSI = 53.0                     # Theo, 2026-11-16 (#301 decision 3)
#: The same less 25% for a 3-layer panel over 5/8 in (Y510 Table 3 footnote 2): a panel whose plies aren't known is taken
#: as that.
GLUE_FACE_3PLY_PSI = 40.0                # Theo, 2026-11-16 (#301 decision 3)
#: Glue to an edge or end grain: no credit. Wood Handbook (2021) ch. 10, p.10-16: "practically impossible to make end-grain
#: butt joints… strong enough".
GLUE_EDGE_PSI = 0.0
#: Bearing on a plywood face: APA Panel Design Specification (2020) §4.4.7, p.19, a design value at 0.04 in deformation
#: (no plywood mean found): on the safe side.
BEARING_PSI = 360.0                      # Theo, 2026-11-16 (#301 decision 4), a design value
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


def check(setup_: dict, load: dict, held: list[dict], min_safety: float, share: str = SHARE,
          mat: Optional[dict] = None) -> dict:
    """One load case's joints: ``{"rows": [...], "governing": the lowest row or None, "unchecked": [why, ...]}``. A row:
    ``{"pieces", "between": "the step and the left side", "mode", "safety", "need", "holds", "said": what gives first}``;
    ``safety`` is the joint's capacity over its share of the load × factor, against the run's ``min_safety`` as the wood's
    is (Theo: "the same safety factor that the rest of the stool is checked at")."""
    joints = setup_["joints"]
    unchecked = [f"the joint between the {j['pieces'][0]} and the {j['pieces'][1]} ({j['unplaced']})"
                 for j in joints if "unplaced" in j]
    unchecked += [f"the joint between the {j['pieces'][0]} and the {j['pieces'][1]} (a {j['kind']})"
                  for j in joints if "unplaced" not in j and not j.get("notch") and j.get("kind") not in EDGE_KINDS]
    arrived: dict = {}
    try:
        got = demands(joints, setup_["pieces"], load, held, setup_["tol"], share, arrivals=arrived)
    except NotChain as e:
        return {"rows": [], "governing": None, "unchecked": [e.why], "chain": False, "n": len(joints)}
    rows = []
    hosts = {}
    for j in joints:
        if j.get("notch"):                                    # a notch joint by its own rule (CALI-192)
            d = got.get(tuple(j["pieces"]))
            rows.append(notch_row(j, d["force"], d["from"], min_safety) if d else
                        {"pieces": j["pieces"], "between": f"the {j['piece']} and the {j['host']}", "mode": None,
                         "safety": None, "holds": True, "said": "carries none of this load"})
            hosts.setdefault(j["host"], j)
            continue
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
    f = np.asarray(load["force"], float)
    if float(np.linalg.norm(f[:2])) > 1e-6 * (float(np.linalg.norm(f)) or 1.0):
        # pushed sideways at all: a joint carries none only because the statics hold each side at the floor; racked, a
        # stringer or rail would take the push. So it's said, and named as not checked, never a plain pass (#313 review)
        for r in rows:
            if r["mode"] is None:
                r["said"] = RACKING_SAID
                unchecked.append(f"the joint between {r['between']} ({RACKING_SAID})")
    by = {pc["key"]: pc for pc in setup_["pieces"]}
    for host, j in hosts.items():                             # each notched side, past its notch: net section by hand
        f = arrived.get(host)
        down = max(0.0, -float(f[2])) if f is not None else 0.0
        if host in by and down > 1e-9:
            if mat is None:
                unchecked.append(f"the {host} past its notch (its material isn't known here)")
            else:
                rows.append(net_row(by[host], j["top_z"], down, mat, min_safety))
    rated = [r for r in rows if r["safety"] is not None]
    return {"rows": rows, "governing": min(rated, key=lambda r: r["safety"]) if rated else None,
            "unchecked": unchecked, "chain": True, "n": len(joints)}


#: What a joint said to carry none of a case with a sideways push says (#313 review): the statics hold each side at the
#: floor, so nothing racks; whether a stringer or rail holds it square isn't checked.
RACKING_SAID = "carries none with the sides held at the floor: racking isn't checked"


def notch_row(joint: dict, force: np.ndarray, frm: str, min_safety: float) -> dict:
    """A notch joint under a force ``frm`` puts through it (CALI-192). The piece bears on the notch's closed faces (at
    :data:`BEARING_PSI`); pushed toward an open face it lifts out, and along its own length nothing in a notch holds a
    pull, glue to the host's edge grain no credit (#301). The lowest of these governs."""
    from . import verdicts as V

    piece, host = joint["piece"], joint["host"]
    f = np.asarray(force, float) if frm == piece else -np.asarray(force, float)      # what the piece puts into the host
    parts = []
    pull = abs(float(f @ np.asarray(joint["axis"], float)))
    if pull > 1e-6:
        how = ("glue to the {h}'s edge grain" if "glue" in joint["fix"] else
               "screws into its end grain" if "screws" in joint["fix"] else "nothing holds it")
        parts.append(("withdrawal", pull, 0.0,
                      f"the {piece}'s notch can't hold a pull along it: {how.format(h=host)}, no credit"))
    for face in joint["faces"]:
        c = float(f @ np.asarray(face["normal"], float))
        if c <= 1e-6:
            continue
        if face["open"]:
            parts.append(("withdrawal", c, 0.0, f"the {piece} lifts out of the {host}'s notch: nothing holds it"))
        else:
            parts.append(("bearing", c, BEARING_PSI * face["area_mm2"] / IN ** 2 * LBF,
                          f"the {piece} bearing on the {host}'s notch"))
    between = f"the {frm} and the {host if frm == piece else piece}"
    if not parts:
        return {"pieces": joint["pieces"], "between": between, "mode": None, "safety": None, "holds": True,
                "said": "carries none of this load"}
    mode, demand, cap, said = min(parts, key=lambda p: p[2] / p[1])
    safety = V.cut(cap / demand)
    return {"pieces": joint["pieces"], "between": between, "mode": mode, "safety": safety, "need": min_safety,
            "verdict": V.meets(safety, min_safety), "holds": safety >= min_safety,  # producer
            "demand_lb": {mode: round(demand / LBF, 1)}, "capacity_lb": {mode: round(cap / LBF, 1)}, "said": said,
            "assumed": joint.get("assumed", False)}


#: What a side's net section past its notch is said as (CALI-192): by hand, the stress at the corner not allowed for.
NET_SAID = "net section, no allowance for the stress at the notch's corner"


def _width_at(pc: dict, z: float) -> float:
    """How much of a sheet's outline is left across it at height ``z``: the even-odd lengths of its outline cut there."""
    P = np.asarray(pc["polys"][0], float)
    pts = []
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        if (a[2] - z) * (b[2] - z) < 0:
            pts.append(a + (b - a) * ((z - a[2]) / (b[2] - a[2])))
    if len(pts) < 2:
        return 0.0
    pts = np.asarray(pts)
    g = pts[-1] - pts[0]
    g /= np.linalg.norm(g) or 1.0
    xs = sorted(float(p @ g) for p in pts)
    return float(sum(xs[i + 1] - xs[i] for i in range(0, len(xs) - 1, 2)))


def net_row(host: dict, top_z: float, down_n: float, mat: dict, min_safety: float) -> dict:
    """A side's net section past its notch (CALI-192, the foreman's call): the vertical load it carries over the width
    left just under the notch's top × its thickness, against the strength the FEA judges it by, taken the weaker way for
    plywood (``across``), as the plate check does."""
    from . import verdicts as V

    width = _width_at(host, top_z - 1.0)
    area = width * float(host["thickness"])
    strength = float(mat["strength"]) * float(mat.get("across", 1.0))
    cap = strength * area
    safety = V.cut(cap / down_n) if down_n > 0 else None
    return {"pieces": [host["key"]], "between": f"the {host['key']} past its notch", "mode": "net section",
            "safety": safety, "need": min_safety, "verdict": V.meets(safety, min_safety),
            "holds": safety is None or safety >= min_safety,  # producer
            "demand_lb": {"net section": round(down_n / LBF, 1)}, "capacity_lb": {"net section": round(cap / LBF, 1)},
            "said": NET_SAID, "assumed": False}


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
