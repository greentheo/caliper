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
VOLUME_MAX = 1.25
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


def polygon_samples(poly, n: int = GRID) -> np.ndarray:
    """Points spread over a flat polygon's face: a grid in its plane, kept where it's inside."""
    o, u, v, _, flat = _frame(np.asarray(poly, float))
    lo, hi = flat.min(axis=0), flat.max(axis=0)
    g = (np.arange(n) + 0.5) / n
    grid = np.stack(np.meshgrid(lo[0] + g * (hi[0] - lo[0]), lo[1] + g * (hi[1] - lo[1])), -1).reshape(-1, 2)
    keep = grid[_inside2d(grid, flat)]
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
            out.append({"name": name, "kind": "sheet", "polys": [np.asarray(p, float) for p in polys],
                        "thickness": t, "volume": sum(C.polygon(p)[0] for p in polys) * t})
        elif item.get("kind") == "stick":
            half, diag, area = _section(item)
            a, b = (np.asarray(item[k], float) for k in ("a", "b"))
            out.append({"name": name, "kind": "stick", "a": a, "b": b, "half": half, "reach": diag,
                        "volume": float(np.linalg.norm(b - a)) * area})
    return out


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------
def _signed(mesh, points: np.ndarray) -> np.ndarray:
    """Signed distance to the solid's surface: positive inside."""
    import trimesh

    return trimesh.proximity.signed_distance(mesh, points)


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
            pts, n = polygon_samples(poly), np.asarray(C.polygon(poly.tolist())[2], float)
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


def _volume(mesh, pieces: list[dict]) -> Optional[AssertionResult]:
    solid = float(mesh.volume)
    if solid <= 0:
        return None
    ratio = sum(pc["volume"] for pc in pieces) / solid
    ok = ratio <= VOLUME_MAX
    heavy = sorted(pieces, key=lambda pc: -pc["volume"])[:3]
    return AssertionResult(
        id="construction_volume", expr=f"no more material than the solid holds (≤ {VOLUME_MAX:g}× its volume)",
        status="pass" if ok else "fail", passed=ok, actual=round(ratio, 3), margin=round(VOLUME_MAX - ratio, 3),
        detail="" if ok else (f"the pieces add up to {ratio:.2f}× the solid ({solid / 1e6:.2f} L): check each "
                              f"sheet's thickness against build(), and that no piece is listed twice (biggest: "
                              + ", ".join(f"{pc['name']} {pc['volume'] / 1e6:.2f} L" for pc in heavy) + ")"))


def check(declared: Optional[dict], geometry) -> list[AssertionResult]:
    """The declarations measured against the built solid: [] when the part declares nothing."""
    if not declared:
        return []
    if declared.get("error"):
        return [AssertionResult(id="construction_reads", expr="construction() and members() run",
                                status="error", passed=False, actual=None, detail=declared["error"])]
    try:
        pieces = shapes(declared)
    except (ValueError, KeyError, TypeError) as e:
        what = f"missing {e}" if isinstance(e, KeyError) else str(e)
        return [AssertionResult(id="construction_reads", expr="every piece is one Caliper can weigh",
                                status="fail", passed=False, actual=None,
                                detail=f"{what} (see the materials table and the piece formats)")]
    mesh = getattr(geometry, "mesh", None)
    if not pieces or mesh is None:
        return []
    tol = tolerance(mesh)
    _sides(mesh, pieces)
    out = [_inside(mesh, pieces, tol), _covers(mesh, pieces, tol)]
    vol = _volume(mesh, pieces)
    return out + ([vol] if vol else [])
