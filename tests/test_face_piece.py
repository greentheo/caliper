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
    assert features.SCHEMA == 4


def test_376_s_pick_writes_the_face_s_words_as_they_come():
    """#376's Pick on the model writes "Picked <the face's words, less "face: ">", so its rows name the piece now."""
    from .test_carve_click import JS, _fn

    pick = _fn(open(JS).read(), "pickScenarioFace")
    assert "String(f.said || 'that face').replace(/^face: /, '')" in pick and "stopScenPick(`Picked ${what}`);" in pick
