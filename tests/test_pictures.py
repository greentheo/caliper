"""CALI-78 (#46) — a picture on it: a T-rex cut out of the side, and it still holds Dad."""

import time

import numpy as np
import pytest

from caliper import chat, holes, lighten, load_study, pictures
from caliper.design import DesignStore

from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")


def test_a_t_rex_is_built_in_and_anything_else_needs_claude_or_a_drawing():
    rex = pictures.draw("a T-rex", use_llm=False)
    x0, y0, x1, y1 = rex.bounds
    assert (x0, y0) == pytest.approx((0, 0)) and max(x1, y1) == pytest.approx(1.0) and rex.is_valid
    with pytest.raises(ValueError, match="draw it on the pad"):
        pictures.draw("a giraffe", use_llm=False)
    # anything else, Claude puts together from simple shapes, joined into one silhouette
    class Fake:
        class messages:  # noqa: N801 — the Anthropic client's shape
            @staticmethod
            def create(**kw):
                body = ('{"shapes": [{"ellipse": [50, 40, 30, 18, 0]}, {"stroke": [[25, 30], [20, 0]], "width": 8},'
                        ' {"stroke": [[75, 30], [80, 0]], "width": 8}, {"polygon": [[78, 45], [100, 70], [90, 40]]}]}')
                return type("M", (), {"content": [type("B", (), {"type": "text", "text": body})]})

    g = pictures.draw("a giraffe", client=Fake)
    assert g.geom_type == "Polygon" and g.is_valid and g.bounds[1] == pytest.approx(0, abs=1e-6)
    # a drawing comes from the screen, y down: a square drawn clockwise on screen is a square
    sq = pictures.from_drawing([(0, 0), (50, 0), (100, 0), (100, 50), (100, 100), (50, 100), (0, 100), (0, 50)])
    assert sq.area == pytest.approx(1.0)
    with pytest.raises(ValueError, match="all the way round"):
        pictures.from_drawing([(0, 0), (1, 1)])


def test_what_a_jigsaw_cant_follow_is_smoothed_out_and_islands_dropped():
    from shapely.geometry import Polygon, box

    body = box(0, 0, 100, 60)
    spike = box(100, 28, 160, 30)                     # 2 mm wide: no blade gets round that
    slot = box(40, 0, 41, 40)                         # a 1 mm gap: no blade gets into that
    eye = box(70, 40, 80, 50)                         # would fall out
    shape = Polygon(body.union(spike).difference(slot).exterior, [eye.exterior.coords])
    got = pictures.cuttable(shape)
    assert got.bounds[2] < 105 and not got.interiors           # the spike is gone (its root rounded), the eye too
    assert got.contains(box(39, 1, 42, 39))                     # the slot closed up
    assert got.area == pytest.approx(6000, rel=0.02)


@pytest.fixture
def stool(tmp_path, monkeypatch):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)        # coarse: quick, and it still has a verdict
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    return store


def test_it_goes_on_a_panel_nobody_stands_on_upright_as_you_look_at_it(stool):
    found = {p["name"]: p for p in pictures.panels(stool, "stool")}
    assert set(found) == {"left", "right", "front", "back"}            # not the top: it's stood on
    assert pictures.choose(list(found.values()))["name"] == "front"
    assert pictures.choose(list(found.values()), "on the side")["name"] in ("left", "right")
    assert pictures.choose(list(found.values()), "the back")["name"] == "back"
    for p in found.values():
        up3 = p["up"][0] * p["u"] + p["up"][1] * p["v"]
        right3 = p["right"][0] * p["u"] + p["right"][1] * p["v"]
        assert up3 == pytest.approx([0, 0, 1], abs=1e-6)
        # right x up points out of the box, at whoever is looking at it
        assert np.cross(right3, up3) @ -p["inward"] == pytest.approx(1.0)


def test_a_t_rex_on_the_side_is_cut_and_it_still_holds(stool):
    heard = []
    got = pictures.put(stool, "stool", pictures.draw("T-rex", use_llm=False), subject="T-rex", where="the side",
                       emit=lambda k, t="", **d: heard.append(d.get("step")))
    assert got["ok"] and got["panel"] in ("left", "right") and got["version"] == 2
    assert heard == ["fit", "check", "cut", "recheck"]
    assert got["verdict"]["kind"] == "holds" and got["safety"] >= got["min_safety"] and got["predicted"] is not None
    w, h = got["size_in"]
    assert 3 < w < 7.5 and 3 < h < 6.5                                  # inside the side's rim (10 x 9 in, 1 1/2 in rim)
    assert got["reply"].startswith("✓ I cut a T-rex") and "still holds" in got["reply"]
    (entry,) = holes.read(stool.read_script("stool"))
    assert entry["picture"] == "T-rex" and entry["piece"] == got["panel"]
    # the rebuilt part has it: lighter by the picture, and its strength check is on this version
    assert load_study.list_runs(stool, "stool")[0]["version"] == 2
    from caliper import construction as C

    rows = {r["name"]: r for r in C.takeoff(C.declared(stool, "stool")["construction"])}
    assert rows[got["panel"]]["holes"] == 1
    # its edge is judged at KT_HOLE times the wall's stress there, and no case reads stronger than that (#64 item 5)
    for c in load_study.list_runs(stool, "stool")[0]["cases"]:
        pe = c.get("picture_edge")
        assert pe and pe["piece"] == got["panel"] and pe["kt"] == lighten.KT_HOLE, c
        assert pe["safety"] is None or c["safety"] <= pe["safety"] + 0.01, c


def test_lightening_leaves_a_picture_alone(stool):
    got = pictures.put(stool, "stool", pictures.draw("T-rex", use_llm=False), subject="T-rex", where="front")
    rec = lighten.study(stool, "stool", steps=(1.0,))
    walls = [s for s in rec["stations"] if s["phase"] == "walls" and s["removed"] > 0 and not s.get("estimate")]
    assert walls
    # adopting a step keeps the picture as it was and adds the lightening holes beside it
    lighten.adopt(stool, rec["id"], walls[-1]["index"])
    after = holes.read(stool.read_script("stool"))
    pics = [h for h in after if h.get("picture")]
    assert len(pics) == 1 and pics[0]["piece"] == got["panel"]
    assert any(not h.get("picture") for h in after)
    # and a web of wood between them (#50, a surviving mutant, #72): without it a hole cut into the T-rex, 0.0 mm apart
    # (measured 35.2 mm at 9.53 mm voxels: the web, less the grid's rounding, which is under a voxel)
    gap = _gap_to_picture(after, got["panel"])
    assert gap >= lighten.MIN_WEB_MM - rec["spacing_mm"], (gap, rec["spacing_mm"])


def _gap_to_picture(entries, panel):
    """The least gap, in the panel's plane, between its picture and any lightening hole on it (both holes' outlines)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    def flat(entry):
        pts = [np.asarray(p, float) for p in entry["polygons"]]
        drop = int(np.argmax(np.abs(entry["normal"])))          # the panel's normal: the axis to drop
        return unary_union([Polygon(np.delete(p, drop, axis=1)) for p in pts])

    pic = next(flat(h) for h in entries if h.get("picture") and h["piece"] == panel)
    others = [flat(h) for h in entries if not h.get("picture") and h["piece"] == panel]
    assert others, "no lightening hole on the picture's panel"
    return min(pic.distance(o) for o in others)


#: A 30 mm hole low in the back, near its corner: the back's still the bigger room, by far.
BACK_HOLE = '''

HOLES = [{"piece": "back", "normal": [0, -1, 0], "depth": 19.05,
          "polygons": [[[60, 254, 60], [90, 254, 60], [90, 254, 90], [60, 254, 90]]]}]
'''


def _holed(tmp_path):
    store = DesignStore.create("a box stool", base=str(tmp_path / "holed"))
    store.write_part("stool", BOX_STOOL + BACK_HOLE, intent="a box step stool")
    return {p["name"]: p for p in pictures.panels(store, "stool")}


def test_a_picture_keeps_a_web_from_a_hole_already_there(tmp_path):
    """#50, a surviving mutant (#72): the room for a picture keeps a web of wood from a panel's holes. Dropped, every test passed."""
    from shapely.geometry import Polygon

    back = _holed(tmp_path)["back"]
    hole = Polygon([((np.asarray(p, float) - back["o"]) @ back["u"], (np.asarray(p, float) - back["o"]) @ back["v"])
                    for p in [(60, 254, 60), (90, 254, 60), (90, 254, 90), (60, 254, 90)]])
    assert back["holes"] == 1 and back["room"].distance(hole) >= lighten.MIN_WEB_MM - 0.5


def test_a_panel_without_holes_is_chosen_before_a_bigger_one_with(tmp_path):
    """#50, a surviving mutant (#72): of the panels the words name, one without holes first. Dropped, every test passed."""
    found = _holed(tmp_path)
    assert found["back"]["room"].area > found["left"]["room"].area        # the back is bigger, hole and all
    assert pictures.choose(list(found.values()), "the left or the back")["name"] == "left"


def test_too_weak_shrinks_it_and_hopeless_says_so(stool, monkeypatch):
    tries = iter([1.2, 1.5, 2.4])
    monkeypatch.setattr(pictures, "_try", lambda *a, **k: next(tries))
    got = pictures.put(stool, "stool", pictures.draw("T-rex", use_llm=False), subject="T-rex", strength=True)
    assert got["ok"] and got["shrunk"] == 2 and "smaller to keep it strong" in got["reply"]

    monkeypatch.setattr(pictures, "_try", lambda *a, **k: 1.1)
    before = stool.design.part("stool").version
    got = pictures.put(stool, "stool", pictures.draw("T-rex", use_llm=False), subject="T-rex")
    assert not got["ok"] and "too weak" in got["reply"] and stool.design.part("stool").version == before


def test_the_chat_routes_a_picture_and_leaves_parts_alone(stool):
    i = chat.offline_classify(stool, "put a T-rex on the side")
    assert (i.action, i.part, i.intent, i.where) == ("picture", "stool", "T-rex", "side")
    assert chat.offline_classify(stool, "cut a dinosaur picture into the front").action == "picture"
    assert chat.offline_classify(stool, "add a foot on the bottom").action != "picture"
    assert chat.offline_classify(stool, "can you put a T-rex on the side?").action == "answer"


# --- through the API: the pad's drawing, cut and checked --------------------------------------------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("whittle")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setattr(load_study, "VOXELS_THROUGH", 2)
    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    return TestClient(create_app()), store.design.slug


def test_a_drawing_from_the_pad_is_cut_out(client):
    c, slug = client
    names = [p["name"] for p in c.get(f"/api/designs/{slug}/parts/stool/picture").json()["panels"]]
    assert "front" in names and "top" not in names
    star = [(160 + 90 * np.cos(a) * (1 if k % 2 == 0 else 0.5), 110 + 90 * np.sin(a) * (1 if k % 2 == 0 else 0.5))
            for k, a in enumerate(np.linspace(0, 2 * np.pi, 10, endpoint=False))]
    job = c.post(f"/api/designs/{slug}/parts/stool/picture",
                 json={"subject": "star", "where": "back", "points": [list(p) for p in star]}).json()
    end = time.time() + 240
    while time.time() < end:
        j = c.get(f"/api/jobs/{job['job_id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert j["status"] == "done" and j["result"]["action"] == "picture" and j["result"]["ok"], j
    state = c.get(f"/api/designs/{slug}").json()
    assert state["parts"][0]["version"] == 2
    kinds = [e["kind"] for e in state["log"]]
    assert kinds[-3:] == ["message", "load", "reply"] and "star" in state["log"][-1]["reply"]   # the recheck between
    assert c.post(f"/api/designs/{slug}/parts/stool/picture", json={}).status_code == 422


def test_a_check_that_couldnt_run_is_never_a_tick(tmp_path):
    """CALI-86 (#62, finding 10; rule 6): with no strength check installed, a part that says what it must hold got
    "✓ … It doesn't say what it must hold" and ok True."""
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    got = pictures.put(store, "stool", pictures.draw("T-rex", use_llm=False), subject="T-rex", where="the side",
                       strength=False)
    assert got["ok"] is False and "✓" not in got["reply"]
    assert "I couldn't check it still holds: the strength check isn't installed" in got["reply"]
    assert "doesn't say what it must hold" not in got["reply"]
    # a part with no loads() at all still says that, and is fine
    plain = DesignStore.create("a box", base=str(tmp_path / "plain"))
    plain.write_part("stool", BOX_STOOL.split("\ndef loads(")[0], intent="a box")
    got = pictures.put(plain, "stool", pictures.draw("T-rex", use_llm=False), subject="T-rex", where="the side",
                       strength=False)
    assert got["ok"] and "doesn't say what it must hold" in got["reply"]


@pytest.mark.parametrize("where,want", [("the right side", {"right"}), ("on the left side", {"left"}),
                                        ("the side", {"left", "right"}), ("the back", {"back"}), ("", {"front"})])
def test_a_named_side_wins_over_the_word_side(where, want):
    """CALI-87 (#63, finding 5): "side" stands for left and right, so "right side" matched both and the bigger
    room won: asked for the right, it cut the left without a word."""
    from shapely.geometry import box

    found = [{"name": "left", "holes": 0, "room": box(0, 0, 200, 150)},       # the most room: the old pick
             {"name": "right", "holes": 0, "room": box(0, 0, 150, 150)},
             {"name": "front", "holes": 0, "room": box(0, 0, 120, 120)},
             {"name": "back", "holes": 0, "room": box(0, 0, 100, 100)}]
    assert pictures.choose(found, where)["name"] in want


def test_a_drawing_with_a_point_that_isnt_a_number_is_refused(client):
    """CALI-87 (#63, finding 6): a NaN from the pad killed the job and left the log with no reply."""
    c, slug = client
    before = len(c.get(f"/api/designs/{slug}").json()["log"])
    for bad in ('[[0, 0], [NaN, 5], [9, 9], [0, 9]]', '[[0, 0], [Infinity, 5], [9, 9], [0, 9]]'):
        got = c.post(f"/api/designs/{slug}/parts/stool/picture", content='{"subject": "x", "points": ' + bad + '}',
                     headers={"content-type": "application/json"})
        assert got.status_code == 422, bad
    assert len(c.get(f"/api/designs/{slug}").json()["log"]) == before


def test_a_picture_job_that_fails_still_answers_in_the_log(client, monkeypatch):
    c, slug = client

    def broken(*a, **k):
        raise RuntimeError("the sandbox died")

    monkeypatch.setattr(chat, "picture_part", broken)
    job = c.post(f"/api/designs/{slug}/parts/stool/picture", json={"subject": "T-rex"}).json()
    end = time.time() + 60
    while time.time() < end:
        j = c.get(f"/api/jobs/{job['job_id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert j["status"] == "error"
    last = c.get(f"/api/designs/{slug}").json()["log"][-1]
    assert last["kind"] == "reply" and last["ok"] is False and "couldn't" in last["reply"]


def test_nor_is_the_chat_turn(tmp_path):
    """CALI-86 (#71 rework, item 9): the turn the person sees in the chat isn't ok either."""
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL, intent="a box step stool")
    res = chat.picture_part(store, "stool", "T-rex", "the side", strength=False, use_llm=False)
    assert res.ok is False and "couldn't check it still holds" in res.reply and "✓" not in res.reply


def test_a_chat_turn_that_fails_still_answers_in_the_log(client, monkeypatch):
    """CALI-87 (#75 rework, item 6): as a picture job does (finding 6), a refine that raises after the person's
    message is logged writes the failure as the reply, so the conversation isn't left hanging."""
    c, slug = client

    def broken(*a, **k):
        raise RuntimeError("the sandbox died")

    monkeypatch.setattr(chat, "refine_part", broken)
    monkeypatch.setattr(chat, "classify", lambda *a, **k: chat.Intent(action="refine", part="stool", intent="taller"))
    job = c.post(f"/api/designs/{slug}/chat", json={"message": "make it a bit taller", "scope": "stool"}).json()
    end = time.time() + 60
    while time.time() < end:
        j = c.get(f"/api/jobs/{job['job_id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert j["status"] == "error"
    log = c.get(f"/api/designs/{slug}").json()["log"]
    assert log[-2]["kind"] == "message" and log[-2]["text"] == "make it a bit taller"
    assert log[-1]["kind"] == "reply" and log[-1]["ok"] is False
    from caliper import errors                                 # the plain sentence with its id, never its words (#70 item 18)

    assert log[-1]["reply"] == errors.plain({"id": j["error_id"]}) and "sandbox" not in log[-1]["reply"], log[-1]


def test_cuttable_does_what_its_words_say():
    """CALI-88 (#64 item 11): "nothing narrower than a blade turns round" overstated it. What the smoothing does: no
    part and no gap narrower than 1/4 in, and every corner rounded to at least 1/8 in, so a scroll blade can follow
    it. Shown as what that means: opening and closing it by 1/8 in leave it as it is."""
    import math

    from shapely.geometry import Polygon

    r = pictures.MIN_FEATURE_MM / 2
    assert abs(r - 0.125 * 25.4) < 1e-9
    # a star with thin spikes and a narrow slot cut into it: both are what a blade can't follow
    pts = [((60 if k % 2 else 18) * math.cos(math.pi * k / 7), (60 if k % 2 else 18) * math.sin(math.pi * k / 7))
           for k in range(14)]
    slot = Polygon([(-2, -40), (2, -40), (2, 0), (-2, 0)])
    shape = Polygon(pts).buffer(4).difference(slot)
    got = pictures.cuttable(shape)
    assert got is not None and got.is_valid
    opened = got.buffer(-r).buffer(r)                     # nothing narrower than 2r: opening changes nothing
    closed = got.buffer(r).buffer(-r)                     # no gap narrower than 2r, inside corners >= r
    assert got.symmetric_difference(opened).area < 0.01 * got.area
    assert got.symmetric_difference(closed).area < 0.01 * got.area
    # and it did change the shape it was given (the slot and the spikes' tips were too fine)
    assert shape.symmetric_difference(got).area > 0.01 * shape.area
    assert "no part or gap narrower than 1/4 in" in pictures.cuttable.__doc__ and "1/8 in" in pictures.cuttable.__doc__


def test_a_pictures_edge_is_judged_at_kt_times_the_walls_stress_there():
    """CALI-88 (#64 item 5): a picture in a wall got the voxel FEA alone, which reads low at a sharp re-entrant edge.
    Its edge is now KT_HOLE times the stress the wall had there solid; and a picture whose edge reaches into where
    the wall works harder (a notch up into it) reads lower than one that doesn't."""
    from shapely.geometry import Polygon

    s = 2.0
    shape = (40, 40)
    cells = np.argwhere(np.ones(shape, dtype=bool))
    p = {"shape": shape, "lo": np.array([0.0, 0.0]), "inside": np.ones(shape, dtype=bool),
         "voxels": np.column_stack([cells, np.zeros(len(cells), dtype=int)]), "cells": cells}
    stress = np.zeros((40, 40, 1))
    stress[:, :, 0] = 1.0 + np.arange(40)[None, :] / 4.0     # works harder going up the wall (v)
    solid = np.ones((40, 40, 1), dtype=bool)
    square = Polygon([(20, 10), (60, 10), (60, 30), (20, 30)])
    notched = square.union(Polygon([(38, 30), (42, 30), (42, 60), (38, 60)]))
    plain = lighten.picture_edge(p, [square], stress, solid, s, allow=40.0)
    worst_cell = 1.0 + 14 / 4.0                               # the square's highest cell, v up to 30 mm
    assert plain == pytest.approx(40.0 / (lighten.KT_HOLE * worst_cell), rel=1e-6)
    assert lighten.picture_edge(p, [notched], stress, solid, s, allow=40.0) < plain
    assert lighten.picture_edge(p, [Polygon([(200, 200), (210, 200), (210, 210)])], stress, solid, s, 40.0) == np.inf
