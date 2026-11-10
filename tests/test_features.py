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


# --- #172 review ------------------------------------------------------------------------------------------------------
def test_an_edge_on_a_placed_part_says_where_its_script_drew_it():
    pose = [[1, 0, 0, 1000], [0, 1, 0, 0], [0, 0, 1, 500], [0, 0, 0, 1]]
    for e in features.of_solid(cq.Workplane("XY").box(40, 20, 10), pose)["edges"]:
        assert e["centre"][0] - e["local"][0] == pytest.approx(1000) and e["centre"][2] - e["local"][2] == pytest.approx(500)


def test_a_part_that_doesn_t_build_gets_a_422_in_its_own_words(store, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(store.root))
    monkeypatch.setattr(features, "for_part", lambda *a: (_ for _ in ()).throw(RuntimeError("box() got a bad width")))
    c, slug = TestClient(create_app()), os.path.basename(store.root)
    got = c.get(f"/api/designs/{slug}/parts/box/features.json")
    assert got.status_code == 422 and got.json()["detail"] == "box() got a bad width"


_CHOOSE = """
const PICK = { mode: 'face', parts: new Map(), overlay: null, turn: 0 };
const S = { scope: 'p', pick: null };
const ray = { ray: { at: 'click', clone() { return { at: this.at }; }, copy(r) { this.at = r.at; } } };
const camera = { clone: () => ({}) }, renderer = { domElement: { getBoundingClientRect: () => ({}) } };
class G { setAttribute() {} setIndex() {} }
const THREE = { BufferGeometry: G, Float32BufferAttribute: class {} };
const drawn = []; const drawPick = () => drawn.push(ray.ray.at);
function clearPick() { S.pick = null; PICK.turn += 1; }
const setScope = () => {}, renderScope = () => {}, plainly = (m) => m, pointSaid = (p) => 'point';
const hints = []; const pickHint = (t) => hints.push(t);
let finish, fail; const waits = [];
const features = () => new Promise((r, x) => waits.push({ r, x }));
const face = { id: 'f1', said: 'face: x', local: [0, 0, 0], verts: [], tris: [] };
const facePicked = () => (ray.ray.at === 'click' ? face : null), edgePicked = () => null;
const hit = { object: { userData: { partId: 'p' } }, point: { x: 0, y: 0, z: 0 } };
"""


def _pick_page(body: str) -> dict:
    import subprocess

    from .test_carve_click import _fn, _node

    src = open(JS).read()
    script = _CHOOSE + _fn(src, "choose") + f"\n(async () => {{ const out = await (async () => {{ {body} }})(); console.log(JSON.stringify(out)); }})();"
    got = subprocess.run([_node(), "-e", script], capture_output=True, text=True, timeout=30)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def test_moving_the_mouse_during_the_first_load_doesn_t_lose_the_pick():
    got = _pick_page("""const go = choose({}, hit);
        ray.ray.at = 'somewhere else';                       // the pointer moved
        waits[0].r({ faces: [face], edges: [] }); await go;
        return { pick: S.pick && S.pick.id, drawn };""")
    assert got == {"pick": "f1", "drawn": ["click"]}


def test_only_the_last_of_two_clicks_counts():
    got = _pick_page("""const a = choose({}, hit), b = choose({}, hit);
        waits[0].r({ faces: [face], edges: [] }); waits[1].r({ faces: [face], edges: [] });
        await a; await b;
        return { drawn: drawn.length };""")
    assert got == {"drawn": 1}


def test_a_pick_cleared_during_the_wait_stays_cleared():
    got = _pick_page("""const go = choose({}, hit);
        clearPick();
        waits[0].r({ faces: [face], edges: [] }); await go;
        return { pick: S.pick, drawn: drawn.length };""")
    assert got == {"pick": None, "drawn": 0}


def test_a_part_that_can_t_be_picked_says_so():
    got = _pick_page("""const go = choose({}, hit);
        waits[0].x(new Error("it won't build")); await go;
        return { hints };""")
    assert got == {"hints": ["can't pick on it: it won't build"]}


def test_the_words_are_kept_per_unit():
    from .test_carve_click import _fn

    assert "S.design.display_units" in _fn(open(JS).read(), "features")


def test_the_pick_has_its_own_chip_and_clear():
    html = open(os.path.join(os.path.dirname(JS), "index.html")).read()
    assert 'id="pickChip"' in html and 'id="pickClear"' in html and "pickbar-top" in html and ">Pick<" in html


# --- #109, slices b and c; #177 review: did it land, on real solids ----------------------------------------------------
from caliper.pick_helpers import edge_at  # noqa: E402

NS = cq.selectors.NearestToPointSelector


def _box_solid():
    return cq.Workplane("XY").box(40, 20, 10)


def _foot():
    """The bar stool in small: a foot flange with a cone on it. Its rim and the concave ring are concentric."""
    return cq.Workplane("XY").circle(30).extrude(10).union(cq.Workplane("XY").add(cq.Solid.makeCone(20, 12, 40, pnt=cq.Vector(0, 0, 10))))


def _ring(got, *, corner, z):
    return next(e for e in got["edges"] if e["type"] == "circle" and e["corner"] == corner and e["centre"][2] == pytest.approx(z))


def _outcome(solid_a, solid_b, edge, words, inches=False, kind="edge"):
    before, after = features.of_solid(solid_a), features.of_solid(solid_b)
    fid = edge(before)["id"]
    return features.landed(before, after, {"kind": kind, "id": fid, "text": words}, words, inches)


_TOP_FRONT = (0, -10, 5)
_TOP_BACK = (0, 10, 5)
_front = lambda got: next(e for e in got["edges"] if e["type"] == "line" and e["centre"] == pytest.approx(_TOP_FRONT, abs=0.01))  # noqa: E731


def _filleted(at, r):
    return _box_solid().edges(NS(at)).fillet(r)


def test_the_guide_names_edge_at_and_the_face_s_centre():
    text = open(os.path.join(os.path.dirname(features.__file__), "part_scripts.md")).read()
    assert "edge_at(result, (x, y, z)).fillet(r)" in text and 'centerOption="CenterOfMass"' in text
    assert "About this edge" in text


@pytest.mark.parametrize("solid", [_box_solid, _foot])
def test_every_edge_returns_itself(solid):
    """NearestToPointSelector measures to the centre, so concentric rings tie: the outer rim came back as the concave ring."""
    made = solid()
    shape = made.val()
    got = features.of_solid(made)
    for e, real in zip(got["edges"], shape.Edges()):
        assert edge_at(made, tuple(e["local"])).val().hashCode() == real.hashCode(), e["id"]


def test_edge_at_on_a_washer_tells_the_rings_apart():
    washer = cq.Workplane("XY").circle(30).circle(10).extrude(5)
    assert edge_at(washer, (-10, 0, 5)).val().radius() == pytest.approx(10)      # a point on the ring, not its seam's end
    assert edge_at(washer, (-30, 0, 5)).val().radius() == pytest.approx(30)


def test_edge_at_takes_a_fillet():
    filleted = edge_at(_box_solid(), _TOP_FRONT).fillet(3)
    assert abs(filleted.val().Volume() - _filleted(_TOP_FRONT, 3).val().Volume()) < 1e-6


def test_edge_at_refuses_a_point_on_no_edge():
    with pytest.raises(ValueError, match="no edge at"):
        edge_at(_box_solid(), (0, 0, 5))


def test_a_script_has_edge_at_to_hand():
    from caliper import sandbox

    script = "def build(params):\n    return edge_at(cq.Workplane('XY').box(40, 20, 10), (0, -10, 5)).fillet(3)\n"
    assert sandbox.run_script(script, {}).ok


def test_a_ring_s_point_is_on_it_and_its_centre_stays_the_centre():
    ring = _ring(features.of_solid(_foot()), corner="inside", z=10)
    assert ring["centre"][:2] == pytest.approx([0, 0], abs=0.01)
    assert (ring["local"][0] ** 2 + ring["local"][1] ** 2) ** 0.5 == pytest.approx(20, abs=0.01)


# what the issue asks: landed, on the exact edge
def test_a_true_fillet_on_the_concave_ring_lands():
    got = _outcome(_foot(), edge_at(_foot(), (-20, 0, 10)).fillet(1 / 2 * 25.4 / 3.0), lambda f: _ring(f, corner="inside", z=10), "fillet this 1/6 in")
    assert got["landed"] is True and got["said"].startswith("Checked: the fillet is on the edge you picked")


def test_a_half_inch_fillet_says_half_an_inch():
    big = cq.Workplane("XY").circle(120).extrude(30).union(cq.Workplane("XY").add(cq.Solid.makeCone(80, 40, 200, pnt=cq.Vector(0, 0, 30))))
    done = edge_at(big, (-80, 0, 30)).fillet(12.7)
    got = _outcome(big, done, lambda f: _ring(f, corner="inside", z=30), "fillet this 1/2 in", inches=True)
    assert got == {"said": "Checked: the fillet is on the edge you picked, 1/2 in.", "landed": True}


@pytest.mark.parametrize("r", [0.2, 0.3, 0.5, 3])
def test_small_fillets_land(r):
    assert _outcome(_box_solid(), _filleted(_TOP_FRONT, r), _front, "fillet this")["landed"] is True


@pytest.mark.parametrize("r", [1, 3])
def test_a_ring_between_two_cones_lands_or_can_t_be_told_never_a_miss(r):
    two = cq.Workplane("XZ").polyline([(0, 0), (40, 0), (25, 30), (40, 60), (0, 60)]).close().revolve(360, (0, 0, 0), (0, 1, 0))
    done = edge_at(two, (-25, 0, 30)).fillet(r)
    got = _outcome(two, done, lambda f: next(e for e in f["edges"] if e["type"] == "circle" and e["centre"][2] == pytest.approx(30)), "fillet this")
    assert got["landed"] is not False


# never landed
def test_nothing_done_is_a_miss_and_offers_the_way_back():
    got = _outcome(_box_solid(), _box_solid(), _front, "fillet this 3 mm")
    assert got["landed"] is False and "still there" in got["said"] and "roll it back" in got["said"]


def test_the_other_ring_filleted_is_a_miss_on_the_one_picked():
    done = edge_at(_foot(), (-30, 0, 10)).fillet(2)        # the rim, and the concave ring was picked
    got = _outcome(_foot(), done, lambda f: _ring(f, corner="inside", z=10), "fillet this 2 mm")
    assert got["landed"] is False


def test_a_neighbouring_edge_filleted_never_lands():
    done = _box_solid().edges(NS((-20, 0, 5))).fillet(3)  # shares a corner with the picked edge and trims it
    assert _outcome(_box_solid(), done, _front, "fillet this 3 mm")["landed"] is not True


def test_a_chamfer_isn_t_a_fillet():
    done = _box_solid().edges(NS(_TOP_FRONT)).chamfer(2)
    assert _outcome(_box_solid(), done, _front, "fillet this 2 mm")["landed"] is not True


def test_a_round_elsewhere_with_the_edge_chamfered_never_lands():
    done = _box_solid().edges(NS(_TOP_FRONT)).chamfer(1).edges(NS(_TOP_BACK)).fillet(3)
    assert _outcome(_box_solid(), done, _front, "fillet this 3 mm")["landed"] is not True


def test_a_round_that_isn_t_between_the_edge_s_own_faces_never_lands():
    """The picked edge chamfered, then the chamfer's top edge rounded: a new round, right there, but between other faces."""
    done = _box_solid().edges(NS(_TOP_FRONT)).chamfer(3).edges(NS((0, -7, 5))).fillet(1)
    assert _outcome(_box_solid(), done, _front, "fillet this 1 mm")["landed"] is not True


def test_the_same_line_on_a_different_face_isn_t_demonstrably_the_same_edge():
    """The picked edge's line is still there, but one of its faces has been tilted: it can't be called a miss."""
    tilted = cq.Workplane("YZ").polyline([(-10, 5), (10, 5), (10, -5), (-15, -5)]).close().extrude(20, both=True)
    got = _outcome(_box_solid(), tilted, _front, "fillet this 3 mm")
    assert got["landed"] is None


def test_a_resized_wall_isn_t_a_round():
    """An old wall that moved isn't a new surface between the picked edge's own two faces."""
    done = cq.Workplane("XY").box(40, 20, 12)
    assert _outcome(_box_solid(), done, _front, "fillet this 3 mm")["landed"] is not True


def test_can_t_tell_says_so_in_those_words_and_neither_passes_nor_fails():
    got = _outcome(_box_solid(), _box_solid().edges(NS(_TOP_FRONT)).chamfer(2), _front, "fillet this 2 mm")
    assert got == {"said": "I couldn't tell whether that landed on what you picked.", "landed": None}


def test_a_stale_pick_can_t_be_told():
    before = features.of_solid(_box_solid())
    got = features.landed({**before, "version": 3}, before, {"kind": "edge", "id": "e0", "version": 2, "text": "fillet"}, "", False)
    assert got["landed"] is None


# sizes
def test_the_wrong_size_says_both_and_doesn_t_call_it_checked():
    got = _outcome(_box_solid(), _filleted(_TOP_FRONT, 3), _front, "fillet this 4 mm")
    assert got["said"] == "The fillet is on the edge you picked, but it's 3 mm, not 4 mm." and got["landed"] is True


@pytest.mark.parametrize("text,mm", [("fillet this 1/2 in", 12.7), ("fillet this 1 1/4 in", 31.75), ("fillet 12.7 mm", 12.7), ('a 2" fillet', 50.8),
                                     ("round it 1 cm", 10.0), ("leave 20 mm of flat then fillet 3 mm", 3.0), ("a 5 mm fillet here", 5.0),
                                     ("make the fillet 3 mm: thanks", 3.0), ("fillet this", None), ("fillet this 1/0 in", None)])
def test_the_size_asked(text, mm):
    got = features._asked_mm(text)
    assert got == (pytest.approx(mm) if mm else None)


def test_a_small_round_says_a_size_a_person_can_read():
    got = _outcome(_box_solid(), _filleted(_TOP_FRONT, 0.6), _front, "fillet this", inches=True)
    assert "0 in" not in got["said"] and got["landed"] is True


# holes
def _top(f):
    return next(x for x in f["faces"] if x["type"] == "plane" and x["centre"][2] == pytest.approx(5))


def test_a_hole_through_the_picked_face_lands():
    got = _outcome(_box_solid(), _box_solid().faces(">Z").workplane().hole(10), _top, "put a hole here", kind="face")
    assert got == {"said": "Checked: there's a 10 mm hole through the face you picked.", "landed": True}


def test_a_hole_of_the_wrong_size_says_both():
    got = _outcome(_box_solid(), _box_solid().faces(">Z").workplane().hole(6), _top, "put a 10 mm hole here", kind="face")
    assert got["said"] == "There's a hole through the face you picked, but it's 6 mm, not 10 mm."


def test_a_blind_hole_from_the_other_side_isn_t_through_the_picked_face():
    done = _box_solid().faces("<Z").workplane().hole(10, 4)
    assert _outcome(_box_solid(), done, _top, "put a hole here", kind="face")["landed"] is not True


def test_a_boss_on_the_picked_face_isn_t_a_hole():
    done = _box_solid().faces(">Z").workplane().circle(5).extrude(8)
    assert _outcome(_box_solid(), done, _top, "put a hole here", kind="face")["landed"] is not True


def test_a_corner_fillet_isn_t_a_hole():
    done = _box_solid().edges("|Z").fillet(3)
    assert _outcome(_box_solid(), done, _top, "put a hole here", kind="face")["landed"] is not True


def test_a_face_left_as_it_was_is_a_miss():
    got = _outcome(_box_solid(), _box_solid(), _top, "put a hole here", kind="face")
    assert got["landed"] is False and "no new hole" in got["said"]


def test_a_hole_in_an_l_shaped_face_s_notch_isn_t_in_it():
    ell = cq.Workplane("XY").polyline([(0, 0), (40, 0), (40, 20), (20, 20), (20, 40), (0, 40)]).close().extrude(10)
    step = cq.Workplane("XY").box(20, 20, 5).translate((30, 30, 2.5))
    both = ell.union(step)                                       # the notch is filled lower: its top is a different face
    done = both.cut(cq.Workplane("XY").circle(2).extrude(5).translate((30, 30, 0)))
    got = _outcome(both, done, lambda f: next(x for x in f["faces"] if x["type"] == "plane" and x["centre"][2] == pytest.approx(10) and x["centre"][0] < 25), "put a hole here", kind="face")
    assert got["landed"] is not True


# what's asked and of what
@pytest.mark.parametrize("words", ["make it red", "chamfer this 2 mm", "remove this fillet"])
def test_what_isn_t_a_fillet_can_t_be_told(words):
    before = features.of_solid(_box_solid())
    assert features.landed(before, before, {"kind": "edge", "id": "e0", "text": words}, words, False)["landed"] is None


@pytest.mark.parametrize("before,after", [(None, {"faces": [], "edges": []}), ({"mesh": True, "faces": [], "edges": []}, {"faces": [], "edges": []})])
def test_a_part_with_no_b_rep_can_t_be_told(before, after):
    assert features.landed(before, after, {"kind": "edge", "id": "e0"}, "x: fillet 3 mm", False)["landed"] is None


def test_the_size_in_the_pick_s_own_words_isn_t_the_size_asked():
    before, after = features.of_solid(_box_solid()), features.of_solid(_filleted(_TOP_FRONT, 3))
    pick = {"kind": "edge", "id": _front(before)["id"], "text": "round it"}
    got = features.landed(before, after, pick, "About this edge: the line, 40 mm long (at x 0): round it", False)
    assert got["said"] == "Checked: the fillet is on the edge you picked, 3 mm."


# the turn
_FILLET = ("def build(params):\n    return edge_at(cq.Workplane('XY').box(40, 20, 10), {at}).fillet(3)\n")
_PLAIN = BOX


def _refine(store, script, words="fillet this 3 mm"):
    from caliper import chat

    e = _front(features.for_part(store, "box"))
    return chat.refine_part(store, "box", f"About this edge: x: {words}", author=lambda s, f, p: script, use_llm=False, max_rounds=1,
                            promote_feedback=False, pick={"kind": "edge", "id": e["id"], "text": words})


def test_a_miss_comes_first_and_the_turn_isn_t_a_success(store):
    got = _refine(store, _PLAIN)
    assert not got.ok and got.reply.startswith("✗ The edge you picked is still there")
    assert "✓ " not in got.reply.split("\n")[0]


def test_a_hit_stays_a_success(store):
    got = _refine(store, _FILLET.format(at=_TOP_FRONT))
    assert got.ok and "Checked: the fillet is on the edge you picked, 3 mm." in got.reply


def test_can_t_tell_doesn_t_fail_the_turn_or_claim_a_hit(store):
    got = _refine(store, _FILLET.format(at=_TOP_FRONT), words="make it red")
    assert got.ok and features.NOT_MEASURED in got.reply and "Checked:" not in got.reply


def _turn(store, words, script, pick, classifier=None):
    from caliper import chat

    return chat.turn(store, words, scope="box", author=lambda s, f, p: script, use_llm=False, max_rounds=1,
                     promote_feedback=False, pick=pick)


def test_a_miss_doesn_t_block_trying_again(store):
    from caliper import awaiting

    words = "fillet this edge 3 mm"
    e = _front(features.for_part(store, "box"))
    _turn(store, words, _PLAIN, {"kind": "edge", "id": e["id"], "text": words})
    version = store.design.part("box").version
    e2 = _front(features.for_part(store, "box"))
    again = _turn(store, words, _FILLET.format(at=_TOP_FRONT), {"kind": "edge", "id": e2["id"], "text": words})
    assert "already did that" not in again.reply and awaiting.pending(store) is None
    assert again.action == "refine" and store.design.part("box").version == version + 1
    assert "Checked: the fillet is on the edge you picked" in again.reply


def test_a_parked_repeat_keeps_the_pick_and_yes_runs_the_same_check(store):
    from caliper import awaiting, chat

    words = "fillet this edge 3 mm"
    e = _front(features.for_part(store, "box"))
    first = _turn(store, words, _FILLET.format(at=_TOP_FRONT), {"kind": "edge", "id": e["id"], "text": words})
    assert first.ok
    e2 = _front(features.for_part(store, "box")) if False else None
    pick = {"kind": "edge", "id": "e0", "text": words}
    asked = _turn(store, words, _PLAIN, pick)
    assert "already did that" in asked.reply and awaiting.pending(store)["pick"] == pick
    yes = chat.turn(store, "yes", use_llm=False, author=lambda s, f, p: _PLAIN, max_rounds=1, promote_feedback=False)
    assert yes.action == "refine" and ("edge you picked" in yes.reply or features.NOT_MEASURED in yes.reply) and e2 is None


def test_the_page_sends_the_pick_with_the_message():
    src = open(JS).read()
    assert "send(said, S.scope, pick);" in src and "...(pick ? { pick } : {})" in src and "version: (S.design.parts.find" in src
