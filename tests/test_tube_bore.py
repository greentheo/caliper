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


# --- #259 (CALI-169): a bore goes all the way through -------------------------------------------------------------------------
def test_a_counterbore_reads_the_hole_through_it_not_the_counterbore():
    """8 through, 14 × 4 deep: it read 14. What fits through is the 8."""
    part = (cq.Workplane("XY").box(40, 40, 12).faces(">Z").workplane()
            .cboreHole(8, cboreDiameter=14, cboreDepth=4))
    assert measure.largest_through_bore(_g(part)) == pytest.approx(8.0)


def test_a_blind_hole_isn_t_a_through_bore():
    """A blind 8 mm hole read 8."""
    part = cq.Workplane("XY").box(40, 40, 12).faces(">Z").workplane().hole(8, depth=5)
    assert measure.largest_through_bore(_g(part)) == 0.0
    (h,) = measure.holes(_g(part))
    assert h.diameter == pytest.approx(8.0) and h.depth == pytest.approx(5.0, abs=0.01)   # along the axis: it read 8


def test_a_pocket_over_a_small_hole_reads_the_small_hole():
    """A 20 mm pocket over a 6 mm through hole read 20."""
    part = (cq.Workplane("XY").box(40, 40, 12).faces(">Z").workplane().hole(20, depth=6)
            .faces(">Z").workplane().hole(6))
    assert measure.largest_through_bore(_g(part)) == pytest.approx(6.0)


def test_an_inside_fillet_isn_t_a_hole():
    """An L bracket's inside fillet, r5, looks in at its axis like a hole and read 10. It isn't a full turn."""
    bracket = (cq.Workplane("XZ").polyline([(0, 0), (40, 0), (40, 6), (6, 6), (6, 40), (0, 40)]).close().extrude(30)
               .edges("|Y").edges(cq.selectors.NearestToPointSelector((6, 0, 6))).fillet(5))
    assert measure.largest_through_bore(_g(bracket)) == 0.0 and measure.holes(_g(bracket)) == []


def test_a_grommet_with_a_counterbore_over_a_6_mm_hole_doesn_t_fit_an_8_mm_cable():
    """intake and refine write `cable_fits: largest_through_bore >= 8`: a 14 mm counterbore over 6 mm passed (a false green)."""
    grommet = (cq.Workplane("XY").circle(15).extrude(10).faces(">Z").workplane()
               .cboreHole(6, cboreDiameter=14, cboreDepth=4))
    assert measure.largest_through_bore(_g(grommet)) == pytest.approx(6.0)
