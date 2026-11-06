"""CALI-97 (#80; rule 6) — a ✓ can't rest on an FEA too coarse to see the wall it's checking.

Found on Theo's bar stool: "✓ Holds a 250 lb person sitting … 2.58x", governed by the FEA, at 4.6 mm voxels across
a 3.9 mm printed wall (about one voxel through it)."""

import os

import pytest

from caliper import answers, design_api, load_study
from caliper.design import DesignStore

pytest.importorskip("cadquery")

#: A printed PETG tube, 4 mm wall, stood on: the load on its rim, held by the floor.
TUBE = '''import cadquery as cq

PARAMS = {"r": 30.0, "h": 80.0, "wall": 4.0}
BUILD = {"material": "petg", "infill": 0.4}


def build(params):
    p = {**PARAMS, **(params or {})}
    return cq.Workplane().circle(p["r"]).circle(p["r"] - p["wall"]).extrude(p["h"])


def construction(params, build=None):
    b = {**BUILD, **(build or {})}
    return [{"name": "tube", "kind": "printed", "material": b["material"], "infill": b["infill"]}]


def loads(params, build=None):
    p = {**PARAMS, **(params or {})}
    return [{"name": "a foot", "lb": 40, "factor": 2.0, "lo": (-32, -32, p["h"] - 2), "hi": (32, 32, p["h"])}]
'''
GOALS = """written_by: caliper
checks:
- id: strength_foot
  label: holds a foot (40 lb), 2 times over
  metric: strength.safety
  op: '>='
  limit: 2.0
  source: assumed
"""
COARSE = "Not resolved yet: the check was too coarse to see its 4 mm walls. Check it again finer."


def _studied(tmp_path, monkeypatch, through):
    pytest.importorskip("whittle")
    monkeypatch.setattr(load_study, "VOXELS_THROUGH", through)
    store = DesignStore.create("a tube", base=str(tmp_path / f"designs{through}"))
    store.write_part("tube", TUBE, intent="a printed tube")
    with open(os.path.join(store.root, "scorecard.yaml"), "w") as f:
        f.write(GOALS)
    return store, load_study.study(store, "tube")


def _work(store, pid=None):
    lines = answers.answers(store, design_api.design_state(store), pid)[1]["lines"]
    return [ln for ln in lines if ln.get("study") == "load"]


def test_a_verdict_on_an_fea_that_cant_see_the_wall_reads_warn(tmp_path, monkeypatch):
    store, rec = _studied(tmp_path, monkeypatch, 1)               # 4 mm voxels across a 4 mm wall: one voxel
    (case,) = rec["cases"]
    assert case["governs"] == "fea" and rec["thinnest_mm"] == pytest.approx(4.0, abs=0.3)
    assert rec["spacing_mm"] > rec["thinnest_mm"] / 2 and not rec["resolved"]
    part = _work(store, "tube")
    assert part and all(ln["status"] == "warn" and ln["text"] == COARSE for ln in part), part
    design = _work(store)
    assert design and all(ln["status"] == "warn" and COARSE in ln["text"] for ln in design), design
    # the finer run it offers: at least 2 voxels across, and how long it'll take
    assert rec["finer"]["spacing_mm"] <= rec["thinnest_mm"] / 2 and rec["finer"]["minutes"] > 0
    finer = load_study.study(store, "tube", spacing=rec["finer"]["spacing_mm"])
    assert finer["resolved"] and finer["spacing_mm"] == pytest.approx(rec["finer"]["spacing_mm"], abs=0.01)
    assert not [ln for ln in _work(store, "tube") if ln["text"] == COARSE]


def test_the_same_tube_seen_finely_reads_as_its_safety_says_with_about(tmp_path, monkeypatch):
    store, rec = _studied(tmp_path, monkeypatch, 2)               # 2 mm voxels: two across the wall
    assert rec["resolved"]
    (part,) = _work(store, "tube")
    assert part["text"].startswith(("Holds a foot, about ", "Doesn't hold a foot: only about ")), part["text"]
    (design,) = _work(store)
    assert ": about " in design["text"] and design["text"].endswith("x."), design["text"]
