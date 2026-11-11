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
    # world transform applied to this part in an assembly (CALI-25). The mesh is baked into world frame
    # at load; the B-rep solid is kept in its LOCAL frame, so feature probes that read the solid (holes)
    # transform their results by this pose to compare parts in the assembly frame. None == identity.
    pose: Any = None

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
        return cls(mesh=m, pose=T)

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
    """Tessellate a CadQuery Workplane/Solid to a trimesh mesh, without the CAD mesher's strays (:func:`clean`)."""
    solid = wp.val() if hasattr(wp, "val") else wp
    verts, faces = solid.tessellate(tol)
    v = np.array([[p.x, p.y, p.z] for p in verts], dtype=float)
    f = np.array(faces, dtype=int)
    return clean(trimesh.Trimesh(vertices=v, faces=f, process=True))


#: A loose open shell this small, against the part's whole surface, is the mesher's, not the part's (CALI-118): it
#: bounds nothing, and at the 0.05 mm tessellation tolerance it moves the volume by at most its area × 0.05 mm,
#: about 0.1 mm³ on Theo's bar stool (2.28 m² of surface). Anything bigger is an opening, and is kept, and said.
STRAY_SHARE = 1e-6


def clean(m: trimesh.Trimesh) -> trimesh.Trimesh:
    """The mesh without what the CAD's mesher leaves that isn't the part (CALI-118, #126):

    - faces with no area. OCCT fans a cone's triangles from its apex, and one of them comes out with two corners on
      the apex (Theo's bar stool v7: the cone's apex at the flange, a 37 mm sliver of no area). It encloses nothing;
      with it the mesh isn't one closed body, and every boolean on it threw "Not all meshes are volumes!";
    - loose open shells under :data:`STRAY_SHARE` of the surface, beside a closed body.

    What it left out is said, once, in ``m.metadata["strays"]``. A bigger open shell, or a part with no closed
    body, is left as it is: :func:`open_near` says where it's open, and a reader that needs a solid says so."""
    if closed(m) or not len(m.faces):
        return m
    gone, where = 0, []
    flat = ~m.nondegenerate_faces(height=1e-9)
    if flat.any():
        where.append(m.vertices[m.faces[flat]].reshape(-1, 3))
        gone += int(flat.sum())
        m = m.copy()
        m.update_faces(~flat)
        m.remove_unreferenced_vertices()
    if not closed(m):
        bodies = m.split(only_watertight=False)
        whole = [b for b in bodies if closed(b)]
        strays = [b for b in bodies if not closed(b) and b.area <= STRAY_SHARE * m.area]
        if whole and len(whole) + len(strays) == len(bodies) and strays:
            where += [b.vertices for b in strays]
            gone += sum(len(b.faces) for b in strays)
            m = trimesh.util.concatenate(whole) if len(whole) > 1 else whole[0]
    if gone:
        pts = np.vstack(where)
        z0, z1 = float(pts[:, 2].min()), float(pts[:, 2].max())
        m.metadata["strays"] = (f"left out {gone} stray face{'s' if gone != 1 else ''} from the CAD's meshing "
                                f"(at z {z0:.1f}" + (f"–{z1:.1f}" if z1 - z0 >= 0.05 else "") + " mm)")
        m.metadata["strays_n"], m.metadata["strays_z"] = gone, [z0, z1]    # for a card in the design's units (#89)
    return m


def closed(m: trimesh.Trimesh, volume: bool = False) -> bool:
    """Closed as it will be read back: two vertices at one point (a pinch) are watertight in memory and merge in any
    STL round trip, after which it isn't (#124 review). Judged on a merged copy, so every reader agrees. ``volume``:
    and a volume too (its faces wound consistently outward), as a solid to weigh or adopt needs (#134)."""
    if not m.is_watertight:  # raw: closed() itself
        return False
    merged = m.copy()
    merged.merge_vertices()
    return bool(merged.is_watertight) and (not volume or bool(merged.is_volume))  # raw: closed() itself, merged


def open_near(m: trimesh.Trimesh) -> Optional[str]:
    """Where a mesh isn't closed, in words ("near z 14 mm"), or None when it's one closed solid. What a reader that
    needs a solid (a boolean, a voxel check, a weight) says instead of throwing (CALI-118)."""
    if closed(m):
        return None
    from trimesh.grouping import group_rows

    m = m.copy()
    m.merge_vertices()
    edges = m.edges_sorted
    # an edge with other than two faces: one (an opening) or more (a pinch, four faces on an edge: #134 review)
    rows = group_rows(edges)
    off = np.array([edges[r[0]] for r in rows if len(r) != 2])
    pts = m.vertices[off.reshape(-1)] if len(off) else m.vertices
    z0, z1 = float(pts[:, 2].min()), float(pts[:, 2].max())
    return "near z " + (f"{z0:.0f} mm" if z1 - z0 < 1 else f"{z0:.0f}–{z1:.0f} mm")


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
        # by name, for a rule (the evaluator reads attributes, not indexes): bbox(mast).max_z (CALI-35)
        min_x=float(lo[0]), min_y=float(lo[1]), min_z=float(lo[2]),
        max_x=float(hi[0]), max_y=float(hi[1]), max_z=float(hi[2]),
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
    """Closed as it reads back (:func:`closed`, CALI-121): a pinch isn't, whatever trimesh says in memory."""
    return closed(g.require_mesh())


def is_manifold(g: Geometry) -> bool:
    m = g.require_mesh()
    return bool(closed(m) and m.is_winding_consistent)


def body_count(g: Geometry) -> int:
    """Number of separate solid bodies — enclosed cavities are not bodies.

    Counting connected mesh surfaces over-counts hollow parts: where a tube's open end sits inside
    another tube, its bore becomes an enclosed pocket of air whose surface is a separate shell (seen
    live: a one-piece welded tube frame read as 6 "bodies"). With a B-rep, count its solids, which is
    exact. With only a mesh, count outward-facing shells: a cavity's surface faces into the cavity, so
    its signed volume is negative.
    """
    solid = getattr(g, "solid", None)
    if solid is not None:
        try:
            shape = solid.val() if hasattr(solid, "val") else solid
            n = len(shape.Solids())
            if n:
                return int(n)
        except Exception:  # noqa: BLE001 — fall back to the mesh
            pass
    m = g.require_mesh()
    shells = m.split(only_watertight=False)
    return int(sum(1 for s in shells if not closed(s) or s.volume > 0))


# ---------------------------------------------------------------------------
# Features — wall thickness (mesh, ray-cast)
# ---------------------------------------------------------------------------
#: a ray that meets the face it ends on within this angle of parallel measured a corner, not a wall (#189). The stool's read 2° or
#: less; 5° leaves room for a facet's error. Loosening this reads real walls as thicker: nothing changes it to get a part through
SKIM_DEG = 5.0
SKIM_SIN = float(np.sin(np.radians(SKIM_DEG)))


def min_wall_thickness(g: Geometry, samples: int = 2000, seed: int = 0) -> float:
    """Smallest local material thickness (:func:`thinnest_wall`'s number)."""
    return thinnest_wall(g, samples, seed)[0]


def thinnest_wall(g: Geometry, samples: int = 2000, seed: int = 0) -> tuple[float, Optional[list]]:
    """The thinnest wall (:func:`wall_samples`) and where it is (the middle of its ray, mm), so a line can say where
    to thicken it (#136 review)."""
    dists, mids = wall_samples(g, samples, seed)
    if not len(dists):
        return float("nan"), None
    i = int(np.argmin(dists))
    return float(dists[i]), [round(float(v), 1) for v in mids[i]]


def wall_near(g: Geometry, point, radius: float, samples: int = 20000, seed: int = 0,
              walls: Optional[tuple] = None) -> Optional[float]:
    """The thinnest wall within ``radius`` of ``point`` (say, an FEA's hottest voxel), or None where no sample falls
    that near (#137 item 2: is the worst stress among walls too thin for the voxels?). ``walls``: :func:`wall_samples`
    already taken."""
    dists, mids = walls if walls is not None else wall_samples(g, samples, seed)
    if not len(dists):
        return None
    near = np.linalg.norm(mids - np.asarray(point, float)[None], axis=1) <= radius
    return float(dists[near].min()) if near.any() else None


def wall_samples(g: Geometry, samples: int = 2000, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Smallest local material thickness, by ray-casting inward from the surface.

    Method: sample points on the surface, step just inside along the inward normal, cast a ray
    along the inward normal, and take the distance to the first opposite surface hit, leaving out a ray that only skims
    the next face at a corner (:data:`SKIM_DEG`). The minimum over samples approximates the thinnest wall. For a solid block this is its smallest dimension.
    Approximate but deterministic (fixed seed); exact-enough for the printability assertion. Returns each sampled
    thickness and the middle of its ray (mm).
    """
    m = g.require_mesh()
    rng = np.random.default_rng(seed)
    pts, face_idx = trimesh.sample.sample_surface(m, samples, seed=int(rng.integers(1 << 31)))
    normals = m.face_normals[face_idx]
    eps = max(m.scale * 1e-4, 1e-6)
    origins = pts - normals * eps          # nudge just inside the surface
    directions = -normals                  # cast inward
    from . import spatial

    locations, index_ray, index_tri = spatial.intersects_location(m, origins, directions, multiple_hits=False)
    if len(locations) == 0:
        return np.zeros(0), np.zeros((0, 3))
    dists = np.linalg.norm(locations - origins[index_ray], axis=1)
    # a ray launched beside a square corner runs along the next face and meets it at a glance: that's the corner, not a wall.
    # A wall's far side is met nearly head on, however close to a corner the ray starts
    facing = np.abs(np.einsum("ij,ij->i", m.face_normals[index_tri], directions[index_ray]))
    ok = (dists > eps * 2) & (facing >= SKIM_SIN)
    return dists[ok], (locations[ok] + origins[index_ray[ok]]) / 2


# ---------------------------------------------------------------------------
# Features — holes (best on B-rep / CadQuery)
# ---------------------------------------------------------------------------
@dataclass
class Hole:
    center: list[float]
    axis: list[float]
    diameter: float
    depth: float


class NotMeasured(NotImplementedError, ValueError):
    """A measurement this part can't have: the evaluator reads it as not checked ("deferred"), never a pass. Still a
    ValueError, as holes() raised before, for any caller that catches that."""


#: Said when a part has no B-rep to find holes in (CALI-90, #66 item 5: [] and 0 passed "largest_through_bore <= 5").
MESH_HOLES = "not measured: the part is a mesh (carved, whittled or imported), with no B-rep to find holes in"


def holes(g: Geometry) -> list[Hole]:
    """Inventory of cylindrical features (holes/bores), detected on the B-rep.

    Requires a CadQuery solid: cylindrical faces are exact there and intractable on a raw mesh.
    Each interior cylindrical face is reported as a :class:`Hole` (diameter = 2·radius).
    """
    if g.solid is None:
        raise NotMeasured(MESH_HOLES)
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
    return max((h.diameter for h in holes(g)), default=0.0)      # a mesh: NotMeasured, never a silent 0


# ---------------------------------------------------------------------------
# Hole alignment across parts (CALI-25) — "do the bolt holes line up?"
# ---------------------------------------------------------------------------
# An assembly joins parts with fasteners; the measurement that proves a joint is buildable is that a
# hole in one part is coaxial with a hole in the next, so a screw passes through both. Holes are exact
# on the B-rep (`holes`), detected in the part's LOCAL frame; `holes_world` applies the part's `pose`
# so holes from different parts are comparable in the assembly frame.

def holes_world(g: Geometry) -> list[Hole]:
    """Holes of ``g`` with center + axis transformed into the assembly (world) frame by ``g.pose``."""
    if g.solid is None:
        raise NotMeasured(MESH_HOLES)
    hs = _holes_from_cadquery(g.solid)
    T = getattr(g, "pose", None)
    if T is None or np.allclose(T, np.eye(4)):
        return hs
    R, t = np.asarray(T)[:3, :3], np.asarray(T)[:3, 3]
    out = []
    for h in hs:
        c = R @ np.asarray(h.center, float) + t
        a = R @ np.asarray(h.axis, float)
        out.append(Hole(center=[float(x) for x in c], axis=[float(x) for x in a],
                        diameter=h.diameter, depth=h.depth))
    return out


def _unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def min_hole_misalignment(a: Geometry, b: Geometry, parallel_tol_deg: float = 25.0) -> float:
    """Smallest axis-offset (mm) between a hole of ``a`` and a (near-parallel) hole of ``b``.

    0.0 = some pair of holes is perfectly coaxial (a screw passes straight through both). Only pairs
    whose axes are within ``parallel_tol_deg`` of parallel are considered; the metric is the
    perpendicular distance from one hole's center to the other hole's axis line. ``inf`` if no parallel
    pair exists (→ the assertion ``hole_misalignment(a, b) <= tol`` fails). Raises
    :class:`NotImplementedError` if either part has no detectable holes (needs a B-rep source).
    """
    ha, hb = holes_world(a), holes_world(b)
    if not ha or not hb:
        raise NotImplementedError(
            "hole alignment needs detectable holes on both parts (a B-rep source, e.g. a .py part)")
    cos_tol = float(np.cos(np.radians(parallel_tol_deg)))
    best = float("inf")
    for h1 in ha:
        u1, c1 = _unit(h1.axis), np.asarray(h1.center, float)
        for h2 in hb:
            u2, c2 = _unit(h2.axis), np.asarray(h2.center, float)
            if abs(float(np.dot(u1, u2))) < cos_tol:
                continue  # axes not parallel enough to share a screw
            w = c2 - c1
            perp = w - np.dot(w, u1) * u1   # offset of c2 from the line through c1 along u1
            best = min(best, float(np.linalg.norm(perp)))
    return best


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
        from . import spatial

        if spatial.contains(b, _sample(a, n, seed=1)).any():
            return True
        if spatial.contains(a, _sample(b, n, seed=2)).any():
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
            from . import spatial

            inside = spatial.contains(second, pts)
            if inside.any():
                _, dist, _ = spatial.on_surface(second, pts[inside])
                depth = max(depth, float(np.max(dist)))
        except Exception:
            continue
    return depth


def _surface_gap(a: trimesh.Trimesh, b: trimesh.Trimesh, n: int = _FIT_SAMPLES) -> float:
    """Smallest distance between the two surfaces (assumes they don't intersect)."""
    from . import spatial

    _, d_ab, _ = spatial.on_surface(b, _sample(a, n, seed=1))
    _, d_ba, _ = spatial.on_surface(a, _sample(b, n, seed=2))
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


# ---------------------------------------------------------------------------
# CALI-162 (#240) — a part in another's pocket: the gap on each side, measured
# ---------------------------------------------------------------------------
#: How far a side's gap may sit from the plan's clearance and still fit (#240): the clearance ± this.
POCKET_TOL_MM = 0.5
#: A pocket's clearance a side when the plan gives none: 0.3 mm, a snug slip fit in plywood.
POCKET_CLEARANCE_MM = 0.3


def pocket(inserted: Geometry, host: Any) -> dict:
    """The gaps round a part where it goes into another's pocket, slot or hole (CALI-162, #240: step-stool-4's sides
    had pockets for a 2×4 and a 3/4 in plywood stretcher in them, and the touch rules couldn't see it).

    The axis it goes in along is the one it sticks out of the host on. From its centre line, half way into the host,
    a ray each way across the other two axes finds the host's first wall: the gap that side is that distance less half
    the part's size, negative where the part runs into the wall. A side with no wall (an open slot) has none.
    ``{"in": bool, "axis": "x", "gaps": {"+y": mm or None, "-y": …, "+z": …, "-z": …}, "why": str}``."""
    from . import spatial

    a, b = inserted.require_mesh(), _as_mesh(host)
    alo, ahi = a.bounds
    blo, bhi = b.bounds
    out = [max(0.0, blo[k] - alo[k]) + max(0.0, ahi[k] - bhi[k]) for k in range(3)]
    k = int(np.argmax(out))
    lo, hi = max(alo[k], blo[k]), min(ahi[k], bhi[k])
    if out[k] <= 0 or hi - lo <= 0.05:
        return {"in": False, "axis": "xyz"[k], "gaps": {}, "why": "doesn't go into it"}
    centre = (alo + ahi) / 2.0
    centre[k] = (lo + hi) / 2.0
    if bool(spatial.contains(b, [centre])[0]):
        return {"in": False, "axis": "xyz"[k], "gaps": {}, "why": "isn't in a pocket of it: its middle is in the solid"}
    gaps: dict = {}
    for i in (j for j in range(3) if j != k):
        half = (ahi[i] - alo[i]) / 2.0
        for sign in (1.0, -1.0):
            d = np.zeros(3)
            d[i] = sign
            loc, _, _ = spatial.intersects_location(b, np.array([centre]), np.array([d]))
            ahead = [float((p[i] - centre[i]) * sign) for p in loc if (p[i] - centre[i]) * sign > 1e-9]
            gaps[("+" if sign > 0 else "-") + "xyz"[i]] = round(min(ahead) - half, 3) if ahead else None
    return {"in": True, "axis": "xyz"[k], "gaps": gaps, "why": ""}


def fit_off(inserted: Geometry, host: Any, clearance: float = POCKET_CLEARANCE_MM) -> float:
    """How far the worst side of a part in a pocket sits from ``clearance``, in mm: a fit passes within
    :data:`POCKET_TOL_MM`. A part that doesn't go into the host raises (said, never a pass)."""
    got = pocket(inserted, host)
    if not got["in"]:
        raise ValueError(got["why"])
    sides = [g for g in got["gaps"].values() if g is not None]
    if not sides:
        raise ValueError("it has no wall on any side to fit against")
    return round(max(abs(g - clearance) for g in sides), 3)


def pocket_said(a: str, b: str, got: dict, clearance: float = POCKET_CLEARANCE_MM) -> str:
    """A fit in words, naming both parts and the play: "the stretcher has 19.1 mm of play in side_left's pocket"."""
    name = a.replace("_", " ")
    if not got.get("in"):
        return f"the {name} {got.get('why') or 'is not in it'} ({b})"
    loose, tight = [], []
    for axis in "xyz":
        pair = [got["gaps"].get(f"+{axis}"), got["gaps"].get(f"-{axis}")]
        if None in pair:
            continue
        total = pair[0] + pair[1]
        if min(pair) < 0:
            tight.append(-total if total < 0 else -min(pair))
        elif max(abs(g - clearance) for g in pair) > POCKET_TOL_MM:
            loose.append(total)
    if not loose and not tight:
        sides = [g for g in got["gaps"].values() if g is not None]
        return f"the {name} sits in {b}'s pocket with {min(sides):.1f}–{max(sides):.1f} mm a side"
    said = []
    if loose:
        said.append(f"has {max(loose):.1f} mm of play in {b}'s pocket")
    if tight:
        said.append(f"is {max(tight):.1f} mm too big for {b}'s pocket" if not loose else f"is {max(tight):.1f} mm too big for it the other way")
    return f"the {name} " + ", and ".join(said)
# CALI-161 (#239) — whether one part is another's mirror, measured
# ---------------------------------------------------------------------------
_PLANES = {"YZ": 0, "XZ": 1, "XY": 2, "ZY": 0, "ZX": 1, "YX": 2}


def mirror_off(g: Geometry, other: Any, plane: Optional[str] = None) -> float:
    """How far part ``g`` is from ``other`` mirrored: ``other`` reflected in ``plane`` (``"yz"``, ``"xz"`` or ``"xy"``;
    across the axis their middles are furthest apart on, if not given) through the point half way between them, and
    the volume where the two don't overlap, as a share of ``g``'s volume. 0 is an exact mirror (#239: a test named
    ``side_left_mirrors_side_right`` compared only the two bounding boxes' sides)."""
    a, b = g.require_mesh(), _as_mesh(other)
    ca, cb = a.bounds.mean(axis=0), b.bounds.mean(axis=0)
    if plane is None:
        k = int(np.argmax(np.abs(ca - cb)))
    else:
        if str(plane).upper() not in _PLANES:
            raise ValueError(f"a mirror's plane is yz, xz or xy, not {plane!r}")
        k = _PLANES[str(plane).upper()]
    at = (ca[k] + cb[k]) / 2.0
    flip = np.eye(4)
    flip[k, k], flip[k, 3] = -1.0, 2.0 * at
    m = b.copy()
    m.apply_transform(flip)
    m.invert() if m.volume < 0 else None           # a reflection turns the faces inside out
    vol = float(abs(a.volume))
    if vol <= 0:
        raise ValueError("the part has no volume to compare")
    only_a = float(abs(a.difference(m).volume))
    only_b = float(abs(m.difference(a).volume))
    return round((only_a + only_b) / vol, 6)
