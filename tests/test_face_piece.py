"""CALI-230 (the #376 follow-up): a picked face says which piece it's on, and which way it faces.

#376's Pick on the model wrote "Picked the flat face, 1.8 in up" on step-stool-5's tread: what kind of face and how high,
never whose. A face on one piece is now that piece's, by the name the tree shows it by (`tree.pieces`, the person's label
else its key): "face: the tread's top face, 400 mm up". A level flat face is its top or its underside, as the part is placed.
Synthetic parts, never Theo's."""
import os

import numpy as np
import pytest

from caliper import features, joints

pytest.importorskip("cadquery")

T, H, W, D = 19.05, 400.0, 400.0, 300.0

#: A tread on a side, the side's top edge under the tread; and, where SECOND, another side at the far end.
STOOL = '''import cadquery as cq

PARAMS = {"t": 19.05, "w": 400.0, "d": 300.0, "h": 400.0}


def build(params):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    tread = cq.Workplane().box(w, d, t, centered=False).translate((0, 0, h - t))
    side = cq.Workplane().box(t, d, h - t, centered=False)
    out = tread.union(side)
    SECOND_BUILD
    return out


def construction(params, build=None):
    p = {**PARAMS, **(params or {})}
    t, w, d, h = p["t"], p["w"], p["d"], p["h"]
    return [{"name": "side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, 0), (0, d, 0), (0, d, h - t), (0, 0, h - t)]},
            {"name": "tread", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]}SECOND_DECL]
'''
SECOND = {"SECOND_BUILD": "out = out.union(cq.Workplane().box(t, d, h - t, centered=False).translate((w - t, 0, 0)))",
          "SECOND_DECL": ''',
            {"name": "side", "kind": "sheet", "material": "plywood", "thickness": t,
             "outline": [(w - t, 0, 0), (w - t, d, 0), (w - t, d, h - t), (w - t, 0, h - t)]}'''}


def _store(tmp_path, second=False):
    from caliper.design import DesignStore

    script = STOOL
    for k, v in SECOND.items():
        script = script.replace(k, v if second else "")
    s = DesignStore.create("a stool", base=str(tmp_path / "designs"))
    s.write_part("stool", script, intent="a tread on a side")
    return s


def _faces(s):
    got = features.with_words(features.for_part(s, "stool"), False, piece=joints.piece_namer(s, "stool"))
    return got["faces"]


def _at(faces, point):
    """The face whose centre is nearest ``point`` (the script's frame)."""
    return min(faces, key=lambda f: np.linalg.norm(np.asarray(f["local"]) - point))


def test_a_point_is_on_the_piece_whose_surface_it_s_on(tmp_path):
    name = joints.piece_namer(_store(tmp_path), "stool")
    assert name((W / 2, D / 2, H)) == "tread"                     # the tread's top
    assert name((0, D / 2, 100.0)) == "side"                      # the side's outer face
    assert name((T, D / 2, H - T)) is None                        # the inside corner: on both as near, no one piece
    assert name((W / 2, D / 2, 100.0)) is None                    # in the air under the tread


def test_the_tread_s_top_and_underside_and_the_side_s_face(tmp_path):
    faces = _faces(_store(tmp_path))
    assert _at(faces, (W / 2, D / 2, H))["said"] == "face: the tread's top face, 400 mm up"
    assert _at(faces, ((W + T) / 2, D / 2, H - T))["said"] == "face: the tread's underside, 381 mm up"
    side = _at(faces, (0, D / 2, (H - T) / 2))
    assert side["said"].startswith("face: the side's flat face, ")


def test_a_piece_is_said_by_the_name_the_person_gave_it_and_a_second_side_by_its_own(tmp_path):
    """The tree keys a second "side" "side 2" and the joints "side #2": the label given to "side 2" is the one said."""
    from caliper import tree

    s = _store(tmp_path, second=True)
    tree.set_label(s, "stool", "Step", piece="tread")
    tree.set_label(s, "stool", "right leg", piece="side 2")
    faces = _faces(s)
    assert _at(faces, (W / 2, D / 2, H))["said"] == "face: the Step's top face, 400 mm up"
    assert _at(faces, (W, D / 2, (H - T) / 2))["said"].startswith("face: the right leg's flat face, ")
    assert _at(faces, (0, D / 2, (H - T) / 2))["said"].startswith("face: the side's flat face, ")


def test_a_part_with_no_pieces_says_its_faces_as_before_with_its_top_and_underside(tmp_path):
    from caliper.design import DesignStore

    from .test_features import BOX

    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    s.write_part("box", BOX, intent="a box")
    words = sorted(f["said"].split(",")[0] for f in _faces_of(s, "box"))
    assert words.count("face: the top face") == 1 and words.count("face: the underside") == 1
    assert words.count("face: the flat face") == 4


def _faces_of(s, pid):
    return features.with_words(features.for_part(s, pid), False, piece=joints.piece_namer(s, pid))["faces"]


def test_top_and_underside_go_by_how_it_s_placed():
    """Turned over (180° about x), what was its top faces down."""
    import cadquery as cq

    from caliper import measure

    box = cq.Workplane().box(100, 50, 10, centered=False)
    up = features.of_solid(box)
    over = features.of_solid(box, measure.pose_matrix([0, 0, 0], [180, 0, 0]))
    top = next(f for f in up["faces"] if f["normal"][2] > 0.98)
    turned = next(f for f in over["faces"] if f["id"] == top["id"])
    assert turned["normal"][2] < -0.98
    assert features.said(over, "face", top["id"], False).startswith("face: the underside")


def test_a_picked_point_is_on_the_face_even_where_its_centre_isn_t():
    """A ring's centre is in its hole: the point the piece is found at is one of its own triangles'."""
    import cadquery as cq

    ring = cq.Workplane().circle(50).circle(30).extrude(10)
    flat = [f for f in features.of_solid(ring)["faces"] if f["type"] == "plane"]
    for f in flat:
        r = np.hypot(f["inside"][0], f["inside"][1])
        assert 30 - 0.5 <= r <= 50 + 0.5, f["inside"]


def test_the_app_s_pick_chip_names_the_piece(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    s = _store(tmp_path)
    monkeypatch.setenv("CALIPER_DESIGNS", os.path.dirname(s.root))
    got = TestClient(create_app()).get(f"/api/designs/{os.path.basename(s.root)}/parts/stool/features.json").json()
    assert _at(got["faces"], (W / 2, D / 2, H))["said"] == "face: the tread's top face, 400 mm up"


def test_an_older_features_file_is_worked_out_again():
    assert features.SCHEMA == 5                            # 5: the points a fused face is named over (#402 review)


def test_376_s_pick_writes_the_face_s_words_as_they_come():
    """#376's Pick on the model writes "Picked <the face's words, less "face: ">", so its rows name the piece now."""
    from .test_carve_click import JS, _fn

    pick = _fn(open(JS).read(), "pickScenarioFace")
    assert "String(f.said || 'that face').replace(/^face: /, '')" in pick and "stopScenPick(`Picked ${what}`);" in pick


# --- #402 review (reviewer-2) ------------------------------------------------------------------------------------------------
def _front(tmp_path):
    return _at(_faces(_store(tmp_path)), (W / 4, 0, H / 2))


def test_the_fused_front_names_both_pieces_biggest_first(tmp_path):
    """The union fuses coplanar faces: the front (y = 0, z 0–400) is an L of the tread's front (400 x 19) and the side's
    front edge (19 x 381), about equal. It read "the tread's flat face" wherever it was clicked; now it says both."""
    f = _front(tmp_path)
    assert f["said"].startswith("face: the flat face across the tread and the side, "), f["said"]


def test_the_end_is_the_side_s_its_tread_sliver_under_the_share(tmp_path):
    """The x = 0 end: the side's outer face (300 x 381) and the tread's left end (300 x 19), under 5% of it."""
    f = _at(_faces(_store(tmp_path)), (0, D / 2, (H - T) / 2))
    assert f["said"].startswith("face: the side's flat face, "), f["said"]


def test_a_moved_and_turned_part_s_face_is_named_as_it_sits(tmp_path):
    """reviewer-2: no fixture was posed. Moved (300, 0, 0) and turned 90° about z, the tread's top is still the tread's top
    face (its pieces are found in its own frame, its top and height as it sits)."""
    s = _store(tmp_path)
    part = next(p for p in s.assembly.parts if p.id == "stool")
    part.position, part.rotation = [300.0, 0.0, 50.0], [0.0, 0.0, 90.0]
    s.save()
    from caliper.design import DesignStore

    s = DesignStore.load(s.root)
    faces = _faces(s)
    top = _at(faces, (W / 2, D / 2, H))                                  # found by its own-frame centre
    assert top["said"] == "face: the tread's top face, 450 mm up", top["said"]
    assert _at(faces, (W / 2, D / 2, H - T))["said"].startswith("face: the tread's underside, 431 mm up")


def test_a_sloped_face_is_never_its_top():
    """reviewer-2: nothing checked that a 30° slope isn't "the top face" (LEVEL, about 11°)."""
    import cadquery as cq

    wedge = cq.Workplane("XZ").polyline([(0, 0), (100, 0), (100, 57.7), (0, 0)]).close().extrude(-50)   # a 30° slope
    got = features.of_solid(wedge)
    slope = next(f for f in got["faces"] if f["type"] == "plane" and 0.5 < f["normal"][2] < 0.98)
    assert features.said(got, "face", slope["id"], False).startswith("face: the flat face, ")


def _named(weights):
    """A plane face whose samples a fake namer puts on pieces by their x: 0 is the tread, 1 the side, 2 a seam (None)."""
    who = {0: "tread", 1: "side", 2: None}
    samples = [[k, 0, 0, w] for k, w in weights.items() for _ in range(1)]
    face = {"id": "f0", "type": "plane", "centre": [0, 0, 100], "normal": [0, 1, 0], "samples": samples}
    got = features.with_words({"faces": [face], "edges": []}, False, piece=lambda p: who[int(p[0])])
    return got["faces"][0]["said"]


@pytest.mark.parametrize("weights,want", [
    ({0: 90, 1: 10}, "face: the tread's flat face, 100 mm up"),               # a 10% sliver of the side: not named
    ({0: 50, 1: 50}, "face: the flat face across the tread and the side, 100 mm up"),
    ({0: 30, 1: 70}, "face: the flat face across the side and the tread, 100 mm up"),   # the bigger share first
    ({0: 10, 2: 80, 1: 10}, "face: the flat face across the tread and the side, 100 mm up"),   # a seam counts for neither
    ({2: 100}, "face: the flat face, 100 mm up")])                            # all seam: no one piece's
def test_a_face_is_each_piece_s_that_holds_a_share_of_it(weights, want):
    assert _named(weights) == want


def test_a_face_is_sampled_four_points_over_each_of_its_biggest_triangles():
    import cadquery as cq

    got = features.of_solid(cq.Workplane().box(100, 50, 10))
    for f in got["faces"]:
        n = len(f["tris"]) // 3
        assert len(f["samples"]) == 4 * min(features.SAMPLED, n) and all(len(x) == 4 for x in f["samples"])
