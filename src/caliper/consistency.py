"""CALI-54 — what a part says it's built from must be the part that was built.

A part's shape comes from ``build()``; its weight, bill of materials and cut plan come from what it
declares (``construction()``, ``members()``; see ``part_scripts.md``). Nothing ties the two together but
the author's care, and when the designer writes both in one go, a panel left at the origin or a sheet
listed at twice its thickness passes every measurement of the shape and quietly ruins the cut plan. So
every build is checked against its declarations, as measurements that fail a round like any other:

- ``construction_reads``: the declarations run, and name pieces Caliper knows how to weigh.
- ``construction_inside``: every piece lies in the solid (a sheet's face on its surface or inside it, with
  the panel's thickness inside; a stick's centreline inside it). Nothing invented, nothing misplaced.
- ``construction_covers``: the pieces cover the solid's surface. Nothing in the shape is left out of
  the bill of materials, and no panel in the shape is thicker than the sheet it's listed as.
- ``construction_volume``: no more material than the solid holds (a wrong thickness, a piece twice).
- ``loads_land``: every load in ``loads()`` says how much and where, and where is on the part, by the strength
  check's own rule (CALI-84); every box in ``held()`` too.

A part that declares nothing gets none of these: there is nothing to disagree with.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import construction as C
from . import materials as M
from .evaluate import AssertionResult

#: Share of a piece's sample points that must sit in the solid, and of the solid's surface that must be
#: on some piece. Not 1.0: tessellation and a builder's rounding put a few points just outside.
INSIDE_MIN = 0.9
COVER_MIN = 0.98
#: The pieces may come to this much more than the solid's volume (joints counted twice, rounded corners).
#: The pieces' volume against the solid's: much less and build() is filled in (CALI-83), much more and a
#: piece is too thick or listed twice.
VOLUME_MIN = 0.67
VOLUME_MAX = 1.25
#: Share of the solid that may lie in no piece at all before build() reads as filled in (CALI-87): a ratio of
#: volumes misses a small filled box, whose panels are most of it; the solid outside every panel doesn't.
SOLID_IN_NO_PIECE = 0.1
SURFACE_SAMPLES = 1500
GRID = 10


def tolerance(mesh) -> float:
    """How far off a point may be and still count as on the surface: tessellation, and a builder's
    rounding to the nearest sixteenth on a big part."""
    return max(2.0, 0.005 * float(np.linalg.norm(mesh.extents)))


# ---------------------------------------------------------------------------
# Pieces as geometry
# ---------------------------------------------------------------------------
def _frame(poly: np.ndarray):
    """A flat polygon's plane: origin, in-plane axes u and v, normal, and its corners in (u, v)."""
    _, _, n = C.polygon(poly.tolist())
    n = np.asarray(n, float)
    o = poly[0]
    edges = np.roll(poly, -1, axis=0) - poly
    lengths = np.linalg.norm(edges, axis=1)
    u = edges[int(np.argmax(lengths > 1e-6))]
    u = u / (np.linalg.norm(u) or 1.0)
    v = np.cross(n, u)
    rel = poly - o
    return o, u, v, n, np.stack([rel @ u, rel @ v], axis=1)


def _inside2d(q: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Even-odd point-in-polygon for many points at once (convex or not)."""
    x, y = q[:, :1], q[:, 1:]
    x0, y0 = poly[None, :, 0], poly[None, :, 1]
    x1, y1 = np.roll(poly[:, 0], -1)[None, :], np.roll(poly[:, 1], -1)[None, :]
    dy = np.where(y1 == y0, 1e-12, y1 - y0)
    crosses = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / dy + x0)
    return crosses.sum(axis=1) % 2 == 1


def _edge_dist2d(q: np.ndarray, poly: np.ndarray) -> np.ndarray:
    a = poly[None, :, :]
    ab = np.roll(poly, -1, axis=0)[None, :, :] - a
    aq = q[:, None, :] - a
    t = np.clip((aq * ab).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-12), 0.0, 1.0)
    return np.linalg.norm(aq - t[..., None] * ab, axis=-1).min(axis=1)


def slab_distance(points: np.ndarray, poly, thickness: float = 0.0, side: float = 1.0) -> np.ndarray:
    """Distance from each point to a panel: a flat polygon (one face) with ``thickness`` behind it on
    ``side`` of its normal (+1 or -1). With no thickness, the distance to the polygon itself."""
    o, u, v, n, flat = _frame(np.asarray(poly, float))
    rel = points - o
    q = np.stack([rel @ u, rel @ v], axis=1)
    off = (rel @ n) * side
    across = np.where(_inside2d(q, flat), 0.0, _edge_dist2d(q, flat))
    through = np.maximum(-off, off - thickness).clip(min=0.0)
    return np.hypot(across, through)


def segment_distance(points: np.ndarray, a, b) -> np.ndarray:
    a, b = np.asarray(a, float), np.asarray(b, float)
    ab = b - a
    t = np.clip(((points - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    return np.linalg.norm(points - (a + t[:, None] * ab), axis=1)


def polygon_samples(poly, n: int = GRID, holes=()) -> np.ndarray:
    """Points spread over a flat polygon's face: a grid in its plane, kept where it's inside (and not in
    one of its ``holes``, polygons on the same face)."""
    o, u, v, _, flat = _frame(np.asarray(poly, float))
    lo, hi = flat.min(axis=0), flat.max(axis=0)
    g = (np.arange(n) + 0.5) / n
    grid = np.stack(np.meshgrid(lo[0] + g * (hi[0] - lo[0]), lo[1] + g * (hi[1] - lo[1])), -1).reshape(-1, 2)
    inside = _inside2d(grid, flat)
    for h in holes:
        rel = np.asarray(h, float) - o
        inside &= ~_inside2d(grid, np.stack([rel @ u, rel @ v], axis=1))
    keep = grid[inside]
    if not len(keep):
        keep = flat
    return o + keep[:, :1] * u + keep[:, 1:] * v


def _section(item: dict) -> tuple[float, float, float]:
    """A stick's or tube's half-width (to its nearest face), half-diagonal and cross-section area."""
    if "size" in item:
        _, (s1, s2) = M.stick(item.get("material", "lumber"), item["size"])
        return min(s1, s2) / 2, math.hypot(s1, s2) / 2, s1 * s2
    o, w = float(item["outer"]), float(item["wall"])
    return o / 2, o * math.sqrt(2) / 2, C.tube_area(o, w)


def shapes(declared: dict) -> list[dict]:
    """Every declared piece that takes up room, as geometry: sheets as their faces, sticks and tubes as
    centrelines. Lumps and coverings weigh but don't occupy the solid. Raises ValueError for a piece
    Caliper can't weigh (an unknown material, a sheet with no outline)."""
    out = []
    items = [dict(m, kind="stick", material="steel") for m in declared.get("members") or []]
    for item in list(declared.get("construction") or []) + items:
        C.piece(item)                                   # the BOM's own validation: unknown material, no outline
        name = item.get("name") or item.get("kind")
        if item.get("kind") == "sheet":
            polys = [item["outline"]] if item.get("outline") else list(item["facets"])
            t = float(item["thickness"])
            holes = [np.asarray(h, float) for h in item.get("holes") or []] if item.get("outline") else []
            out.append({"name": name, "kind": "sheet", "polys": [np.asarray(p, float) for p in polys],
                        "thickness": t, "holes": holes, "material": item.get("material"),
                        # the designer's own grain is only assumed: advice, never the verdict's (CALI-126)
                        "grain_assumed": item.get("grain") if item.get("grain") in ("along", "across") else None,
                        "pictures": [np.asarray(h, float) for h in item.get("pictures") or []],
                        "volume": (sum(C.polygon(p)[0] for p in polys)
                                   - sum(C.polygon(h.tolist())[0] for h in holes)) * t})
        elif item.get("kind") == "stick":
            half, diag, area = _section(item)
            a, b = (np.asarray(item[k], float) for k in ("a", "b"))
            out.append({"name": name, "kind": "stick", "a": a, "b": b, "half": half, "reach": diag,
                        "volume": float(np.linalg.norm(b - a)) * area, "material": item.get("material", "lumber")})
    return out


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------
def _signed(mesh, points: np.ndarray) -> np.ndarray:
    """Signed distance to the solid's surface: positive inside."""
    from . import spatial

    return spatial.signed_distance(mesh, points)


def _xyz(p) -> str:
    return "(" + ", ".join(f"{v:.0f}" for v in p) + ")"


def _sides(mesh, pieces: list[dict]) -> None:
    """Which way each sheet's thickness goes from the face its outline gives: into the solid. The side
    whose mid-thickness has more of the panel inside wins (each polygon of a bent panel on its own)."""
    for pc in pieces:
        if pc["kind"] != "sheet":
            continue
        pc["sides"], pc["mids"] = [], []
        for poly in pc["polys"]:
            pts = polygon_samples(poly, holes=pc.get("holes") if len(pc["polys"]) == 1 else ())
            n = np.asarray(C.polygon(poly.tolist())[2], float)
            best = None
            for side in (1.0, -1.0):
                mid = pts + side * n * pc["thickness"] / 2
                d = _signed(mesh, mid)
                score = (float((d >= 0).mean()), float(np.median(d)))
                if best is None or score > best[0]:
                    best = (score, side, mid)
            pc["sides"].append(best[1])
            pc["mids"].append(best[2])


def _inside(mesh, pieces: list[dict], tol: float) -> AssertionResult:
    bad = []
    for pc in pieces:
        if pc["kind"] == "sheet":
            pts = np.concatenate(pc["mids"])                 # the panel's middle, on the side it's built
            allow = tol
        else:
            pts = pc["a"] + np.linspace(0.15, 0.85, 8)[:, None] * (pc["b"] - pc["a"])
            allow = pc["half"] + tol                     # a hollow tube's centreline is in its bore
        d = _signed(mesh, pts)
        ok = d >= -allow
        if ok.mean() < INSIDE_MIN:
            worst = int(np.argmin(d))
            bad.append(f"{pc['name']}: {100 * (1 - ok.mean()):.0f}% of it is outside the solid, up to "
                       f"{-d[worst]:.0f} mm out (at {_xyz(pts[worst])})")
    share = 1 - len(bad) / max(len(pieces), 1)
    return AssertionResult(
        id="construction_inside", expr="every piece construction() lists lies in the solid build() makes",
        status="pass" if not bad else "fail", passed=not bad, actual=round(share, 3),
        margin=round(share - 1.0, 3),
        detail="; ".join(bad[:6]) + (" — move each piece to where it is in build(), in the same frame"
                                     if bad else ""))


def _proud(mesh, pts: np.ndarray, out: np.ndarray, reach: float, n: int = 25) -> np.ndarray:
    """How far the solid carries on from each point along ``out``, up to ``reach``: where the column first leaves it."""
    steps = np.linspace(0.0, reach, n)
    inside = np.stack([_signed(mesh, pts + out * s) >= 0 for s in steps], axis=1)
    leaves = np.where(inside.all(axis=1), n - 1, (~inside).argmax(axis=1))
    return steps[leaves]


def _in_a_piece(points: np.ndarray, pieces: list[dict], skip: dict, tol: float) -> np.ndarray:
    near = np.full(len(points), np.inf)
    for pc in pieces:
        if pc is skip:
            continue
        if pc["kind"] == "sheet":
            for p, side in zip(pc["polys"], pc["sides"]):
                near = np.minimum(near, slab_distance(points, p, pc["thickness"], side))
        else:
            near = np.minimum(near, segment_distance(points, pc["a"], pc["b"]) - pc["reach"])
    return near <= tol


def _on_its_face(mesh, pieces: list[dict], tol: float) -> AssertionResult:
    """Each sheet's outline is a face of the panel, on the solid's surface (#162). Declared off it, the panel is built
    in the wrong place and the solid left over it, the part of the panel that's missing, reads as the printed rest:
    the bar stool's seat, outlined at its mid-thickness, counted 9.5 mm of its top as PETG with nothing to say so. So: is
    there solid beyond the outline, on the side away from the panel, that no other piece accounts for?"""
    bad = []
    sheets = [pc for pc in pieces if pc["kind"] == "sheet"]
    for pc in sheets:
        for poly, side in zip(pc["polys"], pc["sides"]):
            pts = polygon_samples(poly, holes=pc.get("holes") if len(pc["polys"]) == 1 else ())
            n = np.asarray(C.polygon(poly.tolist())[2], float)
            out = -side * n / np.linalg.norm(n)
            proud = _proud(mesh, pts, out, pc["thickness"] + tol)
            if len(pc["polys"]) > 1:                    # a facet is a chord of the curve: judged at its edges, where it's on it
                proud = np.full_like(proud, np.percentile(proud, 10))
            limit = max(tol, 0.1 * pc["thickness"])
            # the mistake's signature: the solid ends inside the panel's own thickness. Solid running on past it is a block
            # the panel is set against or between, and an outline on either face of that is right (#170 review)
            over = (proud > limit) & (proud < 0.95 * pc["thickness"])
            if over.any():
                over[over] = ~_in_a_piece(pts[over] + out[None] * proud[over, None] / 2, pieces, pc, 0.5)
            if over.mean() >= 0.5:
                # to the tenth it's said to, on the column at the median: the steps are coarser than that
                at = int(np.argsort(proud[over])[len(proud[over]) // 2])
                lo, hi = float(proud[over][at]) - pc["thickness"] / 12, float(proud[over][at]) + pc["thickness"] / 12
                column = pts[over][at]
                for _ in range(10):
                    mid = (lo + hi) / 2
                    lo, hi = (mid, hi) if _signed(mesh, (column + out * mid)[None])[0] >= 0 else (lo, mid)
                off = lo
                way = "below" if out[2] > 0.7 else "above" if out[2] < -0.7 else "off"
                bad.append(f"{pc['name']}: declared {off:.1f} mm {way} where the part has it")
                break
    share = 1 - len(bad) / max(len(sheets), 1)
    return AssertionResult(
        id="construction_on_its_face", expr="each sheet's outline is a face of the panel, on the solid's surface",
        status="pass" if not bad else "fail", passed=not bad, actual=round(share, 3), margin=round(share - 1.0, 3),
        detail="; ".join(bad[:6]) + (": an outline is a face of the panel, not its mid-plane. Until it's moved, what's left "
                                     "over the panel is counted as the printed part" if bad else ""))


#: how far past its outline a panel's solid may run and still be the same size: a saw's kerf, a loose fit (#183)
PLAN_TOL_MM = 3.0
#: how much of an outline has to be short before it's said: less than this is a tab, not the panel's size
PLAN_MIN_RUN_MM = 25.0
_NEAR = np.array([1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0])


def _past_outline(mesh, points: np.ndarray, out: np.ndarray, pieces: list[dict], skip: dict) -> np.ndarray:
    """How far the solid runs on from each point, along its ``out``: to where it ends, or sooner where another piece takes over."""
    from . import spatial

    past = np.zeros(len(points))
    inside = _signed(mesh, points) >= 0
    if not inside.any():
        return past
    hit, ray, _ = spatial.intersects_location(mesh, points[inside], out[inside], multiple_hits=False)
    ends = np.zeros(len(points))
    ends[np.flatnonzero(inside)[ray]] = np.linalg.norm(hit - points[inside][ray], axis=1)
    steps = np.sort(np.concatenate([np.repeat(_NEAR[None], len(points), axis=0), ends[:, None] * np.linspace(0, 1, 18)[1:-1]], axis=1), axis=1)
    steps = np.where(steps < ends[:, None], steps, np.inf)
    usable = np.isfinite(steps)
    grid = points[:, None] + out[:, None] * np.where(usable, steps, 0.0)[:, :, None]
    theirs = np.zeros(steps.shape, bool)
    theirs[usable] = _in_a_piece(grid[usable], pieces, skip, 0.5)
    first = np.where(theirs.any(axis=1), theirs.argmax(axis=1), -1)
    took = np.where(first >= 0, steps[np.arange(len(points)), first], np.inf)
    return np.minimum(ends, took)


def plan_differs(declared: Optional[dict], geometry) -> list[dict]:
    """The sheets cut smaller than the solid they're part of, in plan: ``[{name, outline, solid}]``, the two sizes in mm along the
    outline's own axes. Only where a printed rest takes whatever the pieces aren't: anywhere else that solid is uncovered, and
    :func:`_covers` says so. The stool's seat was cut 16-sided and 11.2 in across from a 12 in round disk, and the 0.8 in went to
    the printed rest with nothing to say so (#183). Edge by edge, so the edges that are right can't outvote the one that's short
    (#183 review); and along the whole of an edge, so a chord of a true curve, on the curve at its ends, is the same size. It's
    said, not failed: a panel set in a printed rim looks the same, and only the person knows which they meant."""
    if not declared or declared.get("error") or getattr(geometry, "mesh", None) is None:
        return []
    if not any(isinstance(it, dict) and it.get("kind") == "printed" and it.get("rest") for it in declared.get("construction") or []):
        return []
    mesh, pieces = geometry.mesh, shapes(declared)
    _sides(mesh, pieces)
    out = []
    for pc in pieces:
        if pc["kind"] != "sheet" or len(pc["polys"]) != 1:
            continue
        poly, side = np.asarray(pc["polys"][0], float), pc["sides"][0]
        o, u, v, n, _ = _frame(poly)
        u, v, n = (np.asarray(a, float) for a in (u, v, n))
        edges = np.roll(poly, -1, axis=0) - poly
        lengths = np.linalg.norm(edges, axis=1)
        each = np.maximum(5, np.round(96 * lengths / lengths.sum()).astype(int))
        at = np.concatenate([poly[i] + edges[i] * ((np.arange(k) + 0.5) / k)[:, None] for i, k in enumerate(each)])
        along = np.concatenate([np.repeat(edges[i][None] / lengths[i], k, axis=0) for i, k in enumerate(each)])
        away = np.cross(along, np.cross(u, v))      # the frame's axes follow the outline's own winding, so this is outward
        owner = np.repeat(np.arange(len(poly)), each)
        points = at + n * side * pc["thickness"] / 2 + away * 0.01
        past = _past_outline(mesh, points, away, pieces, pc)
        short = [i for i in range(len(poly)) if np.percentile(past[owner == i], 10) > PLAN_TOL_MM]
        if lengths[short].sum() < PLAN_MIN_RUN_MM:
            continue
        reached = np.concatenate([poly, at + away * past[:, None]])
        size = lambda q: [float(np.ptp((q - o) @ a)) for a in (u, v)]   # noqa: E731
        cut, drawn = size(poly), size(reached)
        if max(b - a for a, b in zip(cut, drawn)) <= PLAN_TOL_MM:    # a notch in it, not a smaller panel: no two sizes to say
            continue
        out.append({"name": pc["name"], "outline": cut, "solid": drawn})
    return out


def plan_said(s: dict, inches: bool) -> str:
    """One :func:`plan_differs` entry in words, the same on the card, the scorecard and the build book."""
    from .answers import _len

    cut, drawn = (" x ".join(_len(v, inches) for v in s[k]) for k in ("outline", "solid"))
    return (f"The {s['name'].replace('_', ' ')} you'd cut is {cut}, but the model has it at {drawn}. The cut list and patterns follow "
            "the smaller outline; say which you want and I'll revise it.")


def cut_smaller(store, part_ids) -> list[str]:
    """In words, every sheet here cut smaller than the model: for the scorecard and the build book (#183 review). A warning, so a
    part that can't be read leaves nothing to say rather than stopping either."""
    from . import construction as C

    inches = store.design.display_units == "in"
    out = []
    for pid in part_ids:
        try:
            out += [plan_said(s, inches) for s in plan_differs(C.declared(store, pid), store.part_geometry(pid))]
        except Exception:  # noqa: BLE001
            continue
    return out


def remedy(detail: str) -> str:
    """What to say for a sheet off its face: the shape is right and the declared piece is wrong, so it's the outline that
    moves (#170 review: "fix its shape to match its pieces" would change a correct seat to match a wrong outline)."""
    import re

    m = re.match(r"(.+?): declared [\d.]+ mm (below|above|off) where", detail)
    if not m:
        return "move each sheet's outline onto its face"
    where = {"below": "up to its top face", "above": "down to its underside", "off": "onto its face"}[m.group(2)]
    return f"move the {m.group(1)}'s outline {where}"


def _covers(mesh, pieces: list[dict], tol: float) -> AssertionResult:
    import trimesh

    pts, _ = trimesh.sample.sample_surface(mesh, SURFACE_SAMPLES, seed=0)
    near = np.full(len(pts), np.inf)
    for pc in pieces:
        if pc["kind"] == "sheet":
            for p, side in zip(pc["polys"], pc["sides"]):
                near = np.minimum(near, slab_distance(pts, p, pc["thickness"], side))
        else:
            near = np.minimum(near, segment_distance(pts, pc["a"], pc["b"]) - pc["reach"])
    covered = near <= tol
    share = float(covered.mean())
    detail = ""
    if share < COVER_MIN:
        off = pts[~covered]
        lo, hi = off.min(axis=0), off.max(axis=0)
        detail = (f"{100 * (1 - share):.0f}% of the solid's surface isn't on any piece: around "
                  f"{_xyz(off.mean(axis=0))}, within x {lo[0]:.0f}..{hi[0]:.0f}, y {lo[1]:.0f}..{hi[1]:.0f}, "
                  f"z {lo[2]:.0f}..{hi[2]:.0f} — add the piece that's there, or take it out of build() (a panel in the shape thicker than its sheet shows up here too)")
    return AssertionResult(
        id="construction_covers", expr=f"the pieces cover the solid's surface (≥ {COVER_MIN:.0%})",
        status="pass" if share >= COVER_MIN else "fail", passed=share >= COVER_MIN,
        actual=round(share, 3), margin=round(share - COVER_MIN, 3), detail=detail)


def _in_no_piece(mesh, pieces: list[dict], tol: float, n: int = 14) -> float:
    """The share of the solid (on a grid through it) that's in no piece: a sheet's slab or a stick's section."""
    lo, hi = mesh.bounds
    g = [np.linspace(a, b, n + 2)[1:-1] for a, b in zip(lo, hi)]
    pts = np.stack(np.meshgrid(*g, indexing="ij"), -1).reshape(-1, 3)
    from . import spatial

    pts = pts[spatial.contains(mesh, pts)]
    if not len(pts):
        return 0.0
    near = np.full(len(pts), np.inf)
    for pc in pieces:
        if pc["kind"] == "sheet":
            for p, side in zip(pc["polys"], pc["sides"]):
                near = np.minimum(near, slab_distance(pts, p, pc["thickness"], side))
        else:
            near = np.minimum(near, segment_distance(pts, pc["a"], pc["b"]) - pc["reach"])
    return float((near > tol).mean())


def _volume(mesh, pieces: list[dict], strength: bool = False, tol: float = 2.0) -> Optional[AssertionResult]:
    """The pieces' volume against the solid's. ``strength``: the part's strength check analyses the solid itself
    (it declares loads()), so a solid much bigger than its pieces fails too."""
    solid = float(mesh.volume)
    if solid <= 0:
        return None
    ratio = sum(pc["volume"] for pc in pieces) / solid
    heavy = sorted(pieces, key=lambda pc: -pc["volume"])[:3]
    loose = _in_no_piece(mesh, pieces, tol) if strength else 0.0
    if strength and (ratio < VOLUME_MIN or loose > SOLID_IN_NO_PIECE):
        # a solid block round its panels (CALI-83: Theo's stool was built as a filled box): every panel lies in
        # it and covers its surface, so only the volume shows it
        core = ratio >= VOLUME_MIN                    # the volumes pass, and the share in no piece fails (CALI-87)
        return AssertionResult(
            id="construction_volume",
            expr=(f"no more than {SOLID_IN_NO_PIECE:.0%} of the solid is in no piece" if core
                  else f"the solid is its pieces ({VOLUME_MIN:g}–{VOLUME_MAX:g}× its volume)"),
            status="fail", passed=False, actual=round(loose if core else ratio, 3),
            margin=round(SOLID_IN_NO_PIECE - loose if core else ratio - VOLUME_MIN, 3),
            detail=(f"the solid ({solid / 1e6:.2f} L) is {1 / ratio:.1f}× what the pieces add up to, and "
                    f"{loose:.0%} of it is in no piece: build() is filled in "
                    f"or a piece isn't in construction(), and the strength check analyses the solid. Make build() the "
                    f"pieces themselves, each panel as thick as its sheet and hollow between them, as it will really be "
                    f"built, or add the missing piece (solid legs, say) to construction()"))   # either cause (#64 item 12)
    ok = ratio <= VOLUME_MAX
    return AssertionResult(
        id="construction_volume", expr=(f"the solid is its pieces ({VOLUME_MIN:g}–{VOLUME_MAX:g}× its volume)" if strength
                                         else f"no more material than the solid holds (≤ {VOLUME_MAX:g}× its volume)"),
        status="pass" if ok else "fail", passed=ok, actual=round(ratio, 3), margin=round(VOLUME_MAX - ratio, 3),
        detail="" if ok else (f"the pieces add up to {ratio:.2f}× the solid ({solid / 1e6:.2f} L): check each "
                              f"sheet's thickness against build(), and that no piece is listed twice (biggest: "
                              + ", ".join(f"{pc['name']} {pc['volume'] / 1e6:.2f} L" for pc in heavy) + ")"))


def _loads(mesh, declared: dict, pieces: list[dict], tol: float) -> AssertionResult:
    """Every load says how much and where, and where is on the part: a load in thin air is a box in the
    wrong place, and the strength study would find nothing to push on. Asked as the strength check asks it
    (``load_study.touches``, within one of its voxels), so the two can't disagree (CALI-84); held() too."""
    from . import load_study as L

    try:
        loads = L.parse_loads(declared["loads"])
        held = L.parse_held(declared.get("held"), mesh.bounds.tolist(), 1.0) if declared.get("held") else []
    except (ValueError, TypeError) as e:
        return AssertionResult(id="loads_land", expr="every load in loads() says how much and where",
                               status="fail", passed=False, actual=None,
                               detail=f"{e} (see the loads() format)")
    rch = L.reach(tol, L.study_spacing(declared, mesh, pieces)[0])
    missed = []
    for item, support in [(h, True) for h in held] + [(ld, False) for ld in loads]:
        on, gap = L.touches(mesh, (item["lo"], item["hi"]), rch)
        if not on:
            missed.append(L.missed(item["name"], gap, rch, support))
    ok = not missed
    return AssertionResult(id="loads_land", expr="every load in loads() pushes on the part",
                           status="pass" if ok else "fail", passed=ok, actual=len(loads) + len(held) - len(missed),
                           detail="; ".join(missed))


def _edge_foot(mesh, declared: dict, pieces: list[dict], tol: float, rest: bool = False) -> Optional[AssertionResult]:
    """CALI-94 (#73): a top or tread held on just two sides is stood on at its free front edge, where it's weakest
    (BS 8110 cl. 3.5.2.2's edge width, NEEDS ENGINEER CHECK). If no load puts a foot there, say so: a warning, not
    a fail (the round still passes). None when there's no two-sided top to ask about."""
    from . import load_study as L

    try:
        loads = L.parse_loads(declared["loads"])
    except (ValueError, TypeError, KeyError):
        return None                                        # _loads says what's wrong with them
    from . import spatial

    # a top on printed sides (a printed rest, CALI-82) rests on the solid under it, as the plate check reads it
    under = (lambda pts: spatial.contains(mesh, pts)) if rest else None
    tops: dict = {}
    for ld in loads:
        got = L.two_sided(pieces, ld, tol, under)
        if got:
            tops.setdefault(got["piece"], []).append(got["free"])
    if not tops:
        return None
    bare = [name for name, gaps in tops.items() if min(gaps) > L.AT_EDGE_MM]
    detail = "; ".join(f"the {name} is held on two sides, and no load stands on its free edge, where it's weakest: "
                       f"add a case, the same foot mid-span with its edge on the free edge (\"stepping on the front "
                       f"edge\")" for name in bare)
    return AssertionResult(id="loads_edge", expr="a top held on two sides is stood on at its free edge too",
                           status="pass", passed=True, actual=len(tops) - len(bare), detail=detail)
_FILLED: dict = {}
_EDGE: dict = {}
#: What a strength ✓ says while a two-sided top has no foot at its free edge (CALI-94, #106 review).
MIDDLE_ONLY = ("checked in the middle only; the front edge, where people stand, isn't checked (add a \"stepping on "
               "the front edge\" case)")


def bare_edge(store, part_id: str) -> Optional[str]:
    """CALI-94 (#106 review): the loads_edge warning's detail while a part's two-sided top has no foot at its free
    edge, else None. Its strength ✓ isn't one then: the case where people stand wasn't checked. Kept per version and
    script, as filled() is."""
    from . import construction as C

    entry = store.design.part(part_id)
    try:
        script = store.read_script(part_id)
    except (OSError, KeyError, ValueError):
        return None
    key = (store.root, part_id, entry.version if entry else None, hash(script))
    if key not in _EDGE:
        out = None
        try:
            declared = C.declared(store, part_id)
            if declared.get("loads"):
                got = next((r for r in check(declared, store.part_geometry(part_id)) if r.id == "loads_edge"), None)
                out = (got.detail or None) if got is not None else None
        except Exception:  # noqa: BLE001 — this only ever takes a ✓ away; a part that won't check is said elsewhere
            out = None
        _EDGE[key] = out
        while len(_EDGE) > 64:
            _EDGE.pop(next(iter(_EDGE)))
    return _EDGE[key]


def filled(store, part_id: str) -> Optional[str]:
    """CALI-96: why a part's strength check isn't trusted, or None: a part with loads() whose build() is filled in
    round its pieces (the volume check fails that way), so the check analysed a block, not the part as built.
    Kept per version and script, as a card asks again on every redraw."""
    from . import construction as C

    entry = store.design.part(part_id)
    try:
        script = store.read_script(part_id)
    except (OSError, KeyError, ValueError):
        return None
    key = (store.root, part_id, entry.version if entry else None, hash(script))
    if key not in _FILLED:
        out = None
        try:
            declared = C.declared(store, part_id)
            if declared.get("loads"):
                vol = next((r for r in check(declared, store.part_geometry(part_id)) if r.id == "construction_volume"), None)
                if vol is not None and not vol.passed and "filled in" in (vol.detail or ""):
                    out = vol.detail
        except Exception as e:  # noqa: BLE001 — closed, not open: a shape that couldn't be checked isn't trusted
            return f"couldn't check its shape against its pieces ({type(e).__name__}: {e})"   # and not kept
        _FILLED[key] = out
        while len(_FILLED) > 64:
            _FILLED.pop(next(iter(_FILLED)))
    return _FILLED[key]


def check(declared: Optional[dict], geometry) -> list[AssertionResult]:
    """The declarations measured against the built solid: [] when the part declares nothing."""
    if not declared:
        return []
    if declared.get("error"):
        return [AssertionResult(id="construction_reads", expr="its declarations (construction(), members(), loads()) run",
                                status="error", passed=False, actual=None, detail=declared["error"])]
    try:
        pieces = shapes(declared)
    except (ValueError, KeyError, TypeError) as e:
        what = f"missing {e}" if isinstance(e, KeyError) else str(e)
        return [AssertionResult(id="construction_reads", expr="every piece is one Caliper can weigh",
                                status="fail", passed=False, actual=None,
                                detail=f"{what} (see the materials table and the piece formats)")]
    mesh = getattr(geometry, "mesh", None)
    if mesh is None:
        return []
    tol = tolerance(mesh)
    out = []
    # a printed rest (CALI-82: a plywood top on printed sides) is everything the pieces aren't, so it covers the
    # rest of the solid by definition: only that each piece is inside it can be checked
    rest = any(isinstance(it, dict) and it.get("kind") == "printed" and it.get("rest")
               for it in declared.get("construction") or [])
    if pieces:
        _sides(mesh, pieces)
        out.append(_inside(mesh, pieces, tol))
        out.append(_on_its_face(mesh, pieces, tol))
        if not rest:
            out.append(_covers(mesh, pieces, tol))
            vol = _volume(mesh, pieces, strength=bool(declared.get("loads")), tol=tol)
            out += [vol] if vol else []
    if declared.get("loads") is not None:
        out.append(_loads(mesh, declared, pieces, tol))
        if pieces:
            edge = _edge_foot(mesh, declared, pieces, tol, rest)  # a warning, said in its detail (CALI-94)
            out += [edge] if edge else []
    return out


def middle_only(store, part_id: str, run: dict, history: Optional[list] = None) -> bool:
    """Whether a strength run's ✓ is the middle only (CALI-94): its own history line says so, or the part as it is
    now has a two-sided top with no foot at its free edge (as the design state judges its runs). For the readers that
    judge a run away from the design state: Studies, the design card's last-checked line (#106 review sweep)."""
    for h in history if history is not None else store.history(part_id):
        if h.get("kind") == "load" and h.get("action") == "studied" and h.get("run") == run.get("id"):
            if h.get("middle_only"):
                return True
            break
    return bool(bare_edge(store, part_id))
