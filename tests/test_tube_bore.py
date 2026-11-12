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


# --- #261 review -----------------------------------------------------------------------------------------------------------
def test_coaxial_holes_in_a_u_bracket_stay_four_holes():
    """Grouped by axis line alone, two coaxial 5 mm holes in a U-bracket's two sides were one bore. They're joined only where
    their faces meet along the axis."""
    u = (cq.Workplane("XZ").polyline([(0, 0), (60, 0), (60, 30), (56, 30), (56, 4), (4, 4), (4, 30), (0, 30)]).close()
         .extrude(-40).faces("<X").workplane(centerOption="CenterOfBoundBox").pushPoints([(-10, 0), (10, 0)]).hole(5))         # mid-wall, 10 mm either side of centre
    holes = measure.holes(_g(u))
    assert len(holes) == 4 and all(h.diameter == pytest.approx(5.0) for h in holes), [(h.diameter, h.center) for h in holes]
    assert all(h.depth == pytest.approx(4.0, abs=0.01) for h in holes)
    assert measure.holes_matching(_g(u), 5, count=4)


def test_a_slot_reads_no_bore():
    """A slot isn't a bore: its round ends are half turns. The safe side; a cable through a slot is another rule."""
    plate = cq.Workplane("XY").box(40, 40, 6).faces(">Z").workplane().slot2D(20, 8).cutThruAll()
    assert measure.largest_through_bore(_g(plate)) == 0.0
    assert "slot" in measure.largest_through_bore.__doc__


def test_the_through_test_runs_once_per_geometry():
    """1.77 s on a 100-hole plate on every evaluation: worked out once, and read again."""
    import time

    plate = cq.Workplane("XY").box(200, 200, 5).faces(">Z").workplane().rarray(18, 18, 10, 10).hole(6)
    g = _g(plate)
    assert measure.largest_through_bore(g) == pytest.approx(6.0)
    t0 = time.perf_counter()
    for _ in range(3):
        assert measure.largest_through_bore(g) == pytest.approx(6.0) and len(measure.holes(g)) == 100
    assert (time.perf_counter() - t0) / 3 < 0.2


def test_a_posed_part_s_bores_are_tested_where_its_mesh_is():
    """In an assembly the mesh is in the world frame and the solid in its own: a bore is moved by the pose before it's tested."""
    import numpy as np

    pose = np.eye(4)
    pose[:3, 3] = [500.0, 0.0, 0.0]

    def posed(wp):
        g = _g(wp)
        g.mesh = g.mesh.copy().apply_transform(pose)
        g.pose = pose
        return g

    blind = cq.Workplane("XY").box(40, 40, 6).faces(">Z").workplane().hole(8, depth=3)
    through = cq.Workplane("XY").box(40, 40, 6).faces(">Z").workplane().hole(8)
    assert measure.largest_through_bore(posed(blind)) == 0.0          # tested in its own frame, it read as through
    assert measure.largest_through_bore(posed(through)) == pytest.approx(8.0)
