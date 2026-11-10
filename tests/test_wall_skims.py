"""CALI-146 (#189) — the thinnest-wall probe read a square corner as a thin wall. A ray launched beside a corner runs along the next
face and meets it at a glance. On a copy of the stool with its openings cut clean, five of 20,000 rays did that and the rule read
1.8 mm where every neighbouring ray read 5.3 mm or more. It can't be loosened to get a part through: a real thin wall beside a
corner must still read thin (rule 6)."""

import numpy as np
import pytest

from caliper import measure
from caliper.measure import Geometry

cq = pytest.importorskip("cadquery")

N = 20000


def _mesh(wp):
    import tempfile

    import trimesh

    with tempfile.NamedTemporaryFile(suffix=".stl") as f:
        cq.exporters.export(wp, f.name, tolerance=0.02, angularTolerance=0.1)
        return Geometry.from_mesh(trimesh.load(f.name, force="mesh"))


def _window(tilt_deg: float, thickness: float = 6.0):
    """A plate with a square window whose sides lean ``tilt_deg``: a corner that isn't quite square, as a cutter on a slope leaves."""
    plate = cq.Workplane("XY").box(100, 100, thickness, centered=(True, True, False))
    cutter = (cq.Workplane("XY").workplane(offset=-1).rect(40, 40).extrude(thickness + 2, taper=tilt_deg))
    return _mesh(plate.cut(cutter))


@pytest.mark.parametrize("tilt", [0.0, 0.5, 1.0, 2.0, 3.0])
def test_a_window_with_near_square_corners_reads_the_plate_s_thickness(tilt):
    got = measure.thinnest_wall(_window(tilt), samples=N)[0]
    assert got == pytest.approx(6.0, abs=0.15), f"read {got}"


def test_the_corner_really_was_read_thin_before():
    g = _window(2.0)
    old, measure.SKIM_SIN = measure.SKIM_SIN, -1.0
    try:
        assert measure.thinnest_wall(g, samples=N)[0] < 3.0
    finally:
        measure.SKIM_SIN = old


def _web(web: float, tilt: float = 2.0):
    """A block with a slot beside a near-square window, leaving a web ``web`` thick: a real thin wall right beside a corner."""
    block = cq.Workplane("XY").box(100, 60, 20, centered=(True, True, False))
    window = cq.Workplane("XY").workplane(offset=-1).center(-20, 0).rect(40, 30).extrude(22, taper=tilt)
    # its near side is at about x = 0 at the top: a pocket on the far side of the web leaves ``web`` between them
    far = cq.Workplane("XY").workplane(offset=-1).center(20 + web, 0).rect(40, 30).extrude(22)
    return _mesh(block.cut(window).cut(far))


@pytest.mark.parametrize("web", [0.5, 1.0, 2.0])
def test_a_real_thin_web_beside_a_corner_still_reads_thin(web):
    got = measure.thinnest_wall(_web(web, tilt=0.0), samples=N)[0]
    assert got == pytest.approx(web, abs=0.1), f"read {got}"


def test_a_thin_web_between_near_square_windows_still_reads_thin():
    got = measure.thinnest_wall(_web(1.5, tilt=2.0), samples=N)[0]
    assert got <= 1.6, f"read {got}"                                   # the web is its thinnest at the bottom of the lean


def _sliver():
    """A wedge tapering to nothing: 40 mm long, from 3 mm to 0.05 mm."""
    return _mesh(cq.Workplane("XZ").polyline([(0, 0), (40, 0), (40, 0.05), (0, 3)]).close().extrude(20))


def test_a_tapering_sliver_still_reads_thin():
    got = measure.thinnest_wall(_sliver(), samples=N)[0]
    assert got < 0.3, f"read {got}"


def test_a_knife_edge_corner_isn_t_a_skim():
    """A 60° corner really does thin to nothing: only a corner within 5° of square is left out."""
    g = _mesh(cq.Workplane("XZ").polyline([(0, 0), (40, 0), (20, 34.64)]).close().extrude(20))
    assert measure.thinnest_wall(g, samples=N)[0] < 1.0


@pytest.mark.parametrize("deg,kept", [(4.0, False), (6.0, True)])
def test_the_line_is_at_five_degrees(monkeypatch, deg, kept):
    """A corner that's 4° off square is a corner; 6° off is read as it is."""
    d, _ = measure.wall_samples(_window(deg), N, 0)
    assert bool(d.min() < 5.5) is kept


def test_a_solid_block_is_still_its_smallest_dimension():
    assert measure.min_wall_thickness(_mesh(cq.Workplane("XY").box(10, 20, 30))) == pytest.approx(10.0, abs=0.1)
    assert np.isfinite(measure.thinnest_wall(_window(0.0), samples=2000)[0])
