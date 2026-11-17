"""#298: a drag candidate's tessellation, read straight off OCC's triangulation, is CadQuery's ``tessellate()`` exactly.

reviewer-2's aero walk timed a candidate at 0.916 s, 95% of it the CAD rebuild. On the camper's cargo box that is
CadQuery's ``tessellate()``, and nearly all of it the Python copy of the triangles out of OCC (0.265 s of 0.278 s); the
build itself is 13 ms and OCC's mesher 13 ms. ``caliper.tess.triangles`` reads the same triangulation by index: the same
vertices and triangles, element for element, so a study's every number is unchanged."""

import os

import numpy as np
import pytest

cq = pytest.importorskip("cadquery")

from caliper import tess  # noqa: E402

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "samples")
TOLERANCES = [(0.5, 0.2), (0.05, 0.1)]          # a drag study's worker, and the app's measure (tessellate's default angle)


def _shape(script, params=None):
    from caliper._build_worker import _shape_of

    ns = {"cq": cq}
    exec(compile(script, "<part>", "exec"), ns)          # noqa: S102 — the repo's own fixtures
    return _shape_of(ns["build"](dict(params or ns.get("PARAMS") or {})), cq)


def _sample(name, part):
    return open(os.path.join(SAMPLES, name, "parts", part, "part.py")).read()


def _theirs(shape, tol, ang):
    v, f = shape.tessellate(tol, ang)
    return (np.array([p.toTuple() for p in v], dtype=np.float64).reshape(-1, 3),
            np.array(f, dtype=np.int64).reshape(-1, 3))


def _same(shape, tol, ang):
    # each from its own copy of the shape: a mesh left on it by the other never decides it
    mine = tess.triangles(shape.copy(), tol, ang)
    theirs = _theirs(shape.copy(), tol, ang)
    assert mine[0].dtype == np.float64 and mine[1].dtype == np.int64
    assert np.array_equal(mine[0], theirs[0]) and np.array_equal(mine[1], theirs[1])
    return mine


def _reversed(shape):
    from OCP.TopAbs import TopAbs_Orientation

    return sum(f.wrapped.Orientation() == TopAbs_Orientation.TopAbs_REVERSED for f in shape.Faces())


def _fixtures():
    from .test_piece_delete import HOLED, TUBED
    from .test_tipping import BAR_STOOL

    return {"the cargo box": _shape(_sample("camper", "cargo_box")),
            "the step stool": _shape(_sample("step-stool", "step_stool")),
            "a plate with a tube and a clip": _shape(TUBED),
            "a holed panel": _shape(HOLED),
            "a bar stool": _shape(BAR_STOOL)}


FIXTURES = None


def _get(name):
    global FIXTURES
    FIXTURES = FIXTURES or _fixtures()
    return FIXTURES[name]


@pytest.mark.parametrize("tol, ang", TOLERANCES)
@pytest.mark.parametrize("name", ["the cargo box", "the step stool", "a plate with a tube and a clip", "a holed panel",
                                  "a bar stool"])
def test_it_is_tessellate_element_for_element(name, tol, ang):
    v, f = _same(_get(name), tol, ang)
    assert len(v) and len(f)


def test_the_fixtures_have_what_it_must_get_right():
    """Faces wound the other way, curved faces and holes are in the fixtures above, or the test above proves nothing."""
    assert all(_reversed(_get(n)) for n in ("the step stool", "a plate with a tube and a clip", "a holed panel"))
    assert {f.geomType() for f in _get("a plate with a tube and a clip").Faces()} >= {"PLANE", "CYLINDER"}
    assert "BSPLINE" in {f.geomType() for f in _get("the cargo box").Faces()}


@pytest.mark.parametrize("tol, ang", TOLERANCES)
def test_a_moved_shape_s_nodes_are_where_it_is(tol, ang):
    """A face's Location moves its nodes: a box rotated and moved, as an assembly places a part."""
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCP.TopLoc import TopLoc_Location

    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0.7)
    t.SetTranslationPart(gp_Vec(120.0, -35.0, 8.0))
    cyl = cq.Workplane().cylinder(40, 15).val()
    moved = cyl.moved(cq.Location(TopLoc_Location(t)))
    assert not moved.wrapped.Location().IsIdentity()
    v, _ = _same(moved, tol, ang)
    assert v[:, 0].mean() > 60                      # the nodes went with it
    assert not np.allclose(_same(cyl, tol, ang)[0], v)


@pytest.mark.parametrize("tol, ang", TOLERANCES)
def test_a_compound_s_every_solid(tol, ang):
    a = cq.Workplane().box(10, 10, 10).val()
    b = cq.Workplane().sphere(6).translate((40, 0, 0)).val()
    both = cq.Compound.makeCompound([a, b])
    v, f = _same(both, tol, ang)
    assert v[:, 0].min() < 0 and v[:, 0].max() > 40 and f.max() == len(v) - 1


def test_a_shape_with_no_faces_is_empty_arrays_as_tessellate_gives_none():
    empty = cq.Compound.makeCompound([])
    v, f = tess.triangles(empty, 0.5, 0.2)
    assert v.shape == (0, 3) and f.shape == (0, 3) and _theirs(empty, 0.5, 0.2)[0].size == 0


def test_a_face_the_mesher_left_bare_is_skipped_as_tessellate_skips_it(monkeypatch):
    """No triangulation on a face (BRepMesh can leave one): its nodes and triangles are left out, and the next face's
    triangles still index the nodes that are there."""
    from OCP.BRep import BRep_Tool

    box = cq.Workplane().box(10, 20, 30).val()
    full = tess.triangles(box.copy(), 0.5, 0.2)
    shape = box.copy()
    shape.mesh(0.5, 0.2)
    bare = shape.Faces()[2].wrapped
    real = BRep_Tool.Triangulation_s

    class Tool:
        @staticmethod
        def Triangulation_s(face, loc):
            return None if face.IsSame(bare) else real(face, loc)

    import OCP.BRep

    monkeypatch.setattr(OCP.BRep, "BRep_Tool", Tool)
    v, f = tess.triangles(shape, 0.5, 0.2)
    assert len(v) == len(full[0]) - 4 and len(f) == len(full[1]) - 2       # a box face: 4 nodes, 2 triangles
    assert f.max() == len(v) - 1 and f.min() == 0


def test_the_worker_answers_through_it_never_tessellate(monkeypatch):
    """The build worker's answer is the direct read: CadQuery's slow copy isn't called (#298)."""
    from caliper import _build_worker

    shape = _get("the cargo box")
    want = tess.triangles(shape.copy(), 0.5, 0.2)

    def slow(*a, **k):
        raise AssertionError("tessellate() called")

    monkeypatch.setattr(cq.Shape, "tessellate", slow)
    v, f = _build_worker.answer(shape.copy(), 0.5, 0.2)
    assert v.dtype == np.dtype("<f8") and f.dtype == np.dtype("<i8")
    assert np.array_equal(v, want[0]) and np.array_equal(f, want[1])


def test_a_build_worker_s_mesh_is_tessellate_s():
    """Through the real worker process, a candidate is the mesh CadQuery's tessellate() makes of it."""
    from caliper.sandbox import BuildWorker

    from .test_piece_delete import TUBED

    with BuildWorker(TUBED, timeout=60) as w:
        v, f = w.build({"clip_w": 25.0})
    want = _theirs(_shape(TUBED, {"L": 400.0, "od": 50.8, "clip_w": 25.0}), 0.5, 0.2)
    assert np.array_equal(v, want[0]) and np.array_equal(f, want[1])
