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
    g = box_geom()
    for fn in (measure.interference, measure.min_clearance):
        with pytest.raises(NotImplementedError):
            fn(g, ref=None)


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
