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

from typing import Callable, Optional

import math

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
    mesh = store.part_local(pid).require_mesh()
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
        a_, b_ = by[key[0]], by[key[1]]
        stick, sheet = ((a_, b_) if a_["kind"] == "stick" and b_["kind"] == "sheet" else
                        (b_, a_) if b_["kind"] == "stick" and a_["kind"] == "sheet" else (None, None))
        if stick is not None:                     # a post under a top, an apron's end on a leg (#316)
            got = _post(stick, sheet, tol, mesh) or _apron(sheet, stick, tol)
            if got is not None and got.get("mismatch"):   # declared one way, built the other (#321): not checked
                out.append({**base, "unplaced": got["mismatch"], "mismatch": True})
                continue
            if got is not None and "short" in got:       # short in both: no joint, said as that, not unchecked
                out.append({**base, "short": got["short"], "said": got["said"]})
                continue
            if got is not None:
                out.append({**base, **got, "screws": int(s.get("n") or 0), "points": list(s.get("points") or []),
                            **({"crowded": s["crowded"]} if s.get("crowded") else {})})
                continue
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
                    "screws": int(s.get("n") or 0), "points": list(s.get("points") or []),
                            **({"crowded": s["crowded"]} if s.get("crowded") else {}),
                    "face_t": float(face["thickness"])})
    return {"joints": out, "pieces": pieces, "tol": tol, "screw_mm": fasteners.screw_length_mm(pieces)}


def _edged(key: tuple, by: dict, s: dict, tol: float) -> bool:
    """Whether a contact reads as an edge on a face, the way the patterns' screw marks read it."""
    from . import marks

    if s.get("on") and s.get("into"):
        return marks._edge_on(by[s["into"]], by[s["on"]], tol) is not None
    a, b = by[key[0]], by[key[1]]
    return marks._edge_on(a, b, tol) is not None or marks._edge_on(b, a, tol) is not None


def _stick_axis(stick: dict) -> tuple:
    a, b = np.asarray(stick["a"], float), np.asarray(stick["b"], float)
    L = float(np.linalg.norm(b - a)) or 1.0
    return a, b, (b - a) / L, L


#: How close a post's declared end must be to a top's declared face to bear on it (#321): both are the script's own
#: numbers, so a gap is a gap; the mesh's tolerance (tessellation, a builder's rounding: 3.6 mm on a 400 mm stool) would
#: read a leg 3 mm short as bearing.
BEARS_MM = 0.5


#: Where across a leg's end its rays start (#321 re-check): the centre, and four toward its corners at this share of its
#: half-width along each side. It stays on the flat of an 8 mm chamfer, and within about 0.1 mm of a 15 mm round, on a 2x2.
RAY_AT = 0.3
#: A leg bears where all its counted rays but at most this many touch (#321, the foreman): "any" read a dowel stub with
#: its shoulder 3 mm short ([0, 3, 3, 3, 3]) as bearing over its whole end, 2.93 where it's about 0.16.
BEARS_ALL_BUT = 1


def _built_gap(mesh, end: np.ndarray, into: np.ndarray, face_at: float, half: float,
               across: np.ndarray) -> Optional[list]:
    """How far short of a top's face the built solid's leg stops, mm, measured on the mesh's faces (#321): rays from
    5 mm inside the leg, along it toward the top, at its centre and four toward its corners (:data:`RAY_AT`), each
    one's reading in that order. Only the rays that start inside the solid count: a hole down the leg's middle (a
    dowel's, a pilot's, a hollow print) would let one run up it and across a gap. Where the solid runs on past the
    face: 0. None where no ray starts inside it. :func:`_post` reads them (:data:`BEARS_ALL_BUT`)."""
    from . import spatial

    end, into = np.asarray(end, float), np.asarray(into, float)
    e1 = np.asarray(across, float) - into * float(np.asarray(across, float) @ into)
    e1 = e1 / (np.linalg.norm(e1) or 1.0)
    e2 = np.cross(into, e1)
    off = RAY_AT * float(half)
    starts = [end - into * 5.0 + off * (i * e1 + j * e2) for i, j in ((0, 0), (1, 1), (1, -1), (-1, 1), (-1, -1))]
    try:
        kept = [s for s, inside in zip(starts, spatial.contains(mesh, np.array(starts))) if inside]
        gaps = []
        for start in kept:
            locs, _, _ = spatial.intersects_location(mesh, [start], [into])
            ahead = sorted(float((loc - start) @ into) for loc in locs if float((loc - start) @ into) > 1e-6)
            if ahead:
                gaps.append(max(0.0, 5.0 + face_at - ahead[0]))     # the top's face, from the ray's start
    except Exception:  # noqa: BLE001 — no ray test here: not measured, said by the caller
        return None
    return gaps or None


def _post(stick: dict, sheet: dict, tol: float, mesh=None) -> Optional[dict]:
    """A stick standing square to a sheet with an end at its face, inside its outline: a post bearing into a top (#316).
    ``normal`` from the post into the sheet; its area the post's end; its span the post's own width (a post is short
    against any top), so a top on posts shares by the rigid-top rule.

    It bears only where its declared end is within :data:`BEARS_MM` of the face **and** the built solid shows it touching
    (#321: either alone read a 3 mm gap one way or the other). Short in both: ``{"short": mm}``, said as that, not a joint.
    Where they disagree: ``{"mismatch": why}``, and the case isn't checked by hand."""
    from . import marks
    from .consistency import _inside2d

    o, u, v, N, t, poly, flat = marks._geom(sheet)
    a, b, ax, L = _stick_axis(stick)
    if abs(float(ax @ N)) < 0.9:
        return None
    for end, inward in ((a, ax), (b, -ax)):             # inward: from that end along the post
        d = float((end - o) @ N)                         # how far the end sits through the sheet's thickness
        below = float(inward @ N) > 0                    # the post on the side the thickness goes to
        gap = d - t if below else -d                     # short of the face it would bear on: positive
        if abs(gap) > max(tol, BEARS_MM) or not _inside2d(
                np.array([[float((end - o) @ u), float((end - o) @ v)]]), flat)[0]:
            continue
        into = -inward                                    # from the post into the sheet
        declared = abs(gap) <= BEARS_MM
        rays = (_built_gap(mesh, end, into, max(gap, 0.0), float(stick["half"]), u) if mesh is not None else
                [0.0 if declared else gap])
        name = stick["key"]
        if rays is None:                                 # no ray across its end starts in the solid: not measured
            return {"mismatch": f"the {name}'s built end at the {sheet['key']} isn't measured: no ray across it starts "
                                "inside the solid"}
        if len(rays) <= BEARS_ALL_BUT + 1:               # two or fewer: "all but one" would be "any" (#321 review)
            return {"mismatch": f"the {name}'s built end at the {sheet['key']} isn't measured: only {_count(len(rays))} "
                                f"of its rays start{'s' if len(rays) == 1 else ''} inside the solid"}
        touch = sum(1 for r in rays if r <= BEARS_MM)
        if 0 < touch < len(rays) - BEARS_ALL_BUT:        # some of its end touches, not all: no bearing area to take
            return {"mismatch": f"the {name} touches the {sheet['key']} at only part of its end"}
        built = touch > 0
        built_gap = min(rays)
        if declared != built:
            said = (f"the {name} is declared flush with the {sheet['key']} but built {built_gap:.1f} mm short"
                    if declared else
                    f"the {name} is declared {gap:.1f} mm short of the {sheet['key']} but built flush")
            return {"mismatch": said.replace(".0 mm", " mm")}
        if not declared:
            return {"short": gap, "said": f"the {name} stops {gap:.1f} mm short of the {sheet['key']}: it doesn't bear"
                    .replace(".0 mm", " mm")}
        width = 2.0 * float(stick["half"])
        area = float(stick["volume"]) / L               # its section, as consistency weighed it
        return {"edge": stick["key"], "face": sheet["key"], "post": True, "out": into, "normal": into,
                "sin": 0.0, "edge_t": width, "along": u, "length_mm": width, "area_mm2": area, "mid": end,
                "face_t": t}
    return None


def _apron(sheet: dict, stick: dict, tol: float) -> Optional[dict]:
    """A sheet's edge, along a stick, against its side: an apron's end on a leg (#316). ``normal`` from the apron into
    the leg; its span the overlap along the leg."""
    from . import marks

    o, u, v, N, t, poly, flat = marks._geom(sheet)
    a, b, ax, L = _stick_axis(stick)
    half = float(stick["half"])
    for _, p, q, d, out in marks._edges(sheet):
        if abs(float(d @ ax)) < 0.95:
            continue
        m = (p + q) / 2.0
        rel = a + ax * float((m - a) @ ax) - m                    # beside the edge's middle: a raked leg's foot is far off
        beyond, across = float(rel @ out), float(rel @ N)         # the leg's axis past the edge, and through the sheet
        if abs(beyond - half) > 2 * tol or across + half < -tol or across - half > t + tol:
            continue
        s0, s1 = sorted((float((p - a) @ ax), float((q - a) @ ax)))
        lo, hi = max(s0, 0.0), min(s1, L)
        if hi - lo <= tol:
            continue
        mid = a + ax * (lo + hi) / 2.0 + (p - a - ax * float((p - a) @ ax))     # on the edge, halfway up the overlap
        return {"edge": sheet["key"], "face": stick["key"], "apron": True, "out": out, "normal": out, "sin": 0.0,
                "edge_t": t, "along": ax, "length_mm": hi - lo, "area_mm2": (hi - lo) * t, "mid": mid,
                "face_t": 2.0 * half}
    return None


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
        if pc["kind"] == "stick" and pc.get("a") is not None:     # a post on the floor: an end in a held box (#316)
            ends = np.vstack([np.asarray(pc["a"], float), np.asarray(pc["b"], float)])
            for h in held:
                lo, hi = np.asarray(h["lo"], float) - tol, np.asarray(h["hi"], float) + tol
                if np.any(np.all((ends >= lo) & (ends <= hi), axis=1)):
                    out.add(pc["key"])
                    break
            continue
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
    if spans and len(mids) >= 3 and all(sp[0] < MOST_OF_THE_WAY * sp[1] for sp in spans):
        return _rigid(mids, at)                  # posts under a top (#316): the rigid-top rule
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


class Shares(list):
    """A post group's shares, and which posts the top lifts off (``let_go``, their indices): said on their rows (#321)."""
    let_go: tuple = ()


def _rigid(mids: list[np.ndarray], at: np.ndarray) -> "Shares":
    """Each post's share of a load at ``at`` by the rigid-top rule (#316, Theo's C): the top stiff and the posts alike,
    so the shares lie on a plane over the posts, R_i/P = 1/N + b·x_i + c·y_i about their centroid, with b and c from
    the load's lever (Σx² b + Σxy c = e_x, Σxy b + Σy² c = e_y; with the cross term zero, R_i = P/N + Mx·y_i/Σy² +
    My·x_i/Σx²). Exact for three posts; for four or more, the stiff top's answer.

    A post only pushes: its fixings are in its end grain, which holds no pull (#301 decision 2, NDS 12.2.2.3). So a post
    the plane would lift is let go, and the rest share it again, until none is lifted (a stiff top on a ring of four
    posts, the load at 90 of 100 toward one: 0.9 on it, the far one let go, as #311 said statics needs). Posts in a
    line can't take a load off it: in a row; a load outside the posts that stay: it tips, not a joint's to hold. No
    fixing a post can declare holds it in a pull today (glue, screws and dowels all go into its end grain), so every post
    only pushes; a post held in a pull would need a fixing that isn't into end grain, and its capacity, first (#321)."""
    idx = list(range(len(mids)))
    while True:
        P = np.array([[float(mids[i][0]), float(mids[i][1])] for i in idx])
        c = P.mean(axis=0)
        d = P - c
        S = d.T @ d
        if len(idx) < 3 or abs(float(np.linalg.det(S))) < 1e-6 * max(1.0, float(np.trace(S))) ** 2:
            raise NotChain(IN_A_ROW if len(idx) == len(mids) else TIPS)
        b, cc = np.linalg.solve(S, np.asarray(at[:2], float) - c)
        got = [1.0 / len(idx) + float(b * x + cc * y) for x, y in d]
        lifted = min(range(len(idx)), key=lambda k: got[k])
        if got[lifted] >= -1e-9:
            out = Shares([0.0] * len(mids))
            for k, i in enumerate(idx):
                out[i] = max(0.0, got[k])
            out.let_go = tuple(i for i in range(len(mids)) if i not in idx)
            return out
        idx.pop(lifted)                            # the top lifts off it: let it go, the rest share again


#: A load outside the posts a stiff top still pushes on: it would tip about them, which no joint holds (#316).
TIPS = "it would tip on its posts, past the ones that hold it"


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


def _route(mine: list[dict], piece: str, f: np.ndarray, at: np.ndarray, share: str, pieces: Optional[dict] = None,
           lifted: Optional[set] = None) -> list:
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
        shares = _lever([mine[i]["mid"] for i in take], at, share,
                        [(float(mine[i]["length_mm"]), _across(pieces, piece, mine[i]["along"]),
                          mine[i]["along"]) for i in take] if pieces else None)
        if lifted is not None:                                # the posts the top lifts off, named (#321)
            lifted.update(tuple(mine[take[k]]["pieces"]) for k in getattr(shares, "let_go", ()))
        for i, frac in zip(take, shares):
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
            share: str = SHARE, arrivals: Optional[dict] = None, path: Optional[str] = None,
            lifted: Optional[set] = None) -> dict:
    """What each joint carries under one load: ``{(a, b): {"from": the piece pushing, "force": N (3,)}}``. The load,
    × its factor, from the piece it lands on to the pieces holding it up, down to what holds the part; a splayed side's
    foot thrust into the tie between the feet. Raises :class:`NotChain` where that path can't be followed."""
    ground = grounded(pieces, held, tol)
    start = loaded_piece(pieces, load)
    if start is None:
        raise NotChain(NOT_CHAIN)
    by = {pc["key"]: pc for pc in pieces}
    splayed = {k: s for k in ground if k in by for s in [_splay(by[k])] if s is not None}
    placed = [j for j in joints if "unplaced" not in j and j.get("short") is None]    # a short leg is no joint (#321)
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
        posts = [j for j in mine if j.get("post")]
        if posts and len(posts) < len(mine):        # a top on posts and on aprons too (#316): one path at a time
            mine = posts if path == "posts" else [j for j in mine if not j.get("post")]
        if not mine:
            raise NotChain(NOT_CHAIN)
        for j, fj in _route(mine, piece, f, at, share, by, lifted):
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
    if joint.get("post"):                         # into the post's end grain: lateral at NDS's Ceg (#316); no pull
        per_shear = SHEAR_FACE_LB * CEG_END
    glued = "glue" in joint["fix"]
    edge = joint["edge"]
    screws_said = f"{_count(n)} #8 screw{'s' if n != 1 else ''}"
    side = "end" if joint.get("post") else "edge"                 # a post bears on its end, its screws in its end grain
    return {"bearing": BEARING_PSI * area_in2 * LBF,
            "withdrawal": (n * WITHDRAW_EDGE_LB + (GLUE_EDGE_PSI * area_in2 if glued else 0.0)) * LBF,
            "shear": (n * per_shear + (GLUE_EDGE_PSI * area_in2 if glued else 0.0)) * LBF,
            "why": {"bearing": f"the {edge}'s {side} bearing on the {joint['face']}",
                    "withdrawal": f"{screws_said} pulled out of the {edge}'s {side}" if n
                    else f"nothing holding the {edge}'s {side} to the {joint['face']}",
                    "shear": f"{screws_said} in shear into the {edge}'s {side}" if n
                    else f"glue alone on the {edge}'s {side}"}}


#: What would take a failing joint past its need, said on its row and offered under Things to fix (#316, #344): only what
#: the check credits (a glue block isn't, nor a dado: the foreman), by the count that a ``JOINTS`` entry can declare.
FIX_IT = "{more} more #8 screw{s} at the {edge}'s {side}, {to} in all, would read {reads:g}×, past {need:g}"
def screwed(j: dict, n: int) -> dict:
    """Joint ``j`` held by ``n`` screws, as a ``JOINTS`` entry's ``"screws": n`` would make it (#344): laid where
    :func:`marks.spots` lays them, so what a moment puts on its farthest is the fresh check's. An apron's end or a post
    has no screw points there (its moment goes over half its length), so none here."""
    from . import marks

    out = {**j, "fix": sorted(set(j.get("fix") or []) | {"screws"}), "screws": int(n)}
    if j.get("apron") or j.get("post"):
        return out
    if j.get("along") is not None and j.get("mid") is not None and j.get("length_mm"):
        L, mid, along = float(j["length_mm"]), np.asarray(j["mid"], float), np.asarray(j["along"], float)
        out["points"] = [mid + along * (x - L / 2.0) for x in marks.spots(L, n)]
    return out


def fix_it(j: dict, need: float, safety_with: Callable[[int], Optional[float]], most: int = 60) -> Optional[dict]:
    """The fewest #8 screws that take joint ``j`` past ``need``, by ``safety_with(n)``: the joint's safety, every mode of
    it, held by ``n`` (what the fresh check will read once its ``JOINTS`` entry says ``"screws": n``). ``{"pieces", "edge",
    "side", "to", "more", "reads", "said", "entry"}``: laid evenly (:func:`marks.spots`), and said to crowd the edge
    where they come out that close (Theo's even spacing, #344). None where no count takes it past (it bears)."""
    from . import marks
    from . import verdicts as V

    n = int(j.get("screws") or 0) if "screws" in (j.get("fix") or []) else 0
    to = reads = None
    for k in range(n + 1, n + most + 1):
        s = safety_with(k)
        if s is not None and V.meets(s, need)["counts_as_pass"]:
            to, reads = k, s
            break
    if to is None:
        return None
    side = "end" if j.get("apron") or j.get("post") else "edge"
    close = marks.crowded(j["length_mm"], to) if j.get("length_mm") else None
    said = FIX_IT.format(more=to - n, s="" if to - n == 1 else "s", edge=j["edge"], side=side, to=to, reads=reads,
                         need=need) + (f" ({close})" if close else "")
    return {"pieces": list(j["pieces"]), "edge": j["edge"], "side": side, "to": to, "more": to - n, "reads": reads,
            "said": said, **({"crowded": close} if close else {}),
            "entry": {"pieces": list(j["pieces"]), "kind": j.get("kind") or "butt",       # what JOINTS says, to the letter
                      "fix": screwed(j, to)["fix"], "screws": to}}


def _by_hand(j: dict, demands: list, screw_mm: float) -> Callable[[int], Optional[float]]:
    """The hand rule's safety of joint ``j`` under each of ``demands`` (N by mode: the frame's load, a rake's thrust),
    held by ``n`` screws: the lowest."""
    from . import verdicts as V

    def at(n: int) -> Optional[float]:
        cap = capacity(screwed(j, n), screw_mm)
        by = [cap[m] / d[m] if cap[m] > 0 else 0.0 for d in demands for m in ("bearing", "withdrawal", "shear")
              if d.get(m, 0.0) > 1e-6]
        return V.cut(min(by)) if by else None
    return at


def _fixed(row: dict, j: dict, screw_mm: float, min_safety: float) -> None:
    """A failing row's fix-it, from every demand it answers to, or none (#344)."""
    row.pop("more_screws", None)
    row.pop("fix", None)
    if row.get("safety") is not None and row["safety"] < min_safety:        # producer
        more = fix_it(j, min_safety, _by_hand(j, row.get("demands_n") or [], screw_mm))
        if more:
            row.update({"more_screws": more, "fix": more["said"]})


def _count(n: int) -> str:
    return ["no", "one", "two", "three", "four", "five", "six"][n] if 0 <= n <= 6 else str(n)


def check(setup_: dict, load: dict, held: list[dict], min_safety: float, share: str = SHARE,
          mat: Optional[dict] = None) -> dict:
    """One load case's joints: ``{"rows": [...], "governing": the lowest row or None, "unchecked": [why, ...]}``. A row:
    ``{"pieces", "between": "the step and the left side", "mode", "safety", "need", "holds", "said": what gives first}``;
    ``safety`` is the joint's capacity over its share of the load × factor, against the run's ``min_safety`` as the wood's
    is (Theo: "the same safety factor that the rest of the stool is checked at")."""
    joints = setup_["joints"]
    odd = [j["unplaced"] for j in joints if j.get("mismatch")]
    if odd:                                       # a leg declared one way, built another: no number from either (#321)
        return {"rows": [], "governing": None, "unchecked": [odd[0]], "chain": False, "n": len(joints)}
    unchecked = [f"the joint between the {j['pieces'][0]} and the {j['pieces'][1]} ({j['unplaced']})"
                 for j in joints if "unplaced" in j]
    unchecked += [f"the joint between the {j['pieces'][0]} and the {j['pieces'][1]} (a {j['kind']})"
                  for j in joints if "unplaced" not in j and not j.get("notch") and j.get("kind") not in EDGE_KINDS]
    # one path, from the geometry (#321, the foreman's (b)): where the legs reach the top, the top rests on them and shares
    # by the rigid-top rule; only where they stop short does it rest on its aprons, then the legs
    posts = any(j.get("post") for j in joints if "unplaced" not in j)
    aprons = any(j.get("apron") for j in joints if "unplaced" not in j)
    pth = "posts" if posts else "frame" if aprons else None
    arrived: dict = {}
    lifted: set = set()                                       # the posts the top lifts off: said on their rows
    try:
        got = demands(joints, setup_["pieces"], load, held, setup_["tol"], share, arrivals=arrived, path=pth,
                      lifted=lifted)
    except NotChain as e:
        return {"rows": [], "governing": None, "unchecked": [e.why], "chain": False, "n": len(joints)}
    pushing = sum(1 for j in joints if j.get("post") and tuple(j["pieces"]) in got
                  and float(np.linalg.norm(got[tuple(j["pieces"])]["force"])) > 1e-9)
    said_path = PATH_SAID.get(pth)
    if pth == "posts" and pushing:                # four or more: the stiff top's answer; three: statics alone (#316)
        said_path += ", shared as a rigid top" if pushing >= 4 else f", by statics ({_count(pushing)} legs)"
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
        if j.get("short") is not None:                        # a leg short of the top: no joint, said (#321)
            rows.append({"pieces": j["pieces"], "between": f"the {j['pieces'][0]} and the {j['pieces'][1]}", "mode": None,
                         "safety": None, "holds": True, "said": j["said"]})
            continue
        if "unplaced" in j or j.get("kind") not in EDGE_KINDS:
            continue
        d = got.get(tuple(j["pieces"]))
        first = d["from"] if d else j["face"]                  # the piece that pushes, then the one that holds it
        between = f"the {first} and the {other(j, first)}"
        if d is None:
            rows.append({"pieces": j["pieces"], "between": between, "mode": None, "safety": None, "holds": True,
                         "said": LIFTED.format(n=_count(pushing)) if tuple(j["pieces"]) in lifted
                         else "carries none of this load"})
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
                     "demands_n": [{m: float(v) for m, v in parts.items()}],   # unrounded: the fix-it's (#344)
                     "capacity_lb": {m: round(cap[m] / LBF, 1) for m in by},
                     "said": cap["why"][mode] if mode else "carries none of this load", "assumed": j["assumed"],
                     **({"path": said_path} if said_path else {})})
        if j.get("crowded"):                              # credited, and said (Theo's even spacing, #344)
            rows[-1].update({"crowded": j["crowded"], "said": f"{rows[-1]['said']}; {j['crowded']}"})
        _fixed(rows[-1], j, setup_["screw_mm"], min_safety)   # what would take it past, on its row (#344)
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
    sideways = float(np.linalg.norm(np.asarray(load["force"], float)[:2])) > 1e-6 * (
        float(np.linalg.norm(load["force"])) or 1.0)
    for leg in dict.fromkeys(j["edge"] for j in joints if j.get("post") and "unplaced" not in j):
        f = arrived.get(leg)
        down = max(0.0, -float(f[2])) if f is not None else 0.0
        if leg in by and down > 1e-9:
            row = column_row(by[leg], down, min_safety)
            if row is None:
                unchecked.append(f"the {leg} as a column (its material's stiffness isn't known)")
                continue
            if sideways:                          # a post's column under a push: racking isn't checked (#317)
                row["said"] += f"; {COLUMN_RACKING}"
                unchecked.append(f"the {leg} as a column ({COLUMN_RACKING})")
            rows.append(row)
    rake_rows(joints, by, arrived, rows, unchecked, setup_["screw_mm"], min_safety)
    rated = [r for r in rows if r["safety"] is not None]
    gov = min(rated, key=lambda r: r["safety"]) if rated else None
    return {"rows": rows, "governing": gov, "unchecked": unchecked, "chain": True, "n": len(joints),
            **({"path": said_path} if said_path else {})}


#: A raked leg's top, tied by nothing the check can place: its thrust isn't checked, said (#316 slice 2).
RAKE_UNTIED = "the {leg} leans {deg:.0f}° and nothing ties its top"
#: A raked leg's tie that holds no pull (#316 slice 2, the foreman's guard).
RAKE_SAID = "the legs splay and the {tie} is all that ties them"


def _rake(stick: dict) -> Optional[tuple]:
    """A stick leaning off vertical by more than :data:`SPLAY_DEG`: ``(tan of its lean, degrees, the horizontal way its
    foot goes)``, or None."""
    a, b = np.asarray(stick["a"], float), np.asarray(stick["b"], float)
    top, foot = (a, b) if a[2] >= b[2] else (b, a)
    v = foot - top
    flat = np.array([v[0], v[1], 0.0])
    if abs(float(v[2])) < 1e-9 or float(np.linalg.norm(flat)) < 1e-9:
        return None
    deg = float(np.degrees(np.arctan2(float(np.linalg.norm(flat)), abs(float(v[2])))))
    if deg < SPLAY_DEG or deg > 45.0:
        return None
    return float(np.linalg.norm(flat) / abs(float(v[2]))), deg, flat / np.linalg.norm(flat)


def rake_rows(joints: list[dict], by: dict, arrived: dict, rows: list[dict], unchecked: list, screw_mm: float,
              min_safety: float) -> None:
    """A raked leg under a vertical load pushes its top outward, by statics: H = its down force × tan(its rake)
    (#316 slice 2, the foreman's guard). What ties its top (an apron's end on it) takes that as a pull, checked always,
    never waived as the bonded model's: ✗ where the tie holds no pull. Each tie's row says so, and keeps the pull
    (``rake_n``) the FEA's waiver stops at. A raked leg with nothing tying its top is named not checked."""
    from . import verdicts as V

    for leg, f in arrived.items():
        pc = by.get(leg)
        if pc is None or pc["kind"] != "stick":
            continue
        down = max(0.0, -float(np.asarray(f, float)[2]))
        lean = _rake(pc)
        if lean is None or down <= 1e-9:
            continue
        tan, deg, out = lean
        thrust = out * down * tan                         # what the leg's top puts out into whatever ties it
        ties = [j for j in joints if j.get("apron") and j.get("face") == leg and "unplaced" not in j]
        if not ties:
            unchecked.append(RAKE_UNTIED.format(leg=leg, deg=deg))
            continue
        for j in ties:
            parts = split(j, thrust, leg)
            if parts["withdrawal"] <= 1e-9 and parts["shear"] <= 1e-9:
                continue
            cap = capacity(j, screw_mm)
            ratio = {m: (cap[m] / parts[m] if cap[m] > 0 else 0.0) for m in ("withdrawal", "shear") if parts[m] > 1e-6}
            mode = min(ratio, key=ratio.get)
            safety = V.cut(ratio[mode])
            said = (RAKE_SAID.format(tie=j["edge"]) if cap["withdrawal"] <= 0 and parts["withdrawal"] > 1e-6
                    else cap["why"][mode])
            r = next((x for x in rows if tuple(x.get("pieces") or ()) == tuple(j["pieces"])), None)
            mine = {"pieces": j["pieces"], "between": f"the {leg} and the {j['edge']}", "edge": j["edge"], "face": leg,
                    "mode": mode, "safety": safety, "need": min_safety, "verdict": V.meets(safety, min_safety),
                    "holds": safety >= min_safety,  # producer
                    "demand_lb": {m: round(parts[m] / LBF, 1) for m in ratio},
                    "capacity_lb": {m: round(cap[m] / LBF, 1) for m in ratio},
                    "said": f"{said} (it leans {deg:.0f}°)", "assumed": j.get("assumed"),
                    "rake_n": round(parts["withdrawal"], 3)}
            thrust_n = {"bearing": 0.0, "withdrawal": float(parts["withdrawal"]), "shear": float(parts["shear"])}
            if r is None:
                rows.append(mine)
                r = mine
            elif r.get("safety") is None or safety < r["safety"]:
                r.update(mine)
            else:
                r["rake_n"] = mine["rake_n"]
            r["demands_n"] = list(r.get("demands_n") or []) + [thrust_n]   # its count passes both (#344)
            _fixed(r, j, screw_mm, min_safety)


#: Which way a top's load goes, from the geometry, said with why (#321, the foreman's (b)).
PATH_SAID = {"posts": "the legs reach the top: the top rests on them",
             "frame": "the legs stop short of the top: it rests on its aprons, then the legs"}
#: A post the top lifts off (#321): the load is inside the others, so nothing needs to pull on it.
LIFTED = "the top lifts off it: the load is inside the other {n} legs"
#: A post as a column, Euler's buckling load, P = pi^2 E I / (K L)^2: K = 1, both ends held in place and free to turn,
#: the aprons taken as stopping its top moving sideways (#316: interim, until racking is checked, #317).
POST_K = 1.0                              # interim (racking, #317)
#: A lumber post's crushing strength along its grain, MPa: the Wood Handbook (2021) Table 5-3a's weakest SPF species
#: clear at 12% (Engelmann spruce, 30.9 MPa), scaled for knots as Caliper's lumber MOR is (20 of its 64 MPa clear).
POST_CRUSH_MPA = 9.7                      # Theo, 2026-11-16 (#316, by the foreman)
#: A screw's lateral value in a main member's end grain: NDS 2018 §12.5.2.2, Ceg = 0.67 (a post's screws from the top).
CEG_END = 0.67
#: What a post's column row adds under a sideways case.
COLUMN_RACKING = "racking isn't checked (interim, #317)"


def column_row(post: dict, down_n: float, min_safety: float) -> Optional[dict]:
    """A post under ``down_n`` along it as a column (#316): Euler's buckling load at :data:`POST_K`, and its end grain's
    crushing at :data:`POST_CRUSH_MPA`; the lower governs. None where its material's stiffness isn't known."""
    from . import materials as M
    from . import verdicts as V

    mech = (M.STICKS.get(post.get("material") or "") or {}).get("mech")
    if not mech:
        return None
    a, b, ax, L = _stick_axis(post)
    thin = 2.0 * float(post["half"])
    area = float(post["volume"]) / L
    wide = area / thin
    inertia = wide * thin ** 3 / 12.0
    euler = math.pi ** 2 * float(mech["E"]) * inertia / (POST_K * L) ** 2
    crush = POST_CRUSH_MPA * area
    mode, cap, said = (("column", euler, f"the {post['key']} buckling as a column (Euler, K = {POST_K:g})")
                       if euler <= crush else
                       ("crushing", crush, f"the {post['key']} crushing along its grain ({POST_CRUSH_MPA:g} MPa)"))
    safety = V.cut(cap / down_n)
    return {"pieces": [post["key"]], "between": f"the {post['key']}, as a column", "mode": mode, "safety": safety,
            "need": min_safety, "verdict": V.meets(safety, min_safety), "holds": safety >= min_safety,  # producer
            "demand_lb": {mode: round(down_n / LBF, 1)}, "capacity_lb": {mode: round(cap / LBF, 1)}, "said": said,
            "assumed": False}


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
