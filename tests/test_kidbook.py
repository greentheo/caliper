"""CALI-79 (#47) — a build book a kid can follow: pictures first, one step a page."""

import os
import re

import pytest

from caliper import construction as C
from caliper import kidbook, release
from caliper.design import DesignStore

from .test_lighten import HOLE
from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")


@pytest.fixture
def stool(tmp_path):
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL + HOLE.replace('"piece": "left"', '"piece": "left", "picture": "T-rex"'),
                     intent="a box step stool")
    return store


def test_a_wooden_build_gets_one_and_a_welded_frame_doesnt(stool, tmp_path):
    assert kidbook.suits(stool, ["stool"])
    frame = DesignStore.create("a frame", base=str(tmp_path / "frames"))
    frame.write_part("f", "def build(params):\n    return None\n\ndef members(params):\n    return []\n", intent="x")
    assert not kidbook.suits(frame, ["f"])


def test_one_page_a_piece_in_the_order_they_go_together(stool, tmp_path):
    root = str(tmp_path / "release")
    os.makedirs(root)
    shop = {"groups": [{"rows": [{"qty": "1", "item": "sheet 3/4 in plywood"},
                                 {"qty": "18 (a box of 50)", "item": "#8 wood screws"}]}]}
    rec = {"design": "Box stool", "strength": {"stool": [{"name": "An adult stepping up", "safety": 3.11}]}}
    assert kidbook.make(stool, root, rec, ["stool"], shop) == "kids.html"
    book = open(os.path.join(root, "kids.html")).read()
    titles = re.findall(r"<h2><span class='n'>\d+</span>([^<]+)</h2>", book)
    assert titles[:4] == ["Get your things", "Draw the pieces", "Cut them out", "Sand the edges"]
    assert titles[-1] == "Test it" and titles[-2] == "Add the top"          # the top goes on last
    assert titles[4].startswith("Start with the") and len(titles) == 4 + 5 + 1
    assert "18 #8 wood screws" in book and "a box of 50" not in book       # a kid's words
    assert "For the T-rex, drill a hole just inside the line first" in book
    assert "3.1 times over" in book and "not a certificate" in book
    for k in range(5, 10):
        assert os.path.exists(os.path.join(root, "kids", f"step-{k:02d}.png"))
    # every screw the shopping list counts goes in on some page
    said = sum(int(n) for n in re.findall(r"put in (\d+) screws", book))
    assert said == C.report(stool, "stool")["bom"]["fasteners"]["screws"]


def test_drawings_show_a_panels_holes_and_look_at_the_picture(stool):
    pcs = {p["name"]: p for p in release.pieces(stool, "stool")}
    (outline, holes), = pcs["left"]["polys"]
    assert len(holes) == 1 and len(holes[0]) == 4                          # the 2 in square through the left wall
    az = kidbook.facing(list(pcs.values()), {"left"})
    import math

    assert math.cos(math.radians(az)) < -0.5                               # looking at the left side (x = 0)
    assert math.sin(math.radians(az)) < 0                                  # and the front (y = 0) with it
    assert kidbook.facing(list(pcs.values()), set()) == 35.0
