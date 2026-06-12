"""CALI-2 — the sensing / measurement API (MVP subset).

Numbers are ground truth; the render is only a sanity check (design spec §4). Every function here
returns an exact computed quantity off the geometry. The one exception is :func:`render_views`,
which produces images for the *vision* channel and is **forbidden from returning a measurement**.

MVP subset implemented (design spec §8):
    bounding_box, volume, mass, min_wall_thickness, holes / holes_matching,
    largest_through_bore, is_watertight, is_manifold, body_count, render_views.

Reference probes ``interference`` / ``min_clearance`` (CALI-10 / M3) measure a part against an
imported fixed STL — overlap volume and signed gap — so the loop can fit a part to existing
geometry. The remaining deferred probes (overhang, slice, fea, mates) are present as documented
no-ops that raise :class:`NotImplementedError` so nothing has to be re-plumbed later (mates arrives
with multi-part assemblies, CALI-13; the rest in Phase 2+).

Geometry is carried by :class:`Geometry`, which may hold a triangle mesh (``trimesh``) and/or a
B-rep solid (CadQuery). Feature queries (holes, faces) prefer the B-rep where it's exact and cheap;
bulk/topological queries use the mesh. CadQuery is imported lazily so this module loads without OCCT.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Optional

import numpy as np
import trimesh


# ---------------------------------------------------------------------------
# Geometry container
# ---------------------------------------------------------------------------
@dataclass
class Geometry:
    """A part under measurement. Keep the B-rep alive as long as possible (richer measurement)."""

    mesh: Optional[trimesh.Trimesh] = None
    solid: Any = None  # a cadquery.Workplane or cadquery Solid, when available

    @classmethod
    def from_stl(cls, path: str) -> "Geometry":
        return cls(mesh=trimesh.load(path, force="mesh"))

    @classmethod
    def from_stl_posed(cls, path: str, position=None, rotation_deg=None) -> "Geometry":
        """Load an STL and place it by ``position`` (mm) + ``rotation_deg`` (three.js XYZ euler).

        Baking the pose at load time keeps the fit probes pose-agnostic — the geometry handed to
        ``interference``/``min_clearance`` is already where the user put it in the viewer (CALI-10).
        """
        m = trimesh.load(path, force="mesh")
        T = pose_matrix(position, rotation_deg)
        if not np.allclose(T, np.eye(4)):
            m = m.copy()
            m.apply_transform(T)
        return cls(mesh=m)

    @classmethod
    def from_mesh(cls, mesh: trimesh.Trimesh) -> "Geometry":
        return cls(mesh=mesh)

    @classmethod
    def from_cadquery(cls, wp: Any) -> "Geometry":
        """Wrap a CadQuery Workplane/Solid, tessellating a mesh alongside the B-rep."""
        return cls(mesh=_cadquery_to_trimesh(wp), solid=wp)

    def require_mesh(self) -> trimesh.Trimesh:
        if self.mesh is None:
            if self.solid is not None:
                self.mesh = _cadquery_to_trimesh(self.solid)
            else:
                raise ValueError("Geometry has no mesh")
        return self.mesh


def _cadquery_to_trimesh(wp: Any, tol: float = 0.05) -> trimesh.Trimesh:
    """Tessellate a CadQuery Workplane/Solid to a trimesh mesh."""
    solid = wp.val() if hasattr(wp, "val") else wp
    verts, faces = solid.tessellate(tol)
    v = np.array([[p.x, p.y, p.z] for p in verts], dtype=float)
    f = np.array(faces, dtype=int)
    return trimesh.Trimesh(vertices=v, faces=f, process=True)


# ---------------------------------------------------------------------------
# Dimensional (mesh)
# ---------------------------------------------------------------------------
def bounding_box(g: Geometry) -> SimpleNamespace:
    """Axis-aligned bounding box. ``.dx/.dy/.dz`` plus ``.min/.max`` corners (mm)."""
    m = g.require_mesh()
    lo, hi = m.bounds
    d = hi - lo
    return SimpleNamespace(
        dx=float(d[0]), dy=float(d[1]), dz=float(d[2]),
        min=[float(x) for x in lo], max=[float(x) for x in hi],
    )


def volume(g: Geometry) -> float:
    """Solid volume in mm^3 (absolute, so winding/orientation can't make it negative)."""
    return float(abs(g.require_mesh().volume))


def mass(g: Geometry, density: float) -> float:
    """Mass in grams. ``density`` in g/cm^3 (PLA ≈ 1.24); mesh units are mm."""
    return volume(g) / 1000.0 * density  # mm^3 -> cm^3 then * g/cm^3


def center_of_mass(g: Geometry) -> list[float]:
    return [float(x) for x in g.require_mesh().center_mass]


# ---------------------------------------------------------------------------
# Topological (mesh)
# ---------------------------------------------------------------------------
def is_watertight(g: Geometry) -> bool:
    return bool(g.require_mesh().is_watertight)


def is_manifold(g: Geometry) -> bool:
    m = g.require_mesh()
    return bool(m.is_watertight and m.is_winding_consistent)


def body_count(g: Geometry) -> int:
    """Number of disconnected bodies."""
    m = g.require_mesh()
    return int(len(m.split(only_watertight=False)))


# ---------------------------------------------------------------------------
# Features — wall thickness (mesh, ray-cast)
# ---------------------------------------------------------------------------
def min_wall_thickness(g: Geometry, samples: int = 2000, seed: int = 0) -> float:
    """Smallest local material thickness, by ray-casting inward from the surface.

    Method: sample points on the surface, step just inside along the inward normal, cast a ray
    along the inward normal, and take the distance to the first opposite surface hit. The minimum
    over samples approximates the thinnest wall. For a solid block this is its smallest dimension.
    Approximate but deterministic (fixed seed); exact-enough for the printability assertion.
    """
    m = g.require_mesh()
    rng = np.random.default_rng(seed)
    pts, face_idx = trimesh.sample.sample_surface(m, samples, seed=int(rng.integers(1 << 31)))
    normals = m.face_normals[face_idx]
    eps = max(m.scale * 1e-4, 1e-6)
    origins = pts - normals * eps          # nudge just inside the surface
    directions = -normals                  # cast inward
    locations, index_ray, _ = m.ray.intersects_location(
        ray_origins=origins, ray_directions=directions, multiple_hits=False
    )
    if len(locations) == 0:
        return float("nan")
    dists = np.linalg.norm(locations - origins[index_ray], axis=1)
    dists = dists[dists > eps * 2]
    return float(dists.min()) if len(dists) else float("nan")


# ---------------------------------------------------------------------------
# Features — holes (best on B-rep / CadQuery)
# ---------------------------------------------------------------------------
@dataclass
class Hole:
    center: list[float]
    axis: list[float]
    diameter: float
    depth: float


def holes(g: Geometry) -> list[Hole]:
    """Inventory of cylindrical features (holes/bores), detected on the B-rep.

    Requires a CadQuery solid: cylindrical faces are exact there and intractable on a raw mesh.
    Each interior cylindrical face is reported as a :class:`Hole` (diameter = 2·radius).
    """
    if g.solid is None:
        raise ValueError("holes() needs a B-rep solid (Geometry.from_cadquery). Mesh-only hole "
                         "detection is not part of the MVP subset.")
    return _holes_from_cadquery(g.solid)


def _holes_from_cadquery(wp: Any) -> list[Hole]:
    import cadquery as cq  # lazy

    solid = wp.val() if hasattr(wp, "val") else wp
    found: list[Hole] = []
    for f in solid.Faces():
        if f.geomType() != "CYLINDER":
            continue
        # OCCT cylinder face: radius + axis from the underlying surface.
        from OCP.BRepAdaptor import BRepAdaptor_Surface  # type: ignore

        adaptor = BRepAdaptor_Surface(f.wrapped)
        cyl = adaptor.Cylinder()
        radius = cyl.Radius()
        ax = cyl.Axis()
        loc = ax.Location()
        dir_ = ax.Direction()
        bb = f.BoundingBox()
        depth = max(bb.xlen, bb.ylen, bb.zlen)
        found.append(
            Hole(
                center=[loc.X(), loc.Y(), loc.Z()],
                axis=[dir_.X(), dir_.Y(), dir_.Z()],
                diameter=2.0 * radius,
                depth=float(depth),
            )
        )
    return found


class Circle:
    """A bolt-circle pattern descriptor used by ``holes_matching(on=circle(d))``."""

    def __init__(self, diameter: float):
        self.diameter = float(diameter)
        self.radius = self.diameter / 2.0


def circle(diameter: float) -> Circle:
    return Circle(diameter)


def holes_matching(
    g: Geometry,
    diameter: float,
    on: Optional[Circle] = None,
    count: Optional[int] = None,
    tol: float = 0.3,
) -> bool:
    """True if the part has ``count`` holes of ``diameter`` (±tol), optionally on bolt-circle ``on``."""
    hs = holes(g)
    matched = [h for h in hs if abs(h.diameter - diameter) <= tol]
    if on is not None:
        # centers must sit on a circle of the given radius (about their centroid, any axis-plane).
        if matched:
            centers = np.array([h.center for h in matched])
            centroid = centers.mean(axis=0)
            radii = np.linalg.norm(centers - centroid, axis=1)
            matched = [h for h, r in zip(matched, radii) if abs(r - on.radius) <= max(tol, 1.0)]
    if count is not None:
        return len(matched) == count
    return len(matched) > 0


def largest_through_bore(g: Geometry) -> float:
    """Diameter of the largest cylindrical bore (0.0 if none detected)."""
    hs = holes(g) if g.solid is not None else []
    return max((h.diameter for h in hs), default=0.0)


def faces(g: Geometry) -> list[dict]:
    """Face inventory from the B-rep: type, normal/axis, area."""
    if g.solid is None:
        raise ValueError("faces() needs a B-rep solid (Geometry.from_cadquery)")
    solid = g.solid.val() if hasattr(g.solid, "val") else g.solid
    out = []
    for f in solid.Faces():
        try:
            n = f.normalAt()
            normal = [n.x, n.y, n.z]
        except Exception:
            normal = None
        out.append({"type": f.geomType(), "normal": normal, "area": float(f.Area())})
    return out


# ---------------------------------------------------------------------------
# Visual — the vision channel: SANITY ONLY, never a measurement
# ---------------------------------------------------------------------------
def render_views(g: Geometry, views=("front", "top", "iso"), out_dir: str = "runs") -> list[str]:
    """Render canonical views for the vision channel. Returns image *paths*, never numbers.

    Best-effort: if offscreen rendering is unavailable, writes placeholder files so the loop's
    image-path contract still holds. Enforced by architecture: this function cannot report a metric.
    """
    import os

    m = g.require_mesh()
    os.makedirs(out_dir, exist_ok=True)
    paths: list[str] = []
    for view in views:
        path = os.path.join(out_dir, f"render_{view}.png")
        try:
            png = m.scene().save_image(resolution=(640, 480), visible=True)
            with open(path, "wb") as fh:
                fh.write(png)
        except Exception:
            # offscreen GL not available — write a placeholder so the path contract holds.
            with open(path, "wb") as fh:
                fh.write(b"")
        paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# References — fit/clearance against an imported fixed part (CALI-10 / M3)
# ---------------------------------------------------------------------------
# These are the "Stage 2" probes (design spec §4): does the part collide with, or keep enough
# room around, an imported reference? Both are computed on meshes so they work on STL references
# without a B-rep. `interference` reports the *overlap volume* (0.0 = clean); `min_clearance`
# reports the signed gap (positive = smallest air gap, negative = deepest penetration). The
# evaluator turns these into margins, and the loop tunes the part until they pass.

_FIT_SAMPLES = 3000  # surface samples per body for the proximity probes (deterministic seeds)
_FIT_EPS = 1e-6


def pose_matrix(position=None, rotation_deg=None) -> np.ndarray:
    """4×4 transform from a translation (mm) and an XYZ-intrinsic euler rotation (degrees).

    Matches three.js ``object.matrix`` for an Euler of default order ``XYZ`` (rotate about the
    object's local origin, then translate) so the viewer gizmo and the measured pose agree.
    """
    T = np.eye(4)
    if rotation_deg is not None and any(abs(float(a)) > 1e-9 for a in rotation_deg):
        from scipy.spatial.transform import Rotation  # lazy: scipy only needed for posed references

        T[:3, :3] = Rotation.from_euler("XYZ", [float(a) for a in rotation_deg], degrees=True).as_matrix()
    if position is not None:
        T[:3, 3] = [float(x) for x in position]
    return T


def _as_mesh(obj: Any) -> trimesh.Trimesh:
    """Coerce a reference handle to a mesh: a :class:`Geometry`, a raw mesh, or a wrapper with one."""
    if isinstance(obj, Geometry):
        return obj.require_mesh()
    if isinstance(obj, trimesh.Trimesh):
        return obj
    geom = getattr(obj, "geometry", None)
    if isinstance(geom, Geometry):
        return geom.require_mesh()
    mesh = getattr(obj, "mesh", None)
    if isinstance(mesh, trimesh.Trimesh):
        return mesh
    raise ValueError(
        "reference has no geometry to measure against — load it first "
        "(Geometry.from_stl(...)) and pass it as the reference."
    )


def _aabb_overlap(a: trimesh.Trimesh, b: trimesh.Trimesh, pad: float = 0.0) -> bool:
    alo, ahi = a.bounds
    blo, bhi = b.bounds
    return bool(np.all(ahi + pad >= blo) and np.all(bhi + pad >= alo))


def _aabb_overlap_volume(a: trimesh.Trimesh, b: trimesh.Trimesh) -> float:
    alo, ahi = a.bounds
    blo, bhi = b.bounds
    d = np.clip(np.minimum(ahi, bhi) - np.maximum(alo, blo), 0.0, None)
    return float(d.prod())


def _sample(mesh: trimesh.Trimesh, n: int, seed: int) -> np.ndarray:
    pts, _ = trimesh.sample.sample_surface(mesh, n, seed=seed)
    return np.asarray(pts)


def _boolean_intersection_volume(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[float]:
    """Exact overlap volume via a robust boolean (manifold3d). None if the kernel is unavailable."""
    try:
        inter = trimesh.boolean.intersection([a, b])
    except Exception:
        return None
    if inter is None:
        return None
    if getattr(inter, "is_empty", False) or len(getattr(inter, "faces", [])) == 0:
        return 0.0
    return float(abs(inter.volume))


def _meshes_overlap(a: trimesh.Trimesh, b: trimesh.Trimesh, n: int = _FIT_SAMPLES) -> bool:
    """Containment-sampling overlap test — the boolean-free fallback for detecting interference."""
    try:
        if b.contains(_sample(a, n, seed=1)).any():
            return True
        if a.contains(_sample(b, n, seed=2)).any():
            return True
    except Exception:
        return False
    return False


def interference(g: Geometry, ref: Any) -> float:
    """Volume of material the part shares with the reference, in mm^3 (0.0 = no collision).

    Exact via a robust mesh boolean (manifold3d) when available; falls back to a containment test
    bounded by the AABB-overlap volume if the boolean kernel is missing. AABB-disjoint pairs short
    circuit to 0.0. Use in an assertion as ``interference(part_ref) <= 0``.
    """
    a = g.require_mesh()
    b = _as_mesh(ref)
    if not _aabb_overlap(a, b):
        return 0.0
    vol = _boolean_intersection_volume(a, b)
    if vol is not None:
        return vol
    return _aabb_overlap_volume(a, b) if _meshes_overlap(a, b) else 0.0


def _penetration_depth(a: trimesh.Trimesh, b: trimesh.Trimesh, n: int = _FIT_SAMPLES) -> float:
    """Deepest distance any surface point of one body lies inside the other (0.0 if disjoint)."""
    depth = 0.0
    for first, second, seed in ((a, b, 1), (b, a, 2)):
        try:
            pts = _sample(first, n, seed=seed)
            inside = second.contains(pts)
            if inside.any():
                _, dist, _ = second.nearest.on_surface(pts[inside])
                depth = max(depth, float(np.max(dist)))
        except Exception:
            continue
    return depth


def _surface_gap(a: trimesh.Trimesh, b: trimesh.Trimesh, n: int = _FIT_SAMPLES) -> float:
    """Smallest distance between the two surfaces (assumes they don't intersect)."""
    _, d_ab, _ = b.nearest.on_surface(_sample(a, n, seed=1))
    _, d_ba, _ = a.nearest.on_surface(_sample(b, n, seed=2))
    return float(min(np.min(d_ab), np.min(d_ba)))


def min_clearance(g: Geometry, ref: Any) -> float:
    """Smallest gap between the part and the reference, in mm (negative if they interpenetrate).

    Positive = the thinnest air gap between the two surfaces; negative = the deepest penetration
    (so an assertion ``min_clearance(part_ref) >= 0.4`` fails both when too close and when colliding).
    Mesh-based (works on STL references); deterministic via fixed sampling seeds.
    """
    a = g.require_mesh()
    b = _as_mesh(ref)
    pen = _penetration_depth(a, b)
    if pen > _FIT_EPS:
        return -pen
    return _surface_gap(a, b)


# ---------------------------------------------------------------------------
# N-body — the assembly substrate (CALI-20): the same pair probes, over every pair
# ---------------------------------------------------------------------------
# An assembly is N posed bodies with named relationships. The two-body probes above already accept
# any pair of Geometry-likes (``interference``/``min_clearance`` coerce both sides via ``_as_mesh``),
# so the N-body layer is just "run the pair probe over every unordered pair" plus the worst-case
# reductions an assembly-level assertion wants (``no pair collides`` / ``every pair keeps clearance``).

def _as_pairs(parts: Any) -> list[tuple[str, Any]]:
    """Normalize ``{id: geom}`` or ``[(id, geom), ...]`` (or a bare list) to ``[(id, geom)]``."""
    if isinstance(parts, dict):
        return list(parts.items())
    out: list[tuple[str, Any]] = []
    for i, p in enumerate(parts):
        if isinstance(p, (tuple, list)) and len(p) == 2:
            out.append((str(p[0]), p[1]))
        else:
            out.append((str(i), p))
    return out


def pairwise_interference(parts: Any) -> list[tuple[str, str, float]]:
    """Overlap volume (mm^3) for every unordered pair of bodies — ``[(id_a, id_b, volume), ...]``.

    ``parts`` is ``{id: Geometry}`` (or ``[(id, geom), ...]``). The collision substrate for an
    assembly: a clean assembly has every entry's volume == 0.
    """
    items = _as_pairs(parts)
    out: list[tuple[str, str, float]] = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (ida, ga), (idb, gb) = items[i], items[j]
            out.append((ida, idb, interference(ga, gb)))
    return out


def max_interference(parts: Any) -> float:
    """Worst overlap volume across all pairs (0.0 if nothing collides / fewer than two bodies).

    Use as ``max_interference() <= 0`` — one assertion that no pair of parts interpenetrates.
    """
    return max((v for _, _, v in pairwise_interference(parts)), default=0.0)


def min_pair_clearance(parts: Any) -> float:
    """Smallest signed gap across all pairs (``inf`` if fewer than two bodies).

    Negative ⇒ some pair interpenetrates; otherwise the tightest air gap anywhere in the assembly.
    """
    items = _as_pairs(parts)
    gaps = [
        min_clearance(items[i][1], items[j][1])
        for i in range(len(items)) for j in range(i + 1, len(items))
    ]
    return min(gaps) if gaps else float("inf")


# ---------------------------------------------------------------------------
# DEFERRED probes — present as documented no-ops (design spec §4, §7)
# ---------------------------------------------------------------------------
def mates(g: Geometry, ref: Any, tol: float = 0.2):
    raise NotImplementedError("mates(): deferred to CALI-13 (multi-part assemblies / joints).")


def overhang_area(g: Geometry, angle: float, build_dir: Any):
    raise NotImplementedError("overhang_area(): deferred to Phase 2 (printability).")


def slice_part(g: Geometry, profile: Any):
    raise NotImplementedError("slice(): deferred to Phase 2 (slicer-in-loop).")


def fea(g: Geometry, loads: Any, supports: Any, material: Any):
    raise NotImplementedError("fea(): deferred to Phase 3 (simulation).")
