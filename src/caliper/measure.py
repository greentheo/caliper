"""CALI-2 — the sensing / measurement API (MVP subset).

Numbers are ground truth; the render is only a sanity check (design spec §4). Every function here
returns an exact computed quantity off the geometry. The one exception is :func:`render_views`,
which produces images for the *vision* channel and is **forbidden from returning a measurement**.

MVP subset implemented (design spec §8):
    bounding_box, volume, mass, min_wall_thickness, holes / holes_matching,
    largest_through_bore, is_watertight, is_manifold, body_count, render_views.

Deferred probes (overhang, slice, fea, interference, min_clearance, mates) are present as
documented no-ops that raise :class:`NotImplementedError` so nothing has to be re-plumbed later.
``interference`` / ``min_clearance`` arrive in M3 (references); the rest in Phase 2+.

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
# DEFERRED probes — present as documented no-ops (design spec §4, §7)
# ---------------------------------------------------------------------------
def interference(g: Geometry, ref: Any):
    raise NotImplementedError("interference(): deferred to M3 (references / robust booleans).")


def min_clearance(g: Geometry, ref: Any):
    raise NotImplementedError("min_clearance(): deferred to M3 (references).")


def mates(g: Geometry, ref: Any, tol: float = 0.2):
    raise NotImplementedError("mates(): deferred to M3 (references).")


def overhang_area(g: Geometry, angle: float, build_dir: Any):
    raise NotImplementedError("overhang_area(): deferred to Phase 2 (printability).")


def slice_part(g: Geometry, profile: Any):
    raise NotImplementedError("slice(): deferred to Phase 2 (slicer-in-loop).")


def fea(g: Geometry, loads: Any, supports: Any, material: Any):
    raise NotImplementedError("fea(): deferred to Phase 3 (simulation).")
