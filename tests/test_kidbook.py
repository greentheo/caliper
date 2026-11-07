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
    rec = {"design": "Box stool", "strength": {"stool": [{"name": "An adult stepping up", "safety": 3.11, "verdict": {"kind": "holds"}}]}}
    assert kidbook.make(stool, root, rec, ["stool"], shop) == "kids.html"
    book = open(os.path.join(root, "kids.html")).read()
    titles = re.findall(r"<h2><span class='n'>\d+</span>([^<]+)</h2>", book)
    assert titles[:4] == ["Get your things", "Draw the pieces", "Cut them out", "Sand the edges"]
    assert titles[-1] == "Test it" and titles[-2] == "Add the top"          # the top goes on last
    assert titles[4].startswith("Start with the") and len(titles) == 4 + 5 + 1
    assert "18 #8 wood screws" in book and "a box of 50" not in book       # a kid's words
    assert "For the T-rex, the grown-up drills a hole just inside the line first" in book
    assert "3.1 times over" in book and "not a certificate" in book
    for k in range(5, 10):
        assert os.path.exists(os.path.join(root, "kids", f"step-{k:02d}.png"))
    # every screw the shopping list counts goes in on some page
    said = sum(int(n) for n in re.findall(r"drives in (\d+) screws", book))
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


def test_no_page_puts_a_kid_s_hands_at_the_work_while_a_tool_runs(stool, tmp_path):
    """CALI-86 (#62, finding 6; rule 6): the cut page had the kid holding the pattern while the jigsaw ran, and the
    screw pages had them holding a piece while it was screwed. A grown-up clamps, cuts and drives the screws; the
    kid stands back with safety glasses on while a tool runs."""
    root = str(tmp_path / "release")
    os.makedirs(root)
    rec = {"design": "Box stool", "strength": {"stool": [{"name": "An adult stepping up", "safety": 3.11, "verdict": {"kind": "holds"}}]}}
    kidbook.make(stool, root, rec, ["stool"], {"groups": []})
    import html

    book = html.unescape(open(os.path.join(root, "kids.html")).read())      # as the page reads
    pages = re.findall(r"<section class='step'>(.*?)</section>", book, re.S)
    tool = [p for p in pages if re.search(r"jigsaw|drill|screws", re.sub(r"<[^>]+>", " ", p.split("</h2>", 1)[1]),
                                          re.I) and "Get your things" not in p]
    assert len(tool) >= 5                                  # cutting, and every piece that's screwed on
    for p in tool:
        said = " ".join(re.findall(r"<p class='say'>(.*?)</p>", p, re.S))
        assert not AT_THE_WORK.search(said), said
        assert "grown-up" in said and "arm's length behind" in said and "safety glasses" in said, said
        assert "ear defenders" in said, said
    assert "two clamps" in book and "ear defenders" in book    # on the list too
    cut = next(p for p in tool if "Cut them out" in p)
    assert "past the table's edge" in cut and "never in front of the saw" in cut
    # the test of the finished stool is a grown-up's step: they stand on it first, the kid watches (rule 6)
    test = next(p for p in pages if "Test it" in p)
    assert re.search(r"A grown-up stands on it first.*while you watch", test), test


#: A kid's hands at the work: what no page with a running tool may ask (CALI-86, the reviewer's list included).
AT_THE_WORK = re.compile(r"\bhold|\bsteady|\bpress|\bgrip|hand flat|hands? on the|both hands", re.I)


@pytest.mark.parametrize("said", ["hold the pattern still", "grip the board so it can't move",
                                  "put your hand flat on the wood next to the line", "keep both hands on the piece",
                                  "steady it for the grown-up", "press it down"])
def test_the_check_catches_every_way_of_putting_a_kids_hands_there(said):
    assert AT_THE_WORK.search(said)


def test_two_pieces_with_one_name_get_the_screws_the_shopping_list_counts(tmp_path):
    """CALI-87 (#63, finding 9): joints were keyed by name, so two pieces both called "side" against the top were one
    joint to the shopping list and two to the book (22 screws on the pages, 16 in the BOM)."""
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    same = BOX_STOOL.replace('"left": [(0, 0, 0)', '"side": [(0, 0, 0)').replace('"right": [(w, 0, 0)', '"side ": [(w, 0, 0)')
    same = same.replace('return [{"name": k, "kind": "sheet"', 'return [{"name": k.strip(), "kind": "sheet"')
    assert same.count('"side') == 2
    store.write_part("stool", same, intent="a box stool, both sides called side")
    assert [p["name"] for p in C.declared(store, "stool")["construction"]].count("side") == 2
    root = str(tmp_path / "release")
    os.makedirs(root)
    kidbook.make(store, root, {"design": "Box stool", "strength": {}}, ["stool"], {"groups": []})
    book = open(os.path.join(root, "kids.html")).read()
    said = sum(int(n) for n in re.findall(r"drives in (\d+) screws", book))
    assert said == C.report(store, "stool")["bom"]["fasteners"]["screws"]
    assert said == 18                       # as with the sides named apart: 8 joints, none merged, none twice


SHARED = [c for k in range(2, 6) for c in __import__("itertools").combinations(
    ["left", "right", "front", "back", "top"], k)]


@pytest.mark.parametrize("same", SHARED, ids=["+".join(c) for c in SHARED])
def test_any_pieces_sharing_a_name_still_get_a_book(tmp_path, same):
    """CALI-87 (#75 rework, item 1): order() removed the chosen piece with ==, which compares numpy arrays, so 8 of
    these 26 crashed (every one where left and back share a name) and the package shipped with no kids' book."""
    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    src = BOX_STOOL.replace('return [{"name": k, "kind": "sheet"',
                            f'return [{{"name": "side" if k in {list(same)!r} else k, "kind": "sheet"')
    store.write_part("stool", src, intent="a box stool, some pieces sharing a name")
    root = str(tmp_path / "release")
    os.makedirs(root)
    kidbook.make(store, root, {"design": "Box stool", "strength": {}}, ["stool"], {"groups": []})
    book = open(os.path.join(root, "kids.html")).read()
    assert sum(int(n) for n in re.findall(r"drives in (\d+) screws", book)) == 18


def test_pieces_with_one_name_are_told_apart_on_the_pages(tmp_path):
    """CALI-87 (#75 rework, item 3): drawings were found by name, so both "side" pages drew the same piece, and
    both said "Add the side"."""
    import html

    store = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    store.write_part("stool", BOX_STOOL.replace('return [{"name": k, "kind": "sheet"',
                                                'return [{"name": "side" if k in ("left", "right") else k, "kind": "sheet"'),
                     intent="a box stool, both sides called side")
    root = str(tmp_path / "release")
    os.makedirs(root)
    kidbook.make(store, root, {"design": "Box stool", "strength": {}}, ["stool"], {"groups": []})
    book = html.unescape(open(os.path.join(root, "kids.html")).read())
    titles = re.findall(r"<h2><span class='n'>\d+</span>([^<]+)</h2>", book)
    sides = [t for t in titles if t.endswith("side")]
    assert sorted(sides) == sorted({"Start with the first side", "Add the first side"} & set(sides)
                                   | {"Add the other side"}) and len(set(sides)) == 2, titles
    pages = re.findall(r"<section class='step'>(.*?)</section>", book, re.S)
    imgs = [re.search(r"src='(kids/step-\d+\.png)'", p).group(1) for p in pages if re.search(r"<h2>.*side</h2>", p)]
    assert len(imgs) == 2 and open(os.path.join(root, imgs[0]), "rb").read() != open(os.path.join(root, imgs[1]), "rb").read()
    top = next(p for p in pages if "Add the top" in p)
    assert "touches both sides" in top, top
