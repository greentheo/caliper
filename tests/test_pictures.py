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
    assert got["holds"] and got["safety"] >= got["min_safety"] and got["predicted"] is not None
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
