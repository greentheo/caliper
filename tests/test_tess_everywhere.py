"""#298, slice 2: every mesh the app reads is read straight off OCC, and is tessellate()'s, element for element.

#340 moved the drag study's build worker onto ``caliper.tess.triangles``. The app's other meshes went through CadQuery's
slow copy still: ``measure._cadquery_to_trimesh`` (every build, so every check), ``pieces._meshed`` and each face of
``features.of_solid``. Each reads through the helper now. Each is pinned against CadQuery's own ``tessellate()``, called
here with the arguments the app used, at the app's 0.05 mm, on the repo's fixtures: the same mesh, the same faces, so
every check reads the same."""

import numpy as np
import pytest

cq = pytest.importorskip("cadquery")

from caliper import features, measure, pieces  # noqa: E402

from .test_tess import _get, _theirs  # noqa: E402

NAMES = ["the cargo box", "the step stool", "a plate with a tube and a clip", "a holed panel", "a bar stool"]


def _was_measure(wp):
    """main's ``_cadquery_to_trimesh``, as it was: ``solid.tessellate(0.05)`` (its angle 0.1), then cleaned."""
    import trimesh

    solid = wp.val() if hasattr(wp, "val") else wp
    v, f = _theirs(solid, 0.05, 0.1)
    return measure.clean(trimesh.Trimesh(vertices=v, faces=f, process=True))


@pytest.fixture
def never(monkeypatch):
    """CadQuery's slow copy, refused."""
    def refused(*a, **k):
        raise AssertionError("tessellate() called")
    monkeypatch.setattr(cq.Shape, "tessellate", refused)


@pytest.mark.parametrize("name", NAMES)
def test_every_build_s_mesh_is_tessellate_s_at_0_05(name):
    """measure's mesh of a build: what every check reads (its volume, its bounds, its FEA's voxels)."""
    new, old = measure._cadquery_to_trimesh(_get(name).copy()), _was_measure(_get(name).copy())
    assert np.array_equal(new.vertices, old.vertices) and np.array_equal(new.faces, old.faces)
    assert len(new.faces) > 0


def test_a_workplane_s_mesh_is_its_first_solid_s_as_before():
    wp = cq.Workplane().box(30, 20, 10).faces(">Z").workplane().hole(6)
    new, old = measure._cadquery_to_trimesh(wp), _was_measure(wp)
    assert np.array_equal(new.vertices, old.vertices) and np.array_equal(new.faces, old.faces)


@pytest.mark.parametrize("name", ["a plate with a tube and a clip", "a holed panel"])
def test_a_pieces_difference_is_meshed_as_before(name):
    """main's ``_meshed``: ``shape.tessellate(0.05, 0.1)``."""
    new, (v, f) = pieces._meshed(_get(name).copy()), _theirs(_get(name).copy(), 0.05, 0.1)
    import trimesh

    old = trimesh.Trimesh(v, f)
    assert np.array_equal(new.vertices, old.vertices) and np.array_equal(new.faces, old.faces)


def _faces_as_before(shape, pose=None):
    """Each face's points and triangles as main had them: ``face.tessellate(LINEAR, ANGULAR)``, placed by ``pose``."""
    out = []
    for f in shape.Faces():
        v, t = _theirs(f, features.LINEAR, features.ANGULAR)
        pts = np.array([features._apply(pose, p) for p in v], float)
        out.append(([round(float(x), 2) for x in pts.ravel()], [int(x) for x in t.ravel()]))
    return out


@pytest.mark.parametrize("name", NAMES)
def test_the_page_s_faces_are_as_before(name):
    """features.of_solid: each face's triangles, for picking on the page."""
    shape = _get(name)
    got = features.of_solid(shape.copy())
    assert [(f["verts"], f["tris"]) for f in got["faces"]] == _faces_as_before(shape.copy())
    assert all(f["tris"] for f in got["faces"])


def test_the_page_s_faces_placed_by_a_pose_are_as_before():
    pose = np.eye(4)
    pose[:3, 3] = [100.0, -20.0, 5.0]
    shape = _get("a holed panel")
    got = features.of_solid(shape.copy(), pose)
    assert [(f["verts"], f["tris"]) for f in got["faces"]] == _faces_as_before(shape.copy(), pose)


def test_a_hole_s_wall_is_hollow_and_a_post_s_isn_t():
    """features reads which way a cylinder faces from one of its own points: a hole's wall faces its axis."""
    wp = (cq.Workplane().box(60, 40, 10).faces(">Z").workplane().hole(12)
          .faces(">Z").workplane().center(20, 0).circle(4).extrude(15))
    got = {f["radius"]: f["hollow"] for f in features.of_solid(wp)["faces"] if f["type"] == "cylinder"}
    assert got == {6.0: True, 4.0: False}


def test_a_build_s_mesh_never_calls_tessellate(never):
    m = measure._cadquery_to_trimesh(cq.Workplane().box(30, 20, 10))
    assert m.is_watertight and abs(m.volume - 6000) < 1e-6


def test_a_pieces_difference_never_calls_tessellate(never):
    assert abs(pieces._meshed(cq.Workplane().box(10, 10, 10).val()).volume - 1000) < 1e-6


def test_the_page_s_faces_never_call_tessellate(never):
    got = features.of_solid(cq.Workplane().box(10, 10, 10))
    assert len(got["faces"]) == 6 and all(len(f["tris"]) == 6 for f in got["faces"])     # 2 triangles a face


def test_nothing_in_the_app_calls_tessellate_any_more():
    """Every mesh is read through the helper: a new one that calls tessellate() is caught here."""
    import pathlib
    import re

    from caliper import tess

    src = pathlib.Path(tess.__file__).parent
    calls = [f"{p.name}:{n}" for p in src.rglob("*.py") if p.name != "tess.py"      # it says what it matches
             for n, line in enumerate(p.read_text().splitlines(), 1)
             if re.search(r"\.tessellate\(", line) and not line.lstrip().startswith("#")]
    assert calls == []
