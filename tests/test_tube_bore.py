"""CALI-18 (#23) — largest_through_bore counted a tube's outer wall as a bore: both are cylinders. Only a cylinder whose material
is outside it (its face looks in, at the axis) is a hole. Found while authoring a grommet."""

import pytest

cq = pytest.importorskip("cadquery")

from caliper import measure  # noqa: E402


def _g(wp):
    return measure.Geometry.from_cadquery(wp)


def test_a_tube_s_bore_is_its_inside_not_its_outside():
    tube = cq.Workplane("XY").circle(20).circle(10).extrude(30)          # 40 mm outside, 20 mm bore
    assert measure.largest_through_bore(_g(tube)) == pytest.approx(20.0)
    assert [round(h.diameter, 3) for h in measure.holes(_g(tube))] == [20.0]


def test_a_plate_with_a_real_hole_reads_the_hole():
    plate = cq.Workplane("XY").box(50, 50, 10).faces(">Z").workplane().hole(8)
    assert measure.largest_through_bore(_g(plate)) == pytest.approx(8.0)
    assert len(measure.holes(_g(plate))) == 1


def test_a_solid_rod_has_no_bore():
    rod = cq.Workplane("XY").circle(15).extrude(40)
    assert measure.largest_through_bore(_g(rod)) == 0.0 and measure.holes(_g(rod)) == []


def test_a_grommet_s_bore_is_its_hole():
    """The grommet: a flanged tube, two outer cylinders and one bore."""
    grommet = (cq.Workplane("XY").circle(15).extrude(3).faces(">Z").workplane().circle(10).extrude(8)
               .faces(">Z").workplane().hole(12))
    assert measure.largest_through_bore(_g(grommet)) == pytest.approx(12.0)
    assert [round(h.diameter, 3) for h in measure.holes(_g(grommet))] == [12.0]
