"""CALI-2 — measurement API against known primitives."""

import math

import pytest

from caliper import measure
from caliper.measure import Geometry


def test_bounding_box(box_geom):
    bb = measure.bounding_box(box_geom(10, 20, 30))
    assert math.isclose(bb.dx, 10, abs_tol=1e-6)
    assert math.isclose(bb.dy, 20, abs_tol=1e-6)
    assert math.isclose(bb.dz, 30, abs_tol=1e-6)


def test_volume_and_mass(box_geom):
    g = box_geom(10, 20, 30)
    assert math.isclose(measure.volume(g), 6000.0, rel_tol=1e-6)
    # 6000 mm^3 = 6 cm^3; PLA @1.24 g/cm^3 -> 7.44 g
    assert math.isclose(measure.mass(g, density=1.24), 7.44, rel_tol=1e-6)


def test_topology(box_geom, two_box_geom):
    g = box_geom()
    assert measure.is_watertight(g) is True
    assert measure.is_manifold(g) is True
    assert measure.body_count(g) == 1
    assert measure.body_count(two_box_geom) == 2


def test_min_wall_thickness_is_smallest_dimension(box_geom):
    # For a solid block, ray-cast-inward thickness equals the smallest extent.
    mw = measure.min_wall_thickness(box_geom(10, 20, 30))
    assert math.isclose(mw, 10.0, abs_tol=0.5)


def test_holes_need_brep_on_mesh_only(box_geom):
    with pytest.raises(ValueError):
        measure.holes(box_geom())


def test_largest_through_bore_zero_without_solid(box_geom):
    assert measure.largest_through_bore(box_geom()) == 0.0


def test_deferred_probes_raise(box_geom):
    # interference/min_clearance are real now (CALI-10); mates et al. remain deferred.
    g = box_geom()
    with pytest.raises(NotImplementedError):
        measure.mates(g, ref=None)


# --- B-rep hole detection (needs CadQuery/OCCT) ---------------------------
def test_holes_on_cadquery_plate():
    cq = pytest.importorskip("cadquery")
    # 40x40x5 plate with a single Ø6 through hole at the center
    wp = cq.Workplane("XY").box(40, 40, 5).faces(">Z").workplane().hole(6.0)
    g = Geometry.from_cadquery(wp)
    hs = measure.holes(g)
    assert any(abs(h.diameter - 6.0) <= 0.3 for h in hs)


def test_holes_matching_bolt_circle():
    cq = pytest.importorskip("cadquery")
    # four Ø5.2 holes on a Ø60 bolt circle
    wp = (
        cq.Workplane("XY").box(80, 80, 6)
        .faces(">Z").workplane()
        .polarArray(radius=30, startAngle=0, angle=360, count=4)
        .hole(5.2)
    )
    g = Geometry.from_cadquery(wp)
    assert measure.holes_matching(g, diameter=5.2, on=measure.circle(60), count=4)



# --- body_count: cavities are not bodies -------------------------------------------------
def _box_with_cavity():
    """A 20 mm cube with a sealed 10 mm cubic void inside: one body, two surfaces."""
    import trimesh

    outer = trimesh.creation.box(extents=(20, 20, 20))
    inner = trimesh.creation.box(extents=(10, 10, 10))
    inner.invert()                                   # a cavity's surface faces into the cavity
    return Geometry.from_mesh(trimesh.util.concatenate([outer, inner]))


def test_a_sealed_cavity_is_not_counted_as_a_body():
    """Seen live: a welded hollow-tube frame read as 6 bodies — its tubes' enclosed bores."""
    g = _box_with_cavity()
    assert len(g.require_mesh().split(only_watertight=False)) == 2      # two surfaces...
    assert measure.body_count(g) == 1                                            # ...one body


def test_separate_solids_are_still_counted(two_box_geom):
    assert measure.body_count(two_box_geom) == 2


def test_a_hollow_tube_frame_with_enclosed_bores_is_one_body():
    pytest.importorskip("cadquery")
    import cadquery as cq

    def tube(lo, hi, axis):
        size, inner = [20, 20, 20], [16, 16, 16]
        size[axis], inner[axis] = hi - lo, hi - lo + 2
        c = [0, 0, 0]
        c[axis] = (lo + hi) / 2
        o = cq.Workplane("XY").box(*size).translate(tuple(c))
        return o.cut(cq.Workplane("XY").box(*inner).translate(tuple(c)))

    # a cross tube along y, and a tube along x whose open end sits inside it (its bore is sealed)
    t = tube(-50, 50, 1).union(tube(-8, 100, 0))
    g = Geometry.from_cadquery(t)
    assert measure.body_count(g) == 1
