"""CALI-109 (#109, slice a) — a part's faces and edges, with ids, so a click can say exactly which. Stubbed: no Claude."""

import json
import os

import pytest

from caliper import features
from caliper.design import DesignStore

cq = pytest.importorskip("cadquery")


def _box():
    return cq.Workplane("XY").box(40, 20, 10)


def _edge(got, **want):
    return [e for e in got["edges"] if all(e.get(k) == v for k, v in want.items())]


def test_a_box_has_six_flat_faces_and_twelve_straight_edges():
    got = features.of_solid(_box())
    assert len(got["faces"]) == 6 and {f["type"] for f in got["faces"]} == {"plane"}
    assert len(got["edges"]) == 12 and {e["type"] for e in got["edges"]} == {"line"}
    assert len({f["id"] for f in got["faces"]}) == 6 and len({e["id"] for e in got["edges"]}) == 12


def test_every_edge_of_a_box_is_between_two_faces_and_is_an_outside_corner():
    got = features.of_solid(_box())
    ids = {f["id"] for f in got["faces"]}
    for e in got["edges"]:
        assert len(e["faces"]) == 2 and set(e["faces"]) <= ids and e["faces"][0] != e["faces"][1]
        assert e["corner"] == "outside", e


def test_each_face_is_its_own_group_of_triangles():
    got = features.of_solid(_box())
    area = 0.0
    for f in got["faces"]:
        v = f["verts"]
        assert len(v) % 3 == 0 and len(f["tris"]) % 3 == 0 and max(f["tris"]) < len(v) / 3
        area += f["area"]
    assert area == pytest.approx(2 * (40 * 20 + 40 * 10 + 20 * 10), rel=1e-3)


def test_a_cylinder_says_its_radius_and_axis():
    got = features.of_solid(cq.Workplane("XY").circle(15).extrude(30))
    (side,) = [f for f in got["faces"] if f["type"] == "cylinder"]
    assert side["radius"] == pytest.approx(15) and [abs(x) for x in side["axis"]] == [0, 0, 1]
    rims = _edge(got, type="circle")
    assert len(rims) == 2 and all(e["radius"] == pytest.approx(15) and e["corner"] == "outside" for e in rims)
    assert sorted(e["centre"][2] for e in rims) == [0, 30]


def test_a_step_has_an_inside_corner():
    """The bar stool's cone-and-flange edge: the one Theo wanted to pick."""
    solid = cq.Workplane("XY").box(40, 40, 10, centered=(True, True, False)).faces(">Z").workplane().rect(20, 20).extrude(20)
    got = features.of_solid(solid)
    inside = _edge(got, corner="inside")
    assert len(inside) == 4 and all(e["centre"][2] == pytest.approx(10) and e["length"] == pytest.approx(20) for e in inside)
    assert len(_edge(got, corner="outside")) == 20


def test_a_hole_s_rim_is_an_outside_corner_and_its_wall_a_cylinder():
    solid = cq.Workplane("XY").box(40, 40, 10).faces(">Z").workplane().hole(10)
    got = features.of_solid(solid)
    (wall,) = [f for f in got["faces"] if f["type"] == "cylinder"]
    assert wall["radius"] == pytest.approx(5)
    rims = _edge(got, type="circle")
    assert len(rims) == 2 and {e["corner"] for e in rims} == {"outside"}


def test_a_seam_is_not_called_a_corner():
    got = features.of_solid(cq.Workplane("XY").circle(15).extrude(30))
    (seam,) = _edge(got, type="line")
    assert seam["corner"] is None


def test_a_cone_is_a_cone():
    solid = cq.Workplane("XY").add(cq.Solid.makeCone(20, 10, 30))
    got = features.of_solid(solid)
    assert "cone" in {f["type"] for f in got["faces"]}


def test_a_placed_part_is_given_where_it_sits_and_where_its_script_drew_it():
    pose = [[1, 0, 0, 1000], [0, 1, 0, 0], [0, 0, 1, 500], [0, 0, 0, 1]]
    got = features.of_solid(cq.Workplane("XY").box(40, 20, 10), pose)
    (top,) = [f for f in got["faces"] if f["local"][2] == pytest.approx(5)]
    assert top["centre"][0] == pytest.approx(1000) and top["centre"][2] == pytest.approx(505)
    assert top["verts"][2] == pytest.approx(505, abs=0.01)
    e = got["edges"][0]
    assert e["points"][0][2] > 400


# --- for a part in a design ------------------------------------------------------------------------------------------
BOX = """import cadquery as cq

def build(params):
    return cq.Workplane('XY').box(40, 20, 10)
"""


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    s.write_part("box", BOX, intent="a box")
    return s


def test_a_part_s_features_are_kept_per_version(store):
    first = features.for_part(store, "box")
    assert first["version"] == 1 and len(first["faces"]) == 6 and not first["mesh"]
    path = os.path.join(store.root, "parts", "box", "features-v1.json")
    assert json.load(open(path))["version"] == 1
    store.write_part("box", BOX.replace("40", "50"), intent="a box")
    second = features.for_part(store, "box")
    assert second["version"] == 2 and not os.path.exists(path)
    assert os.path.exists(os.path.join(store.root, "parts", "box", "features-v2.json"))


def test_kept_features_aren_t_worked_out_again(store, monkeypatch):
    features.for_part(store, "box")
    monkeypatch.setattr(features, "of_solid", lambda *a, **k: pytest.fail("worked out again"))
    assert len(features.for_part(store, "box")["edges"]) == 12


def test_moving_a_part_works_them_out_again(store):
    features.for_part(store, "box")
    next(p for p in store.assembly.parts if p.id == "box").position = (0.0, 0.0, 500.0)
    store.save()
    got = features.for_part(store, "box")
    assert max(f["centre"][2] for f in got["faces"]) == pytest.approx(505)


def test_a_part_with_no_b_rep_is_a_mesh(store, monkeypatch):
    class G:
        solid = None

    monkeypatch.setattr(store, "part_geometry", lambda pid: G())
    assert features.for_part(store, "box")["mesh"] is True


def test_an_unknown_part_is_a_key_error(store):
    with pytest.raises(KeyError):
        features.for_part(store, "nothing")


def test_the_route_serves_them_or_says_it_has_no_such_part(store, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(store.root))
    c, slug = TestClient(create_app()), os.path.basename(store.root)
    got = c.get(f"/api/designs/{slug}/parts/box/features.json")
    assert got.status_code == 200 and len(got.json()["faces"]) == 6
    assert c.get(f"/api/designs/{slug}/parts/nope/features.json").status_code == 404


# --- what a pick is called ---------------------------------------------------------------------------------------------
_STEP = {"faces": [{"id": "f0", "type": "cone", "centre": [0, 0, 300]}, {"id": "f1", "type": "plane", "centre": [0, 0, 14]},
                   {"id": "f2", "type": "cylinder", "radius": 228.6, "centre": [0, 0, 7]}],
         "edges": [{"id": "e0", "type": "circle", "radius": 228.6, "centre": [0, 0, 14], "length": 1436,
                    "faces": ["f0", "f1"], "corner": "inside"},
                   {"id": "e1", "type": "line", "centre": [0, 0, 25.4], "length": 50.8, "faces": ["f1", "f1"], "corner": None}]}


def test_an_edge_is_said_in_inches():
    assert features.said(_STEP, "edge", "e0", True) == \
        "edge: the circle where the cone meets the flat face, 18 in across, 0.6 in up (inside corner)"


def test_an_edge_is_said_in_mm():
    assert features.said(_STEP, "edge", "e0", False) == \
        "edge: the circle where the cone meets the flat face, 457 mm across, 14 mm up (inside corner)"


def test_a_straight_edge_says_how_long():
    assert features.said(_STEP, "edge", "e1", False) == "edge: the line between two flat faces, 51 mm long, 25 mm up"


def test_a_face_is_said():
    assert features.said(_STEP, "face", "f2", True) == "face: the cylinder 18 in across, 0.3 in up"
    assert features.said(_STEP, "face", "f1", False) == "face: the flat face, 14 mm up"


def test_an_id_it_hasn_t_got_is_none():
    assert features.said(_STEP, "face", "f9", True) is None and features.said(_STEP, "edge", "e9", True) is None


def test_the_route_says_each_in_the_person_s_units(store, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(store.root))
    c, slug = TestClient(create_app()), os.path.basename(store.root)
    got = c.get(f"/api/designs/{slug}/parts/box/features.json").json()
    assert all(f["said"].startswith("face: the flat face") for f in got["faces"])
    assert all(e["said"].startswith("edge: the line between two flat faces") for e in got["edges"])


# --- the page ---------------------------------------------------------------------------------------------------------
JS = os.path.join(os.path.dirname(__file__), "..", "src", "caliper", "web", "static", "design.js")


def _page(body: str) -> dict:
    import subprocess

    from .test_carve_click import _fn, _node

    src = open(JS).read()
    head = "const IN = 25.4;\nconst inches = () => false;\nconst len = (mm, d) => `${mm.toFixed(d)} mm`;\n"
    script = head + "\n".join(_fn(src, n) for n in ("faceOfTriangle", "nearestEdge", "aboutPick")) \
        + "const pointSaid = (p) => `point: ${p[0]}`;\n" + f"const out = (() => {{ {body} }})();\nconsole.log(JSON.stringify(out));"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


@pytest.mark.parametrize("tri,face", [(0, 0), (1, 0), (2, 1), (4, 1), (5, 2), (99, 2)])
def test_a_triangle_is_the_face_it_was_drawn_with(tri, face):
    assert _page(f"return {{ f: faceOfTriangle([0, 2, 5], {tri}) }};") == {"f": face}


_EDGES = """const project = (p) => ({ x: p[0], y: p[1], d: p[2] });
const edges = [{ id: 'near', points: [[0, 0, 10], [100, 0, 10]] }, { id: 'far', points: [[0, 5, 500], [100, 5, 500]] },
               { id: 'other', points: [[0, 50, 10], [100, 50, 10]] }];"""


def test_the_nearest_edge_on_screen_is_picked():
    got = _page(_EDGES + "return { a: nearestEdge(edges, project, { x: 50, y: 2 }, 12, 600).id, b: nearestEdge(edges, project, { x: 50, y: 49 }, 12, 600).id };")
    assert got == {"a": "near", "b": "other"}


def test_an_edge_behind_the_part_is_not_picked():
    got = _page(_EDGES + "return { e: nearestEdge(edges, project, { x: 50, y: 5 }, 12, 100).id };")
    assert got == {"e": "near"}


def test_a_click_far_from_any_edge_picks_none():
    assert _page(_EDGES + "return { e: nearestEdge(edges, project, { x: 50, y: 30 }, 12, 600) };") == {"e": None}


def test_the_designer_is_told_what_was_picked_and_where():
    got = _page("return { t: aboutPick({ said: 'edge: the circle', local: [1, 2, 3.5] }, 'fillet this 1/2 in') };")
    assert got["t"] == "About this edge: the circle (at x 1, y 2, z 3.5 mm in the script's coordinates): fillet this 1/2 in"


def test_a_point_on_a_mesh_is_said_without_script_coordinates():
    got = _page("return { t: aboutPick({ said: 'point on the surface: x 1 mm', local: null }, 'thicken it') };")
    assert got["t"] == "About this point on the surface: x 1 mm: thicken it"


def test_nothing_picked_leaves_the_message_alone():
    assert _page("return { t: aboutPick(null, 'make it taller') };") == {"t": "make it taller"}
