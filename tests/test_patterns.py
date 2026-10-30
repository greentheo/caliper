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
