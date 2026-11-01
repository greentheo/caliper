"""CALI-48 (#4) — patterns for hand tools: measure and mark, print and tape, project and trace."""

import os
import re

import pytest

from caliper import patterns
from caliper.design import DesignStore

from .test_lighten import HOLE
from .test_load_study import BOX_STOOL

pytest.importorskip("cadquery")


@pytest.fixture
def store(tmp_path):
    s = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    s.write_part("stool", BOX_STOOL + HOLE, intent="a box step stool with a hole in its left side")
    return s


def test_every_flat_piece_lies_flat_with_its_long_edge_down(store):
    pcs = {p["name"]: p for p in patterns.pieces(store, "stool")}
    assert sorted(pcs) == ["back", "front", "left", "right", "top"]
    left = pcs["left"]
    assert left["size"] == pytest.approx([254.0, 228.6], abs=0.01)               # 10 x 9 in, long side down
    assert left["outline"].min() == pytest.approx(0.0, abs=1e-6)
    (h,) = left["holes"]                                                           # the 2 in square hole
    assert h.max(axis=0) - h.min(axis=0) == pytest.approx([50.8, 50.8], abs=0.01)
    assert (h.min(axis=0) >= 0).all() and (h.max(axis=0) <= left["size"]).all()
    assert pcs["top"]["label"] == "3/4 in softwood plywood" and not pcs["top"]["holes"]


def test_the_patterns_print_at_true_size(store):
    rec = patterns.make(store, "stool")
    root = os.path.join(patterns.runs_dir(store), rec["id"])
    assert {"measure-and-mark.pdf", "print-full-size.pdf", "index.html", "project-left.svg"} <= set(rec["files"])
    full = open(os.path.join(root, "print-full-size.pdf"), "rb").read()
    boxes = re.findall(rb"/MediaBox \[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", full)
    assert len(boxes) == rec["pages"] and rec["pages"] == sum(p["pages"] + 1 for p in rec["pieces"])
    # every page a letter page: 8.5 x 11 in at 72 points an inch, either way up
    assert all(sorted((float(w), float(h))) == [612.0, 792.0] for w, h in boxes)
    measure = open(os.path.join(root, "measure-and-mark.pdf"), "rb").read()
    assert len(re.findall(rb"/Type\s*/Page\b", measure)) == 5
    svg = open(os.path.join(root, "project-left.svg")).read()
    assert re.search(r'width="(\d+\.\d+)in"', svg) and "zoom until this is 4 in square" in svg
    assert svg.count("<polygon") == 2                                              # the outline and its hole
    assert store.history("stool")[-1]["kind"] == "patterns"
    assert next(p for p in rec["pieces"] if p["name"] == "left")["holes"] == 1


def test_a_part_with_nothing_flat_has_no_patterns(tmp_path):
    s = DesignStore.create("a block", base=str(tmp_path / "designs"))
    s.write_part("block", "def build(params):\n    import cadquery as cq\n    return cq.Workplane().box(10, 10, 10)\n")
    with pytest.raises(ValueError, match="no flat sheet pieces"):
        patterns.make(s, "block")


#: An L-shaped hole in each side, which faces opposite ways: the pattern must be the L as seen from outside.
L = [(40, 40), (120, 40), (120, 70), (70, 70), (70, 140), (40, 140)]
L_HOLES = f'''

HOLES = [{{"piece": "left", "normal": [1, 0, 0], "depth": 19.05,
          "polygons": [{[[0.0, y, z] for y, z in L]}]}},
         {{"piece": "right", "normal": [-1, 0, 0], "depth": 19.05,
          "polygons": [{[[406.4, y, z] for y, z in L]}]}}]
'''


def _signed_area(pts) -> float:
    import numpy as np

    p = np.asarray(pts, float)
    return 0.5 * float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]))


#: The same L on the front and back (±y), which an x-only reading of "outside" gets wrong (the reviewer's mutant).
L_HOLES_Y = f'''

HOLES = [{{"piece": "front", "normal": [0, 1, 0], "depth": 19.05,
          "polygons": [{[[60.0 + x, 0.0, z] for x, z in L]}]}},
         {{"piece": "back", "normal": [0, -1, 0], "depth": 19.05,
          "polygons": [{[[60.0 + x, 254.0, z] for x, z in L]}]}}]
'''


@pytest.mark.parametrize("piece,outward", [("left", (-1, 0, 0)), ("right", (1, 0, 0)),
                                           ("front", (0, -1, 0)), ("back", (0, 1, 0))])
def test_each_pattern_is_the_panel_seen_from_its_outside_face(tmp_path, piece, outward):
    """CALI-86 (#62, finding 7): the left side's pattern was mirrored, so a T-rex traced from it faced the wrong way.
    Turning a pattern round keeps which way an L goes round; mirroring it reverses it."""
    import numpy as np

    s = DesignStore.create("a box stool", base=str(tmp_path / "designs"))
    sideways = piece in ("left", "right")
    s.write_part("stool", BOX_STOOL + (L_HOLES if sideways else L_HOLES_Y), intent="L holes in two panels")
    pc = next(p for p in patterns.pieces(s, "stool") if p["name"] == piece)
    (hole,) = pc["holes"]
    m = np.asarray(outward, float)                         # towards someone standing outside, looking at it
    up = np.array([0.0, 0.0, 1.0])
    right = np.cross(up, m)
    if sideways:
        x0 = 0.0 if piece == "left" else 406.4
        corners = [np.array([x0, y, z]) for y, z in L]
    else:
        y0 = 0.0 if piece == "front" else 254.0
        corners = [np.array([60.0 + x, y0, z]) for x, z in L]
    seen = [(q @ right, q[2]) for q in corners]
    assert np.sign(_signed_area(hole)) == np.sign(_signed_area(seen))
    assert pc["face"] == "outside"
    rec = patterns.make(s, "stool")
    svg = open(os.path.join(patterns.runs_dir(s), rec["id"], f"project-{piece}.svg")).read()
    assert "this is the outside face" in svg


def test_every_page_title_is_in_characters_the_page_font_has(store):
    """CALI-86 (#69 rework, item 5): the titles joined with an em dash, which PIL's default font hasn't got, so the
    pages printed "3/4 in softwood plywood ▯ this is the outside face"."""
    from PIL import Image, ImageDraw

    font = patterns._font(40)

    def ink(ch):
        im = Image.new("L", (90, 90), 0)
        ImageDraw.Draw(im).text((10, 10), ch, fill=255, font=font)
        return im.tobytes()

    missing = ink("\U0010FFFF")
    assert ink("—") == missing                              # the check can tell: the old title's dash fails it
    for pc in patterns.pieces(store, "stool"):
        for title in patterns.titles(pc, cols=2, rows=2).values():
            gone = sorted({ch for ch in title if not ch.isspace() and ink(ch) == missing})
            assert not gone, (title, gone)
