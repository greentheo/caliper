"""CALI-108 (#108, the backend) — a part's exact numbers, set by hand, with no Claude call.

Theo: "the advantage to manual cad is the ability to specify things precisely". Listing a part's PARAMS in plain
words, and setting one: converted to mm, refused outside its range, only its line rewritten (its comment kept), built,
written as a new version that says so, the design measured again, and a value the build ignores or clamps said."""

import pytest

from caliper import aero, params
from caliper.design import DesignStore

pytest.importorskip("cadquery")

BOX = '''import cadquery as cq

PARAMS = {
    "w": 400.0,         # width of the box
    # how tall it stands
    "h": 200.0,
    "fillet_r": 6.0,    # fillet radius at the top edges mm
    "spare": 3.0,       # a number the build never reads
}
RANGES = {"h": (100.0, 300.0), "w": (100.0, 800.0)}


def build(params):
    p = {**PARAMS, **(params or {})}
    r = min(p["fillet_r"], 2.0)          # clamped: anything over 2 mm is 2 mm
    return cq.Workplane().box(p["w"], 100.0, p["h"]).edges("|Z").fillet(r)
'''


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import caliper.chat as chat

    def no_claude(*a, **k):
        raise AssertionError("a number set by hand never asks Claude")

    monkeypatch.setattr(chat, "author_part", no_claude)
    monkeypatch.setattr(chat, "refine_part", no_claude)
    s = DesignStore.create("a box", base=str(tmp_path / "designs"))
    s.write_part("box", BOX, intent="a box")
    return s


def test_the_numbers_are_listed_in_plain_words_with_their_ranges(store):
    got = {e["name"]: e for e in params.listing(store, "box")}
    assert list(got) == ["w", "h", "fillet_r", "spare"]
    assert got["w"] == {"name": "w", "note": "width of the box", "value": 400.0, "unit": "mm", "range": [100.0, 800.0],
                        "read": True}
    assert got["h"]["note"] == "how tall it stands"                               # the comment line just above it
    assert got["fillet_r"]["range"] is None and got["spare"]["read"] is False


def test_only_that_params_line_is_rewritten_its_comment_kept():
    new = aero.write_params(BOX, {"fillet_r": 1.5}, keep_float=True)
    before, after = BOX.splitlines(), new.splitlines()
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(before) == len(after) and changed == [
        ('    "fillet_r": 6.0,    # fillet radius at the top edges mm', '    "fillet_r": 1.5,    # fillet radius at the top edges mm')]
    assert '"h": 250.0,' in aero.write_params(BOX, {"h": 250}, keep_float=True)    # a float stays a float
    assert '"h": 250,' in aero.write_params(BOX, {"h": 250})                       # as the drag study writes it


def test_setting_a_number_writes_a_new_version_rebuilt_and_measured_with_no_claude_call(store):
    v = store.design.part("box").version
    got = params.set_value(store, "box", "h", 250, "mm")
    assert got["version"] == v + 1 and got["said"] == "set h to 250 mm by hand" and got["warning"] is None
    assert '"h": 250.0,' in store.read_script("box")
    assert store.part_geometry("box").require_mesh().extents[2] == pytest.approx(250.0, abs=0.01)
    h = store.history("box")[-1]
    assert h["action"] == "params" and h["feedback"] == "set h to 250 mm by hand" and h["params"] == {"h": [200.0, 250.0]}
    assert got["report"] is not None                                               # the design measured again


def test_inches_in_millimetres_stored(store):
    got = params.set_value(store, "box", "h", 10, "in")
    assert got["value"] == pytest.approx(254.0) and got["said"] == "set h to 10 in by hand"
    assert '"h": 254.0,' in store.read_script("box")


def test_a_value_outside_its_range_is_refused_with_the_range_and_nothing_written(store):
    v = store.design.part("box").version
    with pytest.raises(ValueError, match=r"^h must be between 100 and 300 mm: 400 mm is outside it$"):
        params.set_value(store, "box", "h", 400, "mm")
    with pytest.raises(ValueError, match=r"^h must be between 100 and 300 mm: 1 ft is outside it$"):
        params.set_value(store, "box", "h", 1, "ft")                               # 304.8 mm
    with pytest.raises(ValueError, match="has no number called 'depth'"):
        params.set_value(store, "box", "depth", 10)
    with pytest.raises(ValueError, match="is a length: give it in mm or in"):
        params.set_value(store, "box", "h", 10, "furlongs")
    assert store.design.part("box").version == v and '"h": 200.0,' in store.read_script("box")


def test_a_value_the_build_ignores_or_clamps_is_said(store):
    clamped = params.set_value(store, "box", "fillet_r", 8, "mm")
    assert clamped["moved"] is False
    assert clamped["warning"] == "the part's shape didn't change: its build clamps or ignores fillet_r at 8 mm"
    unread = params.set_value(store, "box", "spare", 9, "mm")
    assert unread["warning"] == "spare isn't used by the part's build, so setting it changed nothing"


def test_the_api_lists_and_sets_a_number(store, monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from caliper.server import create_app

    monkeypatch.setenv("CALIPER_DESIGNS", str(tmp_path / "designs"))
    c, slug = TestClient(create_app()), store.design.slug
    listed = c.get(f"/api/designs/{slug}/parts/box/params").json()
    assert [e["name"] for e in listed["params"]] == ["w", "h", "fillet_r", "spare"]
    got = c.post(f"/api/designs/{slug}/parts/box/params", json={"name": "w", "value": 500, "unit": "mm"})
    assert got.status_code == 200 and got.json()["said"] == "set w to 500 mm by hand"
    assert next(p for p in got.json()["design"]["parts"] if p["id"] == "box")["version"] == 2
    bad = c.post(f"/api/designs/{slug}/parts/box/params", json={"name": "w", "value": 900, "unit": "mm"})
    assert bad.status_code == 422 and "w must be between 100 and 800 mm" in bad.json()["detail"]
