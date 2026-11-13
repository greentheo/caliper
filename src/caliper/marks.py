"""CALI-177 (#222 slice C): what gets marked on each flat piece to make it, read from the part's own geometry.

The patterns, the cut list, the build book and the kids' book all read these, so they say the same thing:

- **Bevels.** Any sheet edge not cut square to its faces: where it meets another piece's face (a splayed side's top edge
  under the top), or where the solid's own edge face leans (its foot on the floor). The angle is the saw's bevel setting,
  0 for square; the line on the other face is where the blade comes out.
- **Mortises, notches, rabbets and dados.** A sheet run through another (a mortise, or a notch where it runs in from an
  edge), or set into it (a dado: the depth it reaches into the thickness), from :func:`joints._through`; and a declared
  rabbet or dado the solid doesn't show, at the default depth (half the thickness for a rabbet, a third for a dado).
- **Screws.** Along each joint line where an edge meets a face: 1 1/2 in from each end, then no more than 6 in apart,
  centred on the edge piece's thickness, driven through the face piece from its far side (a 3/16 in clearance hole,
  countersunk, and a 1/8 in pilot into the edge). A through tenon or notch is glued, not screwed; a joint said to be held
  without screws has none; a glue block is screwed into both pieces.
- **Glue blocks.** A 3/4 x 3/4 in strip along each joint said to be a glue block: a piece on the cut list, weighed and bought.

Every point is in the part's own frame (mm); the patterns turn them into each piece's flat frame.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .fasteners import PILOT_BIT, SCREW_EVERY_IN, WOOD

IN = 25.4
SCREW_END_IN = 1.5
CLEARANCE_BIT = "3/16 in"
#: Below this a cut edge is square: a builder's saw is set to 0.
BEVEL_MIN_DEG = 2.0
#: Beyond this an edge isn't a bevel a circular saw cuts (it tilts to 45°): a mitre or something else, not marked.
BEVEL_MAX_DEG = 50.0
GLUE_BLOCK = {"size": "1x1", "label": "a 3/4 x 3/4 in strip"}
#: The default depth of a declared rabbet or dado the solid doesn't show, as a share of the host's thickness (#222 §1).
DEPTH = {"rabbet": 0.5, "dado": 1.0 / 3.0}


def spots(mm: float) -> list[float]:
    """Where a joint's screws go along it, from one end (mm): 1 1/2 in from each end, then no more than 6 in apart; one in
    the middle of a joint too short for two."""
    end, every = SCREW_END_IN * IN, SCREW_EVERY_IN * IN
    if mm < 2 * end + 1e-6:
        return [mm / 2.0]
    n = math.ceil((mm - 2 * end) / every - 1e-9) + 1
    return [float(x) for x in np.linspace(end, mm - end, max(2, n))]


def count(mm: float) -> int:
    return len(spots(mm))


def comes_out(face_t: float, edge_t: float, sin: float, screw_mm: float) -> bool:
    """Whether a screw driven square through a face piece into another's edge comes out of that piece's face: past the
    face piece, it runs at an angle to the edge piece's plane (``sin`` of it), so it reaches a face after half the edge
    piece's thickness over that sine (#222 §4: the 1.6 x t rule checked at a bevel)."""
    if sin < 1e-3:
        return False                                   # square: it runs down the middle of the edge
    return screw_mm - face_t > (edge_t / 2.0) / sin


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def _sheet(pc: dict) -> bool:
    return pc["kind"] == "sheet" and len(pc.get("polys") or []) == 1 and bool(pc.get("sides"))


def _geom(pc: dict):
    """A sheet's declared face: origin, axes, the face normal pointing into its thickness (N), its thickness, and corners."""
    from .consistency import _frame

    poly = pc["polys"][0]
    o, u, v, n, flat = _frame(poly)
    return o, u, v, n * pc["sides"][0], float(pc["thickness"]), poly, flat


def _edges(pc: dict):
    """Each edge of a sheet's declared face: ``(index, p, q, along, out)``, ``out`` in its plane, away from its middle."""
    o, u, v, N, t, poly, flat = _geom(pc)
    centre = poly.mean(axis=0)
    for e in range(len(poly)):
        p, q = poly[e], poly[(e + 1) % len(poly)]
        L = float(np.linalg.norm(q - p))
        if L < 1e-6:
            continue
        d = (q - p) / L
        out = np.cross(d, N)
        out /= np.linalg.norm(out) or 1.0
        if float(out @ ((p + q) / 2 - centre)) < 0:
            out = -out
        yield e, p, q, d, out


def _faces(pc: dict):
    """A sheet's two faces as ``(point, outward normal)``."""
    o, u, v, N, t, poly, flat = _geom(pc)
    return [(o, -N), (o + N * t, N)]


def _edge_on(a: dict, b: dict, tol: float) -> Optional[dict]:
    """Where an edge of sheet ``a`` lies against a face of sheet ``b`` (the edge square to that face, within 45°): the
    stretch of it that touches, at ``a``'s mid-thickness. The longest such edge, or None."""
    from .consistency import slab_distance

    if not (_sheet(a) and _sheet(b)):
        return None
    _, _, _, N, t, _, _ = _geom(a)
    _, _, _, Nb, _, _, _ = _geom(b)
    best = None
    for e, p, q, d, out in _edges(a):
        if abs(float(out @ Nb)) < math.cos(math.radians(45.0)):
            continue                                   # b's face isn't across this edge: an edge to edge, not on a face
        L = float(np.linalg.norm(q - p))
        k = max(12, int(L / 3.0))
        f = (np.arange(k) + 0.5) / k
        mid = p + f[:, None] * (q - p) + N * t / 2.0
        touch = slab_distance(mid + out * 2.0 * tol, b["polys"][0], b["thickness"], b["sides"][0]) <= tol
        if not touch.any():
            continue
        s0, s1 = float(f[touch].min() * L - L / (2 * k)), float(f[touch].max() * L + L / (2 * k))
        s0, s1 = max(0.0, s0), min(L, s1)
        if best is None or s1 - s0 > best["length"]:
            best = {"edge": e, "a": p + d * s0 + N * t / 2.0, "b": p + d * s1 + N * t / 2.0, "along": d, "out": out,
                    "length": s1 - s0}
    return best


def _far_face(b: dict, toward) -> np.ndarray:
    """The outward normal of ``b``'s face away from a point: the face a screw is driven from."""
    (p0, n0), (p1, n1) = _faces(b)
    return n0 if float((p0 - toward) @ n0) > float((p1 - toward) @ n1) else n1


# ---------------------------------------------------------------------------
# Bevels
# ---------------------------------------------------------------------------
#: Where across the thickness an edge face is read: near each face and in the middle (#283 review).
DEPTHS = (0.15, 0.5, 0.85)


def _same_plane(n1, p1, n2, p2, deg: float = 1.0, mm: float = 0.5) -> bool:
    return float(np.clip(n1 @ n2, -1, 1)) >= math.cos(math.radians(deg)) and abs(float((p2 - p1) @ n1)) <= mm


def _edge_face(mesh, p, q, d, out, N, t: float, fs) -> Optional[dict]:
    """What a free edge's face is, from rays out through it at three points along it and three depths across the thickness:
    ``{"kind": "bevel", "normal", "at"}`` where every depth hits one plane (a saw cut across the whole thickness);
    ``{"kind": "chamfer", "chamfer": {...}}`` where the middle and one face's depth share a slanted plane and the other face's
    is square; None otherwise (square, a small chamfer or a round-over, a taper, or not read): nothing to mark."""
    starts = np.array([p + f_ * (q - p) + N * (w * t) - out * t for f_ in fs for w in DEPTHS])
    try:
        locs, ray, tri = mesh.ray.intersects_location(starts, np.repeat(out[None], len(starts), axis=0), multiple_hits=True)
    except Exception:  # noqa: BLE001 — no rays: the edge isn't read, never guessed
        return None
    pts, nor = [], []
    for r in range(len(starts)):                     # each ray's first way out of the piece, near where its edge is
        hit = sorted((float(np.linalg.norm(locs[i] - starts[r])), int(tri[i])) for i in np.flatnonzero(ray == r))
        hit = [h for h in hit if 0.5 * t <= h[0] <= 1.5 * t]
        if not hit:
            return None                              # buried in the solid, or past a hole: not read
        pts.append(starts[r] + out * hit[0][0])
        nor.append(np.asarray(mesh.face_normals[hit[0][1]], float))
    k = len(DEPTHS)
    P = [pts[i * k:(i + 1) * k] for i in range(len(fs))]
    Nn = [nor[i * k:(i + 1) * k] for i in range(len(fs))]
    if any(abs(float(n_ @ d)) > 0.2 for n_ in nor):
        return None                                  # it twists along the edge: not one saw setting
    mids = [Nn[i][1] for i in range(len(fs))]
    ang = [math.degrees(math.acos(float(np.clip(n_ @ out, -1, 1)))) for n_ in mids]
    if max(ang) - min(ang) > 1.0:
        return None                                  # it changes along the edge (a taper): not one setting
    if all(_same_plane(Nn[i][1], P[i][1], Nn[i][j], P[i][j]) for i in range(len(fs)) for j in (0, 2)):
        return {"kind": "bevel", "normal": mids[1], "at": P[1][1]}
    sides = set()                                    # square through the middle (a small chamfer, a round-over): no slanted plane
    for i in range(len(fs)):
        on = [j for j in (0, 2) if _same_plane(Nn[i][1], P[i][1], Nn[i][j], P[i][j])]
        sq = [j for j in (0, 2) if float(Nn[i][j] @ out) >= math.cos(math.radians(BEVEL_MIN_DEG))]
        if len(on) != 1 or sq != [2 - on[0]]:
            return None                              # not one slanted plane and a square face: leave it to the drawing
        sides.add(on[0])
    if len(sides) != 1:
        return None
    j = sides.pop()
    m, H = mids[1], P[1][1]
    ms, Hs = Nn[1][2 - j], P[1][2 - j]
    # where the chamfer's plane meets the square face's, across the thickness (w from the declared face)
    A, B = float((H - p) @ m) / float(out @ m), float(N @ m) / float(out @ m)
    A2, B2 = float((Hs - p) @ ms) / float(out @ ms), float(N @ ms) / float(out @ ms)
    if abs(B - B2) < 1e-9:
        return None
    w = (A - A2) / (B - B2)
    face = 1 if j == 2 else 0
    depth = (t - w) if face == 1 else w
    angle = math.degrees(math.acos(float(np.clip(m @ ms, -1, 1))))
    return {"kind": "chamfer", "chamfer": {"depth_mm": float(depth), "angle": round(angle, 1), "face": face}}


def bevels(pieces: list[dict], mesh, tol: float, chamfers: Optional[dict] = None) -> dict:
    """``{key: [{"edge", "angle", "length_mm", "meets", "lines": [(p, q) on the declared face, (p, q) on the other]}]}``:
    each sheet edge cut at an angle to its faces, from what it lies against or the solid's edge face, one plane across its
    thickness; a chamfer past the middle of the thickness goes into ``chamfers`` (#283 review), never a saw bevel."""
    from .consistency import slab_distance

    sheets = [pc for pc in pieces if _sheet(pc)]
    out: dict = {}
    chamfers = {} if chamfers is None else chamfers
    for a in sheets:
        o, u, v, N, t, poly, flat = _geom(a)
        for e, p, q, d, ed_out in _edges(a):
            L = float(np.linalg.norm(q - p))
            fs = np.array([0.25, 0.5, 0.75])
            mid = p + fs[:, None] * (q - p) + N * t / 2.0
            m, at, meets = None, None, None
            for b in sheets:                            # lying on another piece's face: cut to sit flat on it
                if b is a:
                    continue
                if (slab_distance(mid + ed_out * 2.0 * tol, b["polys"][0], b["thickness"], b["sides"][0]) <= tol).all():
                    Nb = _geom(b)[3]
                    if abs(float(Nb @ ed_out)) >= math.cos(math.radians(BEVEL_MAX_DEG)):
                        (p0, n0), (p1, n1) = _faces(b)
                        face = min(((p0, n0), (p1, n1)), key=lambda f: abs(float((mid[1] - f[0]) @ f[1])))
                        m = -face[1] if float(face[1] @ ed_out) < 0 else face[1]
                        at = mid[1] + ed_out * float((face[0] - mid[1]) @ face[1]) / float(ed_out @ face[1])
                        meets = b.get("key") or b["name"]
                        break
            if m is None and mesh is not None:          # its own edge face, in the solid: one plane across its thickness
                got = _edge_face(mesh, p, q, d, ed_out, N, t, fs)
                if got is None:
                    continue
                if got["kind"] == "chamfer":
                    chamfers.setdefault(a.get("key") or a["name"], []).append({**got["chamfer"], "edge": e, "length_mm": L})
                    continue
                m, at = got["normal"], got["at"]
                floor = float(mesh.bounds[0][2])
                meets = "the floor" if float(m[2]) < -0.95 and abs(float(at[2]) - floor) <= tol + t else None
            if m is None:
                continue
            cos = float(np.clip(m @ ed_out, -1.0, 1.0))
            angle = math.degrees(math.acos(cos))
            if not (BEVEL_MIN_DEG <= angle <= BEVEL_MAX_DEG):
                continue
            # the cut's plane through ``at`` with normal m: where it crosses each face, along ``out``
            s = [float((at - p - N * w) @ m) / float(ed_out @ m) for w in (0.0, t)]
            out.setdefault(a.get("key") or a["name"], []).append({
                "edge": e, "angle": round(angle, 1), "length_mm": L, "meets": meets,
                "lines": [(p + ed_out * s[0], q + ed_out * s[0]), (p + N * t + ed_out * s[1], q + N * t + ed_out * s[1])],
                "offsets": s})
    return out


# ---------------------------------------------------------------------------
# Mortises, notches, rabbets, dados
# ---------------------------------------------------------------------------
def _footprint(host: dict, piece: dict, got: dict) -> list:
    """The rectangle a crossing piece takes out of the host's face: its line through the host, as wide as the piece is
    thick across it. Four corners, on the host's declared face."""
    from .consistency import _frame

    o, u, v, n = got["frame"]
    pts = got["points"]
    c = pts.mean(axis=0)
    ax = np.linalg.svd(pts - c, full_matrices=False)[2][0] if len(pts) > 1 else np.array([1.0, 0.0])
    along = (pts - c) @ ax
    gaps = np.diff(np.unique(np.round(along, 3)))
    half = float(np.median(gaps[gaps > 1e-3])) / 2.0 if (gaps > 1e-3).any() else 0.0      # its samples' own spacing
    lo, hi = float(along.min()) - half, float(along.max()) + half
    e2 = np.array([-ax[1], ax[0]])
    pn = _frame(piece["polys"][0])[3]
    across = abs(float((e2[0] * u + e2[1] * v) @ pn)) or 1e-3
    w = float(piece["thickness"]) / across / 2.0
    mid_off = float(np.median((pts - c) @ e2))
    corners = [c + ax * a_ + e2 * (mid_off + b_) for a_, b_ in ((lo, -w), (hi, -w), (hi, w), (lo, w))]
    return [o + x * u + y * v for x, y in corners]


def cuts(pieces: list[dict], tol: float, said: Optional[list] = None) -> dict:
    """``{host key: [{"kind": "mortise" | "notch" | "dado" | "rabbet", "for": piece name, "corners": 4 points,
    "depth_mm": None for one right through, "face": 0 (the declared face) or 1, "declared": bool}]}``."""
    from . import joints as J
    from .consistency import _inside2d

    sheets = [pc for pc in pieces if _sheet(pc) and pc.get("material") in WOOD]
    out: dict = {}
    seen = set()
    for host in sheets:
        o, u, v, N, t, poly, flat = _geom(host)
        holes = [np.stack([(np.asarray(h, float) - o) @ u, (np.asarray(h, float) - o) @ v], axis=1)
                 for h in host.get("holes") or []]
        for piece in sheets:
            if piece is host:
                continue
            got = J._through(host, piece, tol)
            if got is None:
                continue
            covered = np.zeros(len(got["points"]), dtype=bool)
            for h in holes:
                covered |= _inside2d(got["points"], h)
            if covered.mean() >= 0.9:
                continue                                # its outline already has the hole: on the pattern as one
            if got["through"]:
                kind, depth, face = ("notch" if got["notch"] else "mortise"), None, 0
            else:
                lo, hi = got["span"]
                w = (piece["polys"][0] - o) @ N              # its own corners say where its end is: the samples fall short
                lo = float(w.min()) if -tol < float(w.min()) <= lo else lo
                hi = float(w.max()) if hi <= float(w.max()) < t + tol else hi
                face = 0 if lo <= tol else 1
                depth = max(0.0, hi) if face == 0 else max(0.0, t - lo)
                kind = "dado"                           # set into its face (a rabbet, at its edge, reads as an edge on a face)
            out.setdefault(host.get("key") or host["name"], []).append(
                {"kind": kind, "for": piece["name"], "corners": _footprint(host, piece, got), "depth_mm": depth,
                 "face": face, "declared": False})
            seen.add(tuple(sorted((host.get("key") or host["name"], piece.get("key") or piece["name"]))))
    by = {pc.get("key") or pc["name"]: pc for pc in sheets}
    for j in said or []:                                 # a rabbet or dado said, that the solid doesn't show
        kind = j.get("kind")
        two = tuple(sorted(p for p in j.get("pieces") or [] if isinstance(p, str)))
        if kind not in DEPTH or len(two) != 2 or two in seen or not all(k in by for k in two):
            continue
        a, b = by[two[0]], by[two[1]]
        g, host, edge = _edge_on(a, b, tol), b, a
        g2 = _edge_on(b, a, tol)
        if g is None or (g2 is not None and g2["length"] > g["length"]):
            g, host, edge = g2, a, b
        if g is None:
            continue
        ht = float(host["thickness"])
        depth = float(j["depth"]) if isinstance(j.get("depth"), (int, float)) and j["depth"] > 0 else DEPTH[kind] * ht
        (p0, n0), (p1, n1) = _faces(host)
        face = 0 if abs(float((g["a"] - p0) @ n0)) < abs(float((g["a"] - p1) @ n1)) else 1
        w = float(edge["thickness"]) / 2.0
        hn = _geom(host)[3]
        side = np.cross(g["along"], hn)
        side /= np.linalg.norm(side) or 1.0
        on = [x - hn * float((x - _geom(host)[0]) @ hn) for x in (g["a"], g["b"])]      # onto the host's declared face
        corners = [on[0] - side * w, on[1] - side * w, on[1] + side * w, on[0] + side * w]
        out.setdefault(host.get("key") or host["name"], []).append(
            {"kind": kind, "for": edge["name"], "corners": corners, "depth_mm": depth, "face": face, "declared": True})
    return out


# ---------------------------------------------------------------------------
# Screws and glue blocks
# ---------------------------------------------------------------------------
def _said_by_pair(said: Optional[list]) -> dict:
    return {tuple(sorted(p for p in j.get("pieces") or [] if isinstance(p, str))): j for j in said or []
            if len([p for p in j.get("pieces") or [] if isinstance(p, str)]) == 2}


def screws(pieces: list[dict], tol: float, said: Optional[list] = None) -> dict:
    """``{(a, b): {"n", "on": the face piece's key or None, "into": the edge piece's key or None, "points": [3D],
    "drive": the outward normal of the face they go in from, "why": why there are none}}`` for every joint
    :func:`joints.contacts` finds, keyed as it keys them: one count for the patterns, the cut list, the book, the
    shopping list and the kids' book."""
    from . import fasteners
    from . import joints as J

    fasteners.keys(pieces)
    found = J.contacts(pieces, tol)
    by = {pc["key"]: pc for pc in pieces}
    told = _said_by_pair(said)
    screw_mm = fasteners.screw_length_mm(pieces)
    out = {}
    for key, c in found.items():
        j = told.get(key)
        a, b = by[key[0]], by[key[1]]
        if j is not None and "screws" not in (j.get("fix") or []):
            out[key] = {"n": 0, "on": None, "into": None, "points": [], "why": "held without screws, as said"}
            continue
        if j is not None and j.get("kind") == "glue block":
            out[key] = {"n": 2 * count(c["length_mm"]), "on": None, "into": None, "points": [],
                        "why": "through the glue block into each piece"}
            continue
        if c["how"] in ("through", "notch"):
            host, piece = (a, b) if _sheet(a) and _sheet(b) and J._through(a, b, tol) is not None else (b, a)
            out[key] = {"n": 0, "on": None, "into": None, "points": [], "host": host["key"], "piece": piece["key"],
                        "why": f"glued in its {'notch' if c['how'] == 'notch' else 'mortise'}"}
            continue
        g, face, edge = None, None, None
        if c["how"] in ("edge", "into"):
            ga, gb = _edge_on(a, b, tol), _edge_on(b, a, tol)
            g, face, edge = (ga, b, a) if ga is not None and (gb is None or ga["length"] >= gb["length"]) else (gb, a, b)
            if c["how"] == "into":
                for host, piece in ((a, b), (b, a)):
                    got = J._through(host, piece, tol) if _sheet(host) and _sheet(piece) else None
                    if got is not None:
                        o, u, v, n = got["frame"]
                        pts = got["points"]
                        cc = pts.mean(axis=0)
                        ax = np.linalg.svd(pts - cc, full_matrices=False)[2][0]
                        al = (pts - cc) @ ax
                        a2, b2 = cc + ax * float(al.min()), cc + ax * float(al.max())
                        p3, q3 = o + a2[0] * u + a2[1] * v, o + b2[0] * u + b2[1] * v
                        L = float(np.linalg.norm(q3 - p3))
                        g = {"a": p3, "b": q3, "along": (q3 - p3) / (L or 1.0), "length": L}
                        face, edge = host, piece
                        break
        if g is None or g["length"] < 1e-6:
            out[key] = {"n": count(c["length_mm"]), "on": None, "into": None, "points": [], "why": ""}
            continue
        pts = [g["a"] + g["along"] * s for s in spots(g["length"])]
        centre = _geom(edge)[5].mean(axis=0) if _sheet(edge) else np.mean(pts, axis=0)
        out_ = False
        if _sheet(face) and _sheet(edge):
            sin = abs(float(_geom(face)[3] @ _geom(edge)[3]))
            out_ = comes_out(float(face["thickness"]), float(edge["thickness"]), sin, screw_mm)
        out[key] = {"n": len(pts), "on": face["key"], "into": edge["key"], "points": pts,
                    "drive": _far_face(face, centre), "why": "", "comes_out": out_}
    return out


def glue_blocks(pieces: list[dict], tol: float, said: Optional[list] = None) -> list[dict]:
    """Each joint said to be a glue block, as a piece to cut: ``{"name", "pieces", "a", "b", "length_mm"}``, ``a`` and
    ``b`` along the inside corner."""
    from . import fasteners
    from . import joints as J

    fasteners.keys(pieces)
    found = J.contacts(pieces, tol)
    by = {pc["key"]: pc for pc in pieces}
    out = []
    for key, j in sorted(_said_by_pair(said).items()):
        if j.get("kind") != "glue block" or key not in found:
            continue
        a, b = by[key[0]], by[key[1]]
        ga, gb = _edge_on(a, b, tol), _edge_on(b, a, tol)
        g, face, edge = (ga, b, a) if ga is not None and (gb is None or ga["length"] >= gb["length"]) else (gb, a, b)
        if g is None:
            continue
        # into the corner: off the edge piece's face, on the face piece's
        side = 0.75 * IN / 2.0 + float(edge["thickness"]) / 2.0
        Nf = _far_face(face, g["a"])
        x = -Nf * 0.75 * IN / 2.0
        y = np.cross(g["along"], Nf)
        y /= np.linalg.norm(y) or 1.0
        pa, pb = g["a"] + x + y * side, g["b"] + x + y * side
        out.append({"name": f"glue block: {key[0]} / {key[1]}", "pieces": list(key), "a": pa, "b": pb,
                    "length_mm": float(g["length"])})
    return out


def glue_block_items(blocks: list[dict]) -> list[dict]:
    """The glue blocks as construction items, for the takeoff (weight, the stick cut list and the shopping list)."""
    return [{"name": g["name"], "kind": "stick", "material": "lumber", "size": GLUE_BLOCK["size"],
             "a": tuple(float(x) for x in g["a"]), "b": tuple(float(x) for x in g["b"])} for g in blocks]


def glue_block_items_of(store, pid: str, declared: Optional[dict] = None) -> list[dict]:
    """A part's glue blocks as items to weigh, buy and cut; [] where none is said (without building anything)."""
    from . import construction as C
    from . import joints as J
    from .consistency import _sides, shapes, tolerance

    said = J.read(store.read_script(pid))
    if not any(j.get("kind") == "glue block" for j in said):
        return []
    try:
        mesh = store.part_geometry(pid).require_mesh()
        pieces = shapes(declared if declared is not None else C.declared(store, pid))
    except Exception:  # noqa: BLE001 — no pieces: no blocks between them
        return []
    _sides(mesh, pieces)
    return glue_block_items(glue_blocks([pc for pc in pieces if pc.get("material") in WOOD], tolerance(mesh), said))


# ---------------------------------------------------------------------------
# A part's marks
# ---------------------------------------------------------------------------
def of(store, pid: str) -> dict:
    """A part's marks: ``{"bevels", "cuts", "screws", "glue_blocks", "pieces"}``, ``pieces`` its pieces with their keys (so
    a reader can match a pattern's outline to its piece). Empty where it has no pieces."""
    from . import construction as C
    from . import fasteners
    from . import joints as J
    from .consistency import _sides, shapes, tolerance

    empty = {"bevels": {}, "chamfers": {}, "cuts": {}, "screws": {}, "glue_blocks": [], "pieces": []}
    try:
        mesh = store.part_geometry(pid).require_mesh()
        pieces = shapes(C.declared(store, pid))
    except Exception:  # noqa: BLE001 — nothing to mark
        return empty
    _sides(mesh, pieces)
    fasteners.keys(pieces)
    tol = tolerance(mesh)
    said = J.read(store.read_script(pid))
    wood = [pc for pc in pieces if pc.get("material") in WOOD]
    chamfers: dict = {}
    return {"bevels": bevels(pieces, mesh, tol, chamfers), "chamfers": chamfers, "cuts": cuts(pieces, tol, said),
            "screws": screws(wood, tol, said),
            "glue_blocks": glue_blocks(wood, tol, said), "pieces": pieces}


def key_of(m: dict, outline) -> Optional[str]:
    """Which piece a pattern's sheet is, by its outline."""
    poly = np.asarray(outline, float)
    for pc in m.get("pieces") or []:
        if pc["kind"] == "sheet" and len(pc["polys"]) == 1 and pc["polys"][0].shape == poly.shape \
                and np.allclose(pc["polys"][0], poly, atol=1e-6):
            return pc["key"]
    return None


def on_piece(m: dict, key: str) -> dict:
    """What's marked on one piece: ``{"bevels", "cuts", "screws": [{"points", "into", "drive"}], "n_screws"}``."""
    s = [dict(c, pair=k) for k, c in sorted((m.get("screws") or {}).items()) if c.get("on") == key and c["n"]]
    return {"bevels": (m.get("bevels") or {}).get(key, []), "chamfers": (m.get("chamfers") or {}).get(key, []),
            "cuts": (m.get("cuts") or {}).get(key, []), "screws": s,
            "n_screws": sum(c["n"] for c in s)}


# ---------------------------------------------------------------------------
# Said
# ---------------------------------------------------------------------------
def _in(mm: float) -> str:
    from .release import inches

    return inches(mm)


def screw_line(n: int, into: list[str]) -> str:
    """The holes, said once a piece: what to drill at each mark."""
    behind = " and the ".join(dict.fromkeys(into)) if into else "the piece behind"
    return (f"{n} screw{'s' if n != 1 else ''}, marked +: drill a {CLEARANCE_BIT} clearance hole through at each and "
            f"countersink it; then hold it in place and drill a {PILOT_BIT} pilot into the {behind}.")


def bevel_line(angles: list[float]) -> str:
    """The bevels on one piece: one saw setting each, the face that goes up."""
    by: dict = {}
    for a in angles:
        by[round(a)] = by.get(round(a), 0) + 1
    parts = [f"saw at {a:g}°, this face up, along the {n} edge{'s' if n != 1 else ''} marked B" for a, n in sorted(by.items())]
    return "Bevels: " + "; ".join(parts) + ". The dashed line is where the blade comes out on the other face."


def chamfer_size(mm: float) -> str:
    """A chamfer's size across the edge, millimetres first (a router bit's or a plane's), inches after."""
    return f"{mm:.0f} mm ({_in(mm)})"


def chamfer_line(chamfers: list) -> str:
    """The chamfers on one piece: shaped after cutting, never a saw setting (#283 review)."""
    parts = [f"{chamfer_size(c['depth_mm'])} along the edge marked C, on {'this face' if c.get('shown', True) else 'the other face'}"
             for c in chamfers]
    return "Chamfer: " + "; ".join(parts) + ". A router or a block plane, after it's cut out: not the saw."


def cut_line(k: int, c: dict, lo, size) -> str:
    """A mortise, notch, rabbet or dado on a piece's page: where and how big, from the piece's square edges."""
    w, h = size
    where = f"{_in(lo[0])} from the left and {_in(lo[1])} up"
    if c["kind"] in ("mortise", "notch"):
        tag = "M" if c["kind"] == "mortise" else "N"
        how = "right through" if c["kind"] == "mortise" else "right through, in from the edge"
        return (f"{tag}{k}: a {c['kind']} for the {c['for']}: cut {_in(w)} x {_in(h)}, {where}, {how}. Size it to your "
                f"ply's measured thickness (3/4 in plywood is often 23/32 in) and test the fit on scrap.")
    face = "this face" if c.get("shown", True) else "the other face"
    return (f"D{k}: a {c['kind']} for the {c['for']}, {_in(c['depth_mm'])} deep, on {face}: the dashed lines, {_in(w)} x "
            f"{_in(h)}, {where}. Make it as wide as the {c['for']} actually is: measure it, and test on scrap.")


def summary(m: dict) -> dict:
    """Counts for the cut list and the book: ``{"bevels": [(piece, angle, mm)], "cuts": [(piece, kind, for)], "screws",
    "glued": [pair], "glue_blocks"}``."""
    bev = [(k, b["angle"], b["length_mm"]) for k, bs in sorted((m.get("bevels") or {}).items()) for b in bs]
    cham = [(k, c["depth_mm"], c["angle"], c["length_mm"]) for k, cs in sorted((m.get("chamfers") or {}).items()) for c in cs]
    cut = [(k, c["kind"], c["for"], c.get("depth_mm")) for k, cs in sorted((m.get("cuts") or {}).items()) for c in cs]
    sc = m.get("screws") or {}
    return {"bevels": bev, "chamfers": cham, "cuts": cut, "screws": sum(c["n"] for c in sc.values()),
            "on": {k: on_piece(m, k)["n_screws"] for k in {c["on"] for c in sc.values() if c.get("on") and c["n"]}},
            "elsewhere": sum(c["n"] for c in sc.values() if not c.get("on")),
            "glued": [k for k, c in sorted(sc.items()) if not c["n"]],
            "glue_blocks": [(g["name"], g["length_mm"]) for g in m.get("glue_blocks") or []]}


def cutlist_lines(m: dict) -> list[str]:
    """The cut list's marks for one part, inches first."""
    s = summary(m)
    lines = []
    for k, a, mm in s["bevels"]:
        lines.append(f"    {k}: bevel {a:.0f}° along {_in(mm)} of edge")
    for k, depth, a, mm in s["chamfers"]:
        lines.append(f"    {k}: chamfer {chamfer_size(depth)} at {a:.0f}° along {_in(mm)} of edge")
    for k, kind, what, depth in s["cuts"]:
        lines.append(f"    {k}: a {kind} for the {what}" + (f", {_in(depth)} deep" if depth else ", right through"))
    for k, n in sorted(s["on"].items()):
        lines.append(f"    {k}: {n} screw hole{'s' if n != 1 else ''} marked ({CLEARANCE_BIT} clearance, countersunk; "
                     f"{PILOT_BIT} pilot)")
    if s["elsewhere"]:
        lines.append(f"    {s['elsewhere']} more screws where sticks meet, not marked on a pattern")
    for name, mm in s["glue_blocks"]:
        lines.append(f"    {name}: {GLUE_BLOCK['label']}, {_in(mm)}")
    return (["  marks (on the hand patterns):"] + lines) if lines else []


def book_lines(m: dict, names: Optional[list] = None) -> list[str]:
    """The build book's step for a part's panels: the bevels to set the saw for, the mortises and dados to cut, the holes to
    drill and the glue blocks to fit, from the same marks as the patterns."""
    s = summary(m)
    keep = (lambda k: True) if names is None else (lambda k: k.split(" #")[0] in names)
    out = []
    by: dict = {}
    for k, a, _ in s["bevels"]:
        if keep(k):
            by.setdefault(round(a), []).append(k)
    for a, ks in sorted(by.items()):
        out.append(f"Set the saw to {a:g}° for the {len(ks)} edge{'s' if len(ks) != 1 else ''} marked B on the "
                   f"{' and the '.join(dict.fromkeys(ks))}: each pattern says which face goes up.")
    ch: dict = {}
    for k, depth, _, _ in s["chamfers"]:
        if keep(k):
            ch.setdefault(chamfer_size(depth), []).append(k)
    for size, ks in sorted(ch.items()):
        out.append(f"Chamfer the {len(ks)} edge{'s' if len(ks) != 1 else ''} marked C on the "
                   f"{' and the '.join(dict.fromkeys(ks))}, {size}, with a router or a block plane: not the saw.")
    kinds: dict = {}
    for k, kind, what, depth in s["cuts"]:
        if keep(k):
            kinds.setdefault(kind, []).append((k, what, depth))
    for kind in ("mortise", "notch"):
        if kinds.get(kind):
            hosts = " and the ".join(dict.fromkeys(k for k, _, _ in kinds[kind]))
            n = len(kinds[kind])
            out.append(f"Cut the {n} {kind}{'s' if n != 1 else ''} marked on the {hosts} before cutting out the "
                       f"outline{'s' if len(set(k for k, _, _ in kinds[kind])) != 1 else ''}: size each one to your "
                       f"ply's measured thickness, and test the fit on scrap.")
    for kind in ("dado", "rabbet"):
        for k, what, depth in kinds.get(kind, []):
            out.append(f"Cut the {kind} in the {k} for the {what}, {_in(depth)} deep, as wide as the {what} actually "
                       f"is: measure it and test on scrap.")
    on = sum(n for k, n in s["on"].items() if keep(k))
    if on:
        out.append(f"Drill the {on} screw holes marked + on the patterns: a {CLEARANCE_BIT} clearance hole through, "
                   f"countersunk, from the face marked. Then glue each joint, hold it, drill a {PILOT_BIT} pilot into the "
                   f"piece behind through each hole, and drive the screw.")
    for k, c in sorted((m.get("screws") or {}).items()):
        if c.get("comes_out") and keep(c["on"]):
            out.append(f"Where the {c['on']} meets the {c['into']}, the screws would come out of the {c['into']}'s face "
                       f"at its angle: use shorter ones there, or angle them in.")
    glued = [k for k in s["glued"] if names is None or any(keep(x) for x in k)]
    sc = m.get("screws") or {}
    for k in glued:
        why = sc[k].get("why") or ""
        if why.startswith("glued in its"):
            out.append(f"Glue the {sc[k]['piece']} into its {why.split()[-1]} in the {sc[k]['host']}: no screws.")
    for name, mm in s["glue_blocks"]:
        out.append(f"Glue the {name.split(': ', 1)[-1].replace(' / ', ' and ')} glue block ({GLUE_BLOCK['label']}, "
                   f"{_in(mm)}) into the inside corner, and screw through it into each piece.")
    return out
